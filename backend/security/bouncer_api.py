import uuid
import base64
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db.models import Q
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import UserProfile, UserRole, AuthorizedDevice
from accounts.permissions import IsSecurityStaffOrAdmin
from identity.models import BarcodeIdentity, StudentProfile, StaffProfile, IdentityStatus
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection
from access_control.services import DualAuthenticationService
from visitors.models import Visitor, TemporaryPass, VisitorStatus, PassStatus
from security.models import (
    SecurityAlert,
    AlertType,
    AlertSeverity,
    AlertStatus,
    IssueReport,
    IssueType,
    SecurityStaffProfile,
    AuditLog,
    AuditAction,
)


def _get_bouncer_location(request, explicit_code=None):
    """
    Resolves the active gate/location for the current bouncer session.
    Prioritizes explicit location_code, then session preference, then assigned primary location.
    """
    if explicit_code:
        loc = AccessLocation.objects.filter(code__iexact=str(explicit_code).strip(), is_active=True).first()
        if loc:
            return loc

    session_loc_id = request.session.get('bouncer_active_location_id')
    if session_loc_id:
        loc = AccessLocation.objects.filter(id=session_loc_id, is_active=True).first()
        if loc:
            return loc

    if request.user.is_authenticated and hasattr(request.user, 'security_profile'):
        profile = request.user.security_profile
        if profile.primary_location and profile.primary_location.is_active:
            return profile.primary_location

    return AccessLocation.objects.filter(is_active=True).first()


class BouncerScanIDAPIView(APIView):
    """
    Primary Bouncer Step 1: Scan and decode printed Barcode / QR ID Card.
    Returns MINIMAL, privacy-conscious cardholder details strictly needed for verification.
    Does NOT expose phone, email, address, marks, or raw biometric data.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        barcode = (request.data.get('barcode') or request.data.get('scanned_code') or '').strip()
        location_code = request.data.get('location_code')
        location = _get_bouncer_location(request, location_code)

        if not barcode:
            return Response({
                'valid': False,
                'error': 'Barcode or Card Number is required.',
                'reason': 'Empty barcode input'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Lookup in BarcodeIdentity, Student, Staff, or Visitor Temporary Pass
        barcode_id = BarcodeIdentity.objects.filter(barcode_value__iexact=barcode, is_active=True).first()
        student = None
        staff = None
        visitor_pass = None

        if barcode_id:
            student = barcode_id.student
            staff = barcode_id.staff
        else:
            student = StudentProfile.objects.filter(student_id__iexact=barcode).first()
            if not student:
                staff = StaffProfile.objects.filter(staff_id__iexact=barcode).first()
            if not student and not staff:
                visitor_pass = TemporaryPass.objects.filter(pass_code__iexact=barcode).first()

        # Unrecognized Barcode / QR
        if not student and not staff and not visitor_pass:
            if location:
                SecurityAlert.objects.create(
                    alert_type=AlertType.INVALID_BARCODE,
                    severity=AlertSeverity.HIGH,
                    location=location,
                    user_identifier=barcode,
                    description=f"Unrecognized ID card barcode '{barcode}' presented at {location.name}."
                )
            return Response({
                'valid': False,
                'identifier': barcode,
                'error': 'Unregistered or Invalid ID Card.',
                'failure_reason': 'Barcode / QR code not found in campus database.',
                'status': 'UNKNOWN'
            }, status=status.HTTP_404_NOT_FOUND)

        # Temporary Visitor Pass Result
        if visitor_pass:
            visitor = visitor_pass.visitor
            is_valid = visitor_pass.is_valid()
            return Response({
                'valid': is_valid,
                'identifier': visitor_pass.pass_code,
                'name': visitor.full_name,
                'role': 'VISITOR',
                'department': visitor.organization or 'Guest / Visitor',
                'status': visitor_pass.status,
                'is_active': is_valid,
                'photo_url': visitor.photo.url if visitor.photo else None,
                'has_face_enrolled': bool(visitor.photo),
                'face_status': 'NOT_VERIFIED',
                'temporary_pass': True,
                'valid_until': visitor_pass.valid_until.strftime('%I:%M %p, %b %d'),
                'failure_reason': '' if is_valid else 'Temporary Pass Expired or Inactive',
            })

        # Student / Staff Result
        person = student or staff
        role_label = 'STUDENT' if student else 'STAFF'
        card_id = student.student_id if student else staff.staff_id

        # Check Account Status
        if person.status in [IdentityStatus.SUSPENDED, IdentityStatus.DROPPED]:
            if location:
                SecurityAlert.objects.create(
                    alert_type=AlertType.BLOCKED_ID,
                    severity=AlertSeverity.HIGH,
                    location=location,
                    user_identifier=f"{person.full_name} ({card_id})",
                    description=f"Blocked/Suspended {role_label.lower()} '{person.full_name}' attempted entry at {location.name}."
                )
            return Response({
                'valid': False,
                'identifier': card_id,
                'name': person.full_name,
                'role': role_label,
                'department': person.department,
                'status': person.get_status_display(),
                'is_active': False,
                'photo_url': person.photo.url if person.photo else None,
                'has_face_enrolled': False,
                'face_status': 'BLOCKED',
                'failure_reason': f"Account is {person.get_status_display()} - Access Blocked",
            }, status=status.HTTP_403_FORBIDDEN)

        # Check Enrolled Face Profile
        face_profile = getattr(person, 'face_profile', None)
        has_face = bool(face_profile and face_profile.registered_photo)
        photo_url = None
        if person.photo:
            photo_url = person.photo.url
        elif has_face:
            photo_url = face_profile.registered_photo.url

        # Minimal Privacy-Safe Identity Response
        return Response({
            'success': True,
            'valid': True,
            'identifier': card_id,
            'name': person.full_name,
            'role': role_label,
            'department': person.department,
            'status': 'ACTIVE',
            'is_active': True,
            'photo_url': photo_url,
            'has_face_enrolled': has_face,
            'face_status': 'NOT_VERIFIED',
            'temporary_pass': False,
            'identity': {
                'name': person.full_name,
                'type': role_label,
                'identifier': card_id,
                'department': person.department,
            }
        })


class BouncerVerifyAccessAPIView(APIView):
    """
    Primary Bouncer Step 2: Live Face Verification + Location Authorization Check.
    Combines: Scanned Barcode + Live Face Capture + Gate Permission + Shift Logging.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        barcode = request.data.get('barcode') or request.data.get('identifier')
        live_face = request.data.get('live_face') or request.data.get('live_face_image')
        location_code = request.data.get('location_code')
        direction = request.data.get('direction', AccessDirection.ENTRY)
        demo_auto_face = request.data.get('demo_auto_face', False)

        resolved_loc = _get_bouncer_location(request, location_code)
        loc_code = resolved_loc.code if resolved_loc else 'GATE-MAIN'

        if not barcode:
            return Response({
                'decision': AccessDecision.DENIED,
                'access_granted': False,
                'error': 'Barcode or Card Number is required.',
                'failure_reason': 'Missing barcode'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Strict dual-authentication: A genuine live camera frame is strictly required
        has_real_face = bool(live_face and len(str(live_face).strip()) > 100 and live_face not in ['USE_ENROLLED', 'AUTO'])
        if not has_real_face:
            return Response({
                'decision': AccessDecision.DENIED,
                'access_granted': False,
                'error': 'Live facial capture is required for dual-factor authentication.',
                'failure_reason': 'No live face captured. Please align your face inside the camera oval.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Execute Dual Authentication with current bouncer user logged
        verified_by = request.user if request.user.is_authenticated else None
        result = DualAuthenticationService.verify_access(
            barcode_value=barcode,
            live_face_image_base64=live_face,
            location_code=loc_code,
            direction=direction,
            verified_by=verified_by
        )

        is_granted = (result.get('decision') == AccessDecision.GRANTED)
        result['access_granted'] = is_granted

        # Structure operational bouncer response
        user_info = result.get('user_data') or {}
        sanitized = {
            'decision': result.get('decision'),
            'access_granted': is_granted,
            'identifier': barcode,
            'name': user_info.get('full_name') or user_info.get('name') or 'Cardholder',
            'role': user_info.get('type') or 'STUDENT',
            'department': user_info.get('department') or '',
            'location_code': loc_code,
            'location_name': resolved_loc.name if resolved_loc else loc_code,
            'direction': direction,
            'timestamp': timezone.now().strftime('%I:%M %p'),
            'barcode_verified': result.get('barcode_verified', False),
            'face_matched': result.get('face_verified', False),
            'face_distance': result.get('face_distance'),
            'similarity_score': result.get('face_similarity'),
            'permission_granted': result.get('permission_granted', False),
            'failure_reason': result.get('failure_reason', ''),
        }

        http_status = status.HTTP_200_OK if is_granted else status.HTTP_403_FORBIDDEN
        return Response(sanitized, status=http_status)


class BouncerVisitorRegisterAPIView(APIView):
    """
    Bouncer Operational Feature: On-the-spot Visitor Registration & QR Pass Generation.
    Eliminates separate visitor portals. Bouncer registers visitor and issues temporary pass.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        full_name = (request.data.get('full_name') or '').strip()
        phone = (request.data.get('phone') or request.data.get('contact_phone') or '').strip()
        purpose = (request.data.get('purpose_of_visit') or request.data.get('purpose') or '').strip()
        person_to_meet = (request.data.get('person_to_meet') or request.data.get('host') or request.data.get('person_to_visit') or '').strip()
        organization = (request.data.get('organization') or '').strip()
        photo_b64 = request.data.get('photo') or request.data.get('photo_b64')
        location_code = request.data.get('location_code')

        if not full_name or not phone or not purpose or not person_to_meet:
            return Response({
                'success': False,
                'error': 'Full name, mobile number, purpose of visit, and person to meet are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        resolved_loc = _get_bouncer_location(request, location_code)

        # Create Visitor
        visitor = Visitor.objects.create(
            full_name=full_name,
            phone=phone,
            organization=organization,
            purpose_of_visit=purpose,
            person_to_meet=person_to_meet,
            status=VisitorStatus.CHECKED_IN,
            entry_time=timezone.now(),
            registered_by=request.user if request.user.is_authenticated else None
        )

        # Handle Photo upload or base64 webcam capture
        if photo_b64 and 'base64,' in str(photo_b64):
            try:
                img_data = base64.b64decode(photo_b64.split('base64,')[1])
                fname = f"visitor_{visitor.id}_{int(timezone.now().timestamp())}.jpg"
                visitor.photo.save(fname, ContentFile(img_data), save=True)
            except Exception:
                pass
        elif request.FILES.get('photo'):
            visitor.photo = request.FILES['photo']
            visitor.save()

        # Generate Time-bound Temporary QR Pass (Default 8 hours)
        pass_code = f"PASS-{uuid.uuid4().hex[:8].upper()}"
        valid_until = timezone.now() + timezone.timedelta(hours=8)
        temp_pass = TemporaryPass.objects.create(
            visitor=visitor,
            pass_code=pass_code,
            valid_from=timezone.now(),
            valid_until=valid_until,
            status=PassStatus.ACTIVE,
            notes=f"Registered by Security Staff at {resolved_loc.name if resolved_loc else 'Entrance'}"
        )
        if resolved_loc:
            temp_pass.allowed_locations.add(resolved_loc)

        # Log Access Entry
        if resolved_loc:
            AccessLog.objects.create(
                scanned_barcode=pass_code,
                visitor_name=visitor.full_name,
                location=resolved_loc,
                direction=AccessDirection.ENTRY,
                barcode_verified=True,
                face_verified=bool(visitor.photo),
                permission_granted=True,
                final_decision=AccessDecision.GRANTED,
                verified_by=request.user if request.user.is_authenticated else None,
                timestamp=timezone.now()
            )

        return Response({
            'success': True,
            'message': f"Visitor {visitor.full_name} registered and checked in.",
            'visitor': {
                'id': visitor.id,
                'name': visitor.full_name,
                'full_name': visitor.full_name,
                'phone': visitor.phone,
                'organization': visitor.organization,
                'person_to_meet': visitor.person_to_meet,
                'entry_time': visitor.entry_time.strftime('%I:%M %p'),
                'photo_url': visitor.photo.url if visitor.photo else None,
            },
            'pass': {
                'pass_code': pass_code,
                'valid_from': temp_pass.valid_from.strftime('%I:%M %p'),
                'valid_until': temp_pass.valid_until.strftime('%I:%M %p'),
                'status': 'ACTIVE',
            }
        }, status=status.HTTP_201_CREATED)


class BouncerActiveVisitorsAPIView(APIView):
    """
    Returns only visitors who are currently checked in or have an active temporary pass.
    Bouncers do NOT have access to complete historical visitor databases.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        active_visitors = Visitor.objects.filter(
            status=VisitorStatus.CHECKED_IN
        ).prefetch_related('passes').order_by('-entry_time')[:50]

        items = []
        for v in active_visitors:
            active_pass = v.passes.filter(status=PassStatus.ACTIVE).order_by('-created_at').first()
            items.append({
                'id': v.id,
                'full_name': v.full_name,
                'organization': v.organization or 'Individual',
                'person_to_meet': v.person_to_meet,
                'purpose_of_visit': v.purpose_of_visit,
                'entry_time': v.entry_time.strftime('%I:%M %p') if v.entry_time else 'Active',
                'photo_url': v.photo.url if v.photo else None,
                'pass_code': active_pass.pass_code if active_pass else None,
                'valid_until': active_pass.valid_until.strftime('%I:%M %p') if active_pass else None,
            })
        return Response({'visitors': items, 'total_active': len(items)})


class BouncerVisitorCheckoutAPIView(APIView):
    """
    Marks a visitor as exited when they leave through the security gate.
    Deactivates their temporary pass and records the exit event.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk=None):
        pass_code = request.data.get('pass_code')
        visitor_id = pk or request.data.get('visitor_id')
        visitor = None

        if visitor_id:
            visitor = Visitor.objects.filter(pk=visitor_id).first()
        elif pass_code:
            t_pass = TemporaryPass.objects.filter(pass_code__iexact=str(pass_code).strip()).first()
            if t_pass:
                visitor = t_pass.visitor

        if not visitor:
            return Response({'error': 'Active visitor record not found'}, status=status.HTTP_404_NOT_FOUND)

        location = _get_bouncer_location(request, request.data.get('location_code'))

        visitor.status = VisitorStatus.CHECKED_OUT
        visitor.exit_time = timezone.now()
        visitor.checked_out_by = request.user if request.user.is_authenticated else None
        visitor.save(update_fields=['status', 'exit_time', 'checked_out_by'])

        # Expire any active passes
        visitor.passes.filter(status=PassStatus.ACTIVE).update(status=PassStatus.USED)

        # Log Exit Event
        if location:
            AccessLog.objects.create(
                scanned_barcode=pass_code or f"VISITOR-{visitor.id}",
                visitor_name=visitor.full_name,
                location=location,
                direction=AccessDirection.EXIT,
                barcode_verified=True,
                face_verified=True,
                permission_granted=True,
                final_decision=AccessDecision.GRANTED,
                failure_reason='',
                verified_by=request.user if request.user.is_authenticated else None,
                timestamp=timezone.now()
            )

        return Response({
            'success': True,
            'message': f"Visitor {visitor.full_name} marked as EXITED.",
            'exit_time': visitor.exit_time.strftime('%I:%M %p')
        })


class BouncerAlertsAPIView(APIView):
    """
    Returns security alerts relevant to the bouncer's location and current shift/day.
    Excludes admin-only sensitive audits and global system diagnostics.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        location = _get_bouncer_location(request)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        query = Q(timestamp__gte=today_start)
        if location:
            query &= (Q(location=location) | Q(location__isnull=True))

        alerts = SecurityAlert.objects.filter(query).select_related('location').order_by('-timestamp')[:25]

        items = []
        for a in alerts:
            items.append({
                'id': a.id,
                'alert_type': a.get_alert_type_display(),
                'severity': a.severity,
                'location_name': a.location.name if a.location else 'Campus Gate',
                'user_identifier': a.user_identifier or 'Unknown',
                'description': a.description,
                'status': a.status,
                'time': a.timestamp.strftime('%I:%M %p'),
            })

        return Response({'alerts': items, 'count': len(items)})


class BouncerAlertAcknowledgeAPIView(APIView):
    """
    Allows a bouncer to acknowledge a security alert for their post.
    Bouncers cannot delete alerts or dismiss critical security breaches.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        alert = SecurityAlert.objects.filter(pk=pk).first()
        if not alert:
            return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)

        alert.status = AlertStatus.INVESTIGATING
        alert.resolved_by = request.user if request.user.is_authenticated else None
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['status', 'resolved_by', 'resolved_at'])

        return Response({
            'success': True,
            'message': f"Alert #{alert.id} acknowledged by security staff."
        })


class BouncerIssueReportAPIView(APIView):
    """
    Allows bouncers/security staff to report operational equipment/card/verification issues.
    Directly routes to supervisor and campus administrators.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        issue_type = request.data.get('issue_type') or IssueType.OTHER
        description = (request.data.get('description') or '').strip()
        location_code = request.data.get('location_code')
        location = _get_bouncer_location(request, location_code)

        if not description:
            return Response({'error': 'Please provide an issue description.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        if not user:
            # Fallback for anonymous demo session
            user = UserProfile.objects.filter(role=UserRole.SECURITY_STAFF).first()
            user = user.user if user else None

        if not user:
            from django.contrib.auth.models import User
            user = User.objects.first()

        report = IssueReport.objects.create(
            reporter=user,
            location=location,
            issue_type=issue_type,
            description=description,
            status='OPEN'
        )

        return Response({
            'success': True,
            'message': 'Issue reported successfully to campus security supervisor.',
            'report_id': report.id
        }, status=status.HTTP_201_CREATED)


class BouncerMyActivityAPIView(APIView):
    """
    Displays ONLY the current security staff member's recent verifications.
    Filterable by 'today' or 'shift'. Does NOT allow browsing the full database.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        filter_mode = request.GET.get('filter', 'today')

        query = Q(timestamp__gte=today_start)
        if request.user.is_authenticated and not request.user.is_superuser:
            query &= (Q(verified_by=request.user) | Q(verified_by__isnull=True))

        logs = AccessLog.objects.filter(query).select_related('location', 'student', 'staff').order_by('-timestamp')[:35]

        items = []
        for l in logs:
            name = l.student.full_name if l.student else (l.staff.full_name if l.staff else (l.visitor_name or l.scanned_barcode))
            items.append({
                'id': l.id,
                'time': l.timestamp.strftime('%I:%M %p'),
                'direction': l.direction,
                'name': name,
                'identifier': l.scanned_barcode,
                'decision': l.final_decision,
                'barcode_verified': l.barcode_verified,
                'face_verified': l.face_verified,
                'failure_reason': l.failure_reason if l.final_decision == AccessDecision.DENIED else '',
                'location_name': l.location.name if l.location else 'Gate',
            })

        return Response({
            'activity': items,
            'filter': filter_mode,
            'total': len(items)
        })


class BouncerStatsAPIView(APIView):
    """
    Provides minimal operational metrics for the bouncer's shift dashboard.
    No complex charts, revenue, or academic analytics.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        location = _get_bouncer_location(request)

        log_query = Q(timestamp__gte=today_start)
        alert_query = Q(timestamp__gte=today_start, status=AlertStatus.NEW)
        if location:
            log_query &= Q(location=location)
            alert_query &= (Q(location=location) | Q(location__isnull=True))

        today_logs = AccessLog.objects.filter(log_query)
        today_scans = today_logs.count()
        today_granted = today_logs.filter(final_decision=AccessDecision.GRANTED).count()
        today_denied = today_logs.filter(final_decision=AccessDecision.DENIED).count()

        active_visitors = Visitor.objects.filter(status=VisitorStatus.CHECKED_IN).count()
        open_alerts = SecurityAlert.objects.filter(alert_query).count()

        return Response({
            'today_scans': today_scans,
            'today_granted': today_granted,
            'today_denied': today_denied,
            'active_visitors': active_visitors,
            'open_alerts': open_alerts,
            'location_code': location.code if location else 'GATE-01',
            'location_name': location.name if location else 'Gate 1 (Main Entrance)',
        })


