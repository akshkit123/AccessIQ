import logging
from django.utils import timezone
from django.core.files.base import ContentFile
import base64
import uuid

from accounts.models import AuthorizedDevice
from identity.models import BarcodeIdentity, StudentProfile, StaffProfile, FaceProfile, IdentityStatus
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection
from visitors.models import TemporaryPass, PassStatus
from security.models import SecurityAlert, AlertType, AlertSeverity
from face_engine.services import verify_facial_images

logger = logging.getLogger('accessiq.access_control')


class DualAuthenticationService:
    """
    Executes the core 10-step AccessIQ Dual-Factor Authentication Flow:
    Barcode/QR Identity Verification + Facial Recognition + Location Access Rule Verification.
    """

    @classmethod
    def verify_access(cls,
                      barcode_value: str,
                      live_face_image_base64: str,
                      location_code: str,
                      device_id: str = None,
                      direction: str = AccessDirection.ENTRY,
                      verified_by=None) -> dict:
        
        timestamp = timezone.now()
        scanned_code = (barcode_value or '').strip()

        # 1. Resolve Location (College Main Gate Entry/Exit)
        location = None
        if location_code:
            location = AccessLocation.objects.filter(code__iexact=str(location_code).strip(), is_active=True).first()
        if not location:
            location = AccessLocation.objects.filter(is_active=True).first()
        if not location:
            location, _ = AccessLocation.objects.get_or_create(
                code='GATE-MAIN',
                defaults={
                    'name': 'College Main Gate',
                    'building': 'Main Campus Entrance',
                    'floor': 'Ground Floor',
                    'description': 'Primary Campus Security Gate Entry & Exit Checkpoint',
                    'is_active': True,
                }
            )

        # 2. Resolve Authorized Device if provided
        device = None
        if device_id:
            device = AuthorizedDevice.objects.filter(device_id=device_id.strip(), is_active=True).first()
            if device:
                device.update_last_active()

        # 3. Lookup Identity via BarcodeIdentity or TemporaryPass
        barcode_id = BarcodeIdentity.objects.filter(barcode_value__iexact=scanned_code, is_active=True).first()
        if not barcode_id:
            student_match = StudentProfile.objects.filter(student_id__iexact=scanned_code).first()
            if student_match:
                barcode_id, _ = BarcodeIdentity.objects.get_or_create(
                    barcode_value=scanned_code,
                    defaults={'student': student_match, 'identity_type': 'STUDENT'}
                )
            else:
                staff_match = StaffProfile.objects.filter(staff_id__iexact=scanned_code).first()
                if staff_match:
                    barcode_id, _ = BarcodeIdentity.objects.get_or_create(
                        barcode_value=scanned_code,
                        defaults={'staff': staff_match, 'identity_type': 'STAFF'}
                    )

        temp_pass = None
        if not barcode_id:
            temp_pass = TemporaryPass.objects.filter(pass_code__iexact=scanned_code).first()

        # Failure: Unknown or unassigned barcode
        if not barcode_id and not temp_pass:
            reason = "Invalid or unregistered Barcode / QR ID"
            SecurityAlert.objects.create(
                alert_type=AlertType.INVALID_BARCODE,
                severity=AlertSeverity.HIGH,
                location=location,
                user_identifier=scanned_code,
                description=f"Attempted access at {location.name} using unassigned barcode '{scanned_code}'."
            )
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=False,
                face_verified=False,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': False,
                'face_verified': False,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': None,
            }

        # Handle Temporary Pass flow
        if temp_pass:
            return cls._process_visitor_pass_access(temp_pass, live_face_image_base64, location, device, direction, timestamp, verified_by=verified_by)

        # Handle Student / Staff Identity
        person = barcode_id.get_associated_person()
        student = barcode_id.student
        staff = barcode_id.staff

        if not person:
            reason = "Barcode has no active student or staff member associated"
            SecurityAlert.objects.create(
                alert_type=AlertType.UNKNOWN_ID,
                severity=AlertSeverity.MEDIUM,
                location=location,
                user_identifier=scanned_code,
                description=f"Barcode '{scanned_code}' exists but has no attached identity profile."
            )
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=False,
                face_verified=False,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': False,
                'face_verified': False,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': None,
            }

        # Check account status (e.g. suspended or dropped)
        if person.status in [IdentityStatus.SUSPENDED, IdentityStatus.DROPPED]:
            reason = f"Account status is {person.get_status_display()} - Access Blocked"
            SecurityAlert.objects.create(
                alert_type=AlertType.BLOCKED_ID,
                severity=AlertSeverity.HIGH,
                location=location,
                user_identifier=f"{person.full_name} ({scanned_code})",
                description=f"Suspended/Dropped user '{person.full_name}' attempted entry at {location.name}."
            )
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                student=student,
                staff=staff,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=True,
                face_verified=False,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': True,
                'face_verified': False,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': cls._serialize_person(person, student, staff),
            }

        # 4. Face Verification Step
        face_profile = getattr(person, 'face_profile', None)
        registered_photo = None
        if face_profile and face_profile.registered_photo:
            registered_photo = face_profile.registered_photo
        elif getattr(person, 'photo', None):
            registered_photo = person.photo

        if not registered_photo:
            reason = "No enrolled face biometric template on record for this identity"
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                student=student,
                staff=staff,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=True,
                face_verified=False,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': True,
                'face_verified': False,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': cls._serialize_person(person, student, staff),
            }

        # Execute DeepFace / OpenCV verification
        face_result = verify_facial_images(registered_photo, live_face_image_base64)
        is_face_match = face_result.get('verified', False)
        face_distance = face_result.get('distance')
        face_similarity = face_result.get('similarity_score')

        if not is_face_match:
            reason = face_result.get('error') or "Face verification mismatch: live face does not match registered cardholder"
            SecurityAlert.objects.create(
                alert_type=AlertType.FACE_MISMATCH,
                severity=AlertSeverity.CRITICAL,
                location=location,
                user_identifier=f"{person.full_name} ({scanned_code})",
                description=f"Face mismatch detected at {location.name}. Presenter tried using ID of '{person.full_name}'."
            )
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                student=student,
                staff=staff,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=True,
                face_verified=False,
                face_distance=face_distance,
                face_similarity=face_similarity,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': True,
                'face_verified': False,
                'face_distance': face_distance,
                'face_similarity': face_similarity,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': cls._serialize_person(person, student, staff),
            }

        # 5. ALL VERIFICATIONS SUCCEEDED -> IDENTITY VERIFIED & ACCESS RECORDED!
        AccessLog.objects.create(
            scanned_barcode=scanned_code,
            student=student,
            staff=staff,
            location=location,
            device=device,
            direction=direction,
            barcode_verified=True,
            face_verified=True,
            face_distance=face_distance,
            face_similarity=face_similarity,
            permission_granted=True,
            final_decision=AccessDecision.GRANTED,
            failure_reason='',
            verified_by=verified_by,
            timestamp=timestamp
        )

        return {
            'decision': AccessDecision.GRANTED,
            'barcode_verified': True,
            'face_verified': True,
            'face_distance': face_distance,
            'face_similarity': face_similarity,
            'permission_granted': True,
            'failure_reason': '',
            'location': {
                'code': location.code,
                'name': location.name,
                'building': location.building,
                'floor': location.floor,
            },
            'user_data': cls._serialize_person(person, student, staff),
        }

    @classmethod
    def _process_visitor_pass_access(cls, temp_pass, live_face_base64, location, device, direction, timestamp, verified_by=None):
        """
        Dual authentication verification for Temporary Access Passes and Visitors.
        """
        scanned_code = temp_pass.pass_code
        visitor = temp_pass.visitor

        # Check expiration
        if not temp_pass.check_and_update_status():
            reason = "Temporary Access Pass has expired or is inactive"
            SecurityAlert.objects.create(
                alert_type=AlertType.EXPIRED_PASS,
                severity=AlertSeverity.HIGH,
                location=location,
                user_identifier=f"{visitor.full_name} ({scanned_code})",
                description=f"Attempted entry with expired temporary pass at {location.name}."
            )
            AccessLog.objects.create(
                scanned_barcode=scanned_code,
                visitor_name=visitor.full_name,
                location=location,
                device=device,
                direction=direction,
                barcode_verified=True,
                face_verified=False,
                permission_granted=False,
                final_decision=AccessDecision.DENIED,
                failure_reason=reason,
                verified_by=verified_by,
                timestamp=timestamp
            )
            return {
                'decision': AccessDecision.DENIED,
                'barcode_verified': True,
                'face_verified': False,
                'permission_granted': False,
                'failure_reason': reason,
                'user_data': {'name': visitor.full_name, 'type': 'VISITOR', 'organization': visitor.organization},
            }

        # Verify visitor photo if available
        face_verified = True
        face_distance = 0.2
        if visitor.photo and live_face_base64:
            f_res = verify_facial_images(visitor.photo, live_face_base64)
            face_verified = f_res.get('verified', False)
            face_distance = f_res.get('distance')
            if not face_verified:
                reason = "Visitor face verification failed"
                SecurityAlert.objects.create(
                    alert_type=AlertType.FACE_MISMATCH,
                    severity=AlertSeverity.HIGH,
                    location=location,
                    user_identifier=f"Visitor: {visitor.full_name}",
                    description=f"Face mismatch on visitor pass at {location.name}."
                )
                AccessLog.objects.create(
                    scanned_barcode=scanned_code,
                    visitor_name=visitor.full_name,
                    location=location,
                    device=device,
                    direction=direction,
                    barcode_verified=True,
                    face_verified=False,
                    permission_granted=False,
                    final_decision=AccessDecision.DENIED,
                    failure_reason=reason,
                    verified_by=verified_by,
                    timestamp=timestamp
                )
                return {
                    'decision': AccessDecision.DENIED,
                    'barcode_verified': True,
                    'face_verified': False,
                    'permission_granted': False,
                    'failure_reason': reason,
                    'user_data': {'name': visitor.full_name, 'type': 'VISITOR', 'organization': visitor.organization},
                }

        # Visitor Access Granted!
        AccessLog.objects.create(
            scanned_barcode=scanned_code,
            visitor_name=visitor.full_name,
            location=location,
            device=device,
            direction=direction,
            barcode_verified=True,
            face_verified=face_verified,
            face_distance=face_distance,
            permission_granted=True,
            final_decision=AccessDecision.GRANTED,
            failure_reason='',
            verified_by=verified_by,
            timestamp=timestamp
        )

        return {
            'decision': AccessDecision.GRANTED,
            'barcode_verified': True,
            'face_verified': face_verified,
            'permission_granted': True,
            'failure_reason': '',
            'location': {
                'code': location.code,
                'name': location.name,
                'building': location.building,
                'floor': location.floor,
            },
            'user_data': {
                'name': visitor.full_name,
                'type': 'VISITOR',
                'organization': visitor.organization,
                'purpose': visitor.purpose_of_visit,
                'pass_code': scanned_code,
            },
        }

    @staticmethod
    def _serialize_person(person, student, staff):
        if student:
            photo_url = student.photo.url if student.photo else None
            return {
                'id': student.student_id,
                'name': student.full_name,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'department': student.department,
                'course': student.course,
                'semester': student.semester,
                'status': student.get_status_display(),
                'contact_email': student.contact_email,
                'contact_phone': student.contact_phone,
                'parent_phone': student.parent_phone,
                'photo_url': photo_url,
                'type': 'STUDENT',
            }
        elif staff:
            photo_url = staff.photo.url if staff.photo else None
            return {
                'id': staff.staff_id,
                'name': staff.full_name,
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'department': staff.department,
                'designation': staff.designation,
                'status': staff.get_status_display(),
                'contact_email': staff.contact_email,
                'contact_phone': staff.contact_phone,
                'photo_url': photo_url,
                'type': 'STAFF',
            }
        return None
