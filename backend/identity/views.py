import base64
import os
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile, IdentityStatus
from .serializers import StudentProfileSerializer, StaffProfileSerializer
from accounts.models import AuthorizedDevice
from security.models import AuditLog, AuditAction, SecurityAlert, AlertType, AlertSeverity


def get_base64_from_field(image_field):
    if not image_field:
        return ""
    try:
        if os.path.exists(image_field.path):
            with open(image_field.path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        pass
    return ""


def build_identity_response(person, student, staff, barcode_val):
    photo_b64 = ""
    photo_url = ""
    face_enrolled = False

    face_prof = getattr(person, 'face_profile', None)
    if face_prof and face_prof.registered_photo:
        photo_b64 = get_base64_from_field(face_prof.registered_photo)
        photo_url = face_prof.registered_photo.url
        face_enrolled = True
    elif person.photo:
        photo_b64 = get_base64_from_field(person.photo)
        photo_url = person.photo.url

    if student:
        return {
            'MessageStatus': True,
            'success': True,
            'id': student.student_id,
            'name': student.full_name,
            'StudentName': student.full_name,
            'EnrollmentNo': student.student_id,
            'CurrentStatus': student.get_status_display(),
            'Status': student.get_status_display(),
            'ParentMobileNo': student.parent_phone or student.contact_phone,
            'department': student.department,
            'course': student.course,
            'semester': student.semester,
            'contact_email': student.contact_email,
            'contact_phone': student.contact_phone,
            'barcode': barcode_val,
            'type': 'STUDENT',
            'Photo': photo_b64,
            'photo_url': photo_url,
            'face_enrolled': face_enrolled,
        }
    elif staff:
        return {
            'MessageStatus': True,
            'success': True,
            'id': staff.staff_id,
            'name': staff.full_name,
            'StudentName': staff.full_name,
            'EnrollmentNo': staff.staff_id,
            'CurrentStatus': staff.get_status_display(),
            'Status': staff.get_status_display(),
            'ParentMobileNo': staff.contact_phone,
            'department': staff.department,
            'designation': staff.designation,
            'contact_email': staff.contact_email,
            'contact_phone': staff.contact_phone,
            'barcode': barcode_val,
            'type': 'STAFF',
            'Photo': photo_b64,
            'photo_url': photo_url,
            'face_enrolled': face_enrolled,
        }


class BarcodeVerifyAPIView(APIView):
    """
    Primary AccessIQ Barcode/QR verification endpoint.
    Retrieves registered identity record associated with scanned barcode.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        barcode = request.data.get('barcode') or request.data.get('cardNumber') or request.data.get('lCardNo')
        return self._process_barcode(barcode, request)

    def get(self, request):
        barcode = request.query_params.get('barcode') or request.query_params.get('cardNumber') or request.query_params.get('lCardNo')
        return self._process_barcode(barcode, request)

    def _process_barcode(self, barcode, request):
        if not barcode:
            return Response({
                'MessageStatus': False,
                'success': False,
                'Message': 'Barcode / QR code parameter is required',
                'error': 'Missing barcode parameter'
            }, status=status.HTTP_400_BAD_REQUEST)

        barcode = str(barcode).strip()

        # Lookup in BarcodeIdentity
        barcode_obj = BarcodeIdentity.objects.filter(barcode_value__iexact=barcode, is_active=True).first()

        # Fallback check direct student_id match if barcode equals student_id
        if not barcode_obj:
            student_direct = StudentProfile.objects.filter(student_id__iexact=barcode).first()
            if student_direct:
                barcode_obj, _ = BarcodeIdentity.objects.get_or_create(
                    barcode_value=barcode,
                    defaults={'student': student_direct, 'identity_type': 'STUDENT'}
                )

        if not barcode_obj:
            # Check staff direct
            staff_direct = StaffProfile.objects.filter(staff_id__iexact=barcode).first()
            if staff_direct:
                barcode_obj, _ = BarcodeIdentity.objects.get_or_create(
                    barcode_value=barcode,
                    defaults={'staff': staff_direct, 'identity_type': 'STAFF'}
                )

        if not barcode_obj:
            return Response({
                'MessageStatus': False,
                'success': False,
                'Message': f"Unknown or unregistered ID: '{barcode}'",
                'error': 'Identity not found'
            }, status=status.HTTP_404_NOT_FOUND)

        person = barcode_obj.get_associated_person()
        if not person:
            return Response({
                'MessageStatus': False,
                'success': False,
                'Message': f"Barcode '{barcode}' is not assigned to any student or staff member",
                'error': 'No profile attached'
            }, status=status.HTTP_404_NOT_FOUND)

        resp_data = build_identity_response(person, barcode_obj.student, barcode_obj.staff, barcode)
        return Response(resp_data, status=status.HTTP_200_OK)


class LegacyCardVerifyAPIView(APIView):
    """
    Direct backward-compatibility endpoint for legacy mobile app:
    GET /CardVerify?sIdentificationNo=...&sPinNo=...&lCardNo=...
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        imei = request.query_params.get('sIdentificationNo')
        pin = request.query_params.get('sPinNo')
        card_no = request.query_params.get('lCardNo') or request.query_params.get('cardNumber')

        if not card_no:
            return Response({
                'MessageStatus': False,
                'Message': 'Card number (lCardNo) is required',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check device registration if imei and pin are provided
        if imei and pin:
            device = AuthorizedDevice.objects.filter(device_id=imei.strip(), is_active=True).first()
            if device:
                device.update_last_active()

        # Delegate to BarcodeVerify logic
        barcode_obj = BarcodeIdentity.objects.filter(barcode_value__iexact=card_no.strip(), is_active=True).first()
        if not barcode_obj:
            # Fallback direct lookup
            student = StudentProfile.objects.filter(student_id__iexact=card_no.strip()).first()
            if student:
                barcode_obj, _ = BarcodeIdentity.objects.get_or_create(barcode_value=card_no.strip(), defaults={'student': student})

        if not barcode_obj or not barcode_obj.get_associated_person():
            return Response({
                'MessageStatus': False,
                'Message': f"No student/identity found for card number {card_no}",
            }, status=status.HTTP_200_OK)  # Legacy returns 200 with MessageStatus: False

        person = barcode_obj.get_associated_person()
        return Response(build_identity_response(person, barcode_obj.student, barcode_obj.staff, card_no))


class FaceEnrollAPIView(APIView):
    """
    Face Enrollment Endpoint: Registers live camera capture as reference biometric template.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identity_id = request.data.get('identity_id') or request.data.get('student_id')
        photo_b64 = request.data.get('photo') or request.data.get('image')

        if not identity_id or not photo_b64:
            return Response({
                'error': 'identity_id and photo (base64) are required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        student = StudentProfile.objects.filter(student_id=identity_id).first()
        staff = StaffProfile.objects.filter(staff_id=identity_id).first() if not student else None

        if not student and not staff:
            return Response({'error': f"User with ID '{identity_id}' not found", 'success': False}, status=status.HTTP_404_NOT_FOUND)

        # Decode base64 and save as file
        if 'base64,' in photo_b64:
            photo_b64 = photo_b64.split('base64,')[1]
        
        try:
            image_data = base64.b64decode(photo_b64)
            file_name = f"face_{identity_id}_{int(timezone.now().timestamp())}.jpg"
            content_file = ContentFile(image_data, name=file_name)

            if student:
                face_profile, _ = FaceProfile.objects.get_or_create(student=student)
                face_profile.registered_photo.save(file_name, content_file, save=True)
                face_profile.sample_count += 1
                face_profile.enrollment_status = 'ENROLLED'
                face_profile.save()
            elif staff:
                face_profile, _ = FaceProfile.objects.get_or_create(staff=staff)
                face_profile.registered_photo.save(file_name, content_file, save=True)
                face_profile.sample_count += 1
                face_profile.enrollment_status = 'ENROLLED'
                face_profile.save()

            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=AuditAction.ENROLL_FACE,
                entity_type='FaceProfile',
                entity_id=identity_id,
                details=f"Facial biometrics enrolled for {identity_id}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            return Response({
                'success': True,
                'message': f"Face biometrics successfully enrolled for {identity_id}",
                'enrollment_status': 'ENROLLED',
            })

        except Exception as e:
            return Response({'error': f"Failed to save facial data: {str(e)}", 'success': False}, status=status.HTTP_400_BAD_REQUEST)


class StudentListAPIView(APIView):
    def get(self, request):
        students = StudentProfile.objects.all().order_by('student_id')
        serializer = StudentProfileSerializer(students, many=True)
        return Response(serializer.data)


class StaffListAPIView(APIView):
    def get(self, request):
        staff = StaffProfile.objects.all().order_by('staff_id')
        serializer = StaffProfileSerializer(staff, many=True)
        return Response(serializer.data)


class StudentEnrollAPIView(APIView):
    """
    Direct Student Enrollment API:
    Supports instant enrollment from phone camera or desktop.
    Accepts:
      - student_id / id_number / id
      - first_name, last_name, name
      - department, course, semester
      - barcode (scanned from phone camera)
      - photo (base64 string or file upload)
      - contact_phone
    Creates:
      1. StudentProfile
      2. BarcodeIdentity linked to card
      3. FaceProfile for biometric face matching
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        student_id = (data.get('student_id') or data.get('id_number') or data.get('id') or '').strip()
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        full_name = (data.get('name') or data.get('full_name') or '').strip()

        if full_name and not first_name:
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

        department = (data.get('department') or 'Computer Engineering').strip()
        course = (data.get('course') or 'B.Tech').strip()
        try:
            semester = int(data.get('semester') or 3)
        except (ValueError, TypeError):
            semester = 3

        barcode_val = (data.get('barcode') or data.get('barcode_value') or student_id).strip()
        contact_phone = (data.get('contact_phone') or data.get('phone') or '').strip()

        if not student_id:
            return Response({
                'success': False,
                'error': 'Student ID / Barcode number is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not first_name:
            first_name = f"Student {student_id[-4:]}"

        student, created = StudentProfile.objects.get_or_create(
            student_id=student_id,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'department': department,
                'course': course,
                'semester': semester,
                'contact_phone': contact_phone,
                'status': IdentityStatus.ACTIVE,
            }
        )

        if not created:
            student.first_name = first_name or student.first_name
            student.last_name = last_name or student.last_name
            student.department = department or student.department
            student.course = course or student.course
            student.semester = semester or student.semester
            if contact_phone:
                student.contact_phone = contact_phone
            student.save()

        # Handle Photo (File upload or Base64 data)
        photo_file = request.FILES.get('photo')
        photo_b64 = data.get('photo_b64') or (data.get('photo') if isinstance(data.get('photo'), str) else None)
        saved_file = None

        if photo_file:
            student.photo = photo_file
            student.save()
            saved_file = student.photo
        elif photo_b64 and 'base64' in photo_b64:
            try:
                raw_b64 = photo_b64.split('base64,')[1] if 'base64,' in photo_b64 else photo_b64
                img_data = base64.b64decode(raw_b64)
                fname = f"student_{student_id}_{int(timezone.now().timestamp())}.jpg"
                student.photo.save(fname, ContentFile(img_data), save=True)
                saved_file = student.photo
            except Exception:
                pass

        # Link Barcode
        barcode_obj, _ = BarcodeIdentity.objects.get_or_create(
            barcode_value=barcode_val,
            defaults={'student': student, 'identity_type': 'STUDENT', 'is_active': True}
        )
        if barcode_obj.student != student:
            barcode_obj.student = student
            barcode_obj.save()

        # Link Face Biometrics Profile
        if saved_file:
            fp, _ = FaceProfile.objects.get_or_create(student=student)
            fp.registered_photo = saved_file
            fp.enrollment_status = 'ENROLLED'
            fp.sample_count += 1
            fp.save()

        # Face profile completed

        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=AuditAction.CREATE,
            entity_type='StudentProfile',
            entity_id=student.student_id,
            details=f"Student {student.full_name} enrolled via Barcode scan ({barcode_val})",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'success': True,
            'message': f"Student '{student.full_name}' ({student.student_id}) enrolled successfully!",
            'student_id': student.student_id,
            'barcode': barcode_val,
            'name': student.full_name,
            'department': student.department,
            'course': student.course,
            'semester': student.semester,
            'photo_url': student.photo.url if student.photo else '',
        }, status=status.HTTP_201_CREATED)


class ParseIdCardAPIView(APIView):
    """
    AI-Powered ID Card Parser Endpoint:
    Accepts an ID card photo (via multipart file or base64) or barcode value.
    Extracts barcode, student ID, name, course, department, contact phone,
    and crops student face photo automatically.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .id_card_parser import parse_id_card_data

        card_file = request.FILES.get('card_image') or request.FILES.get('photo')
        image_b64 = request.data.get('image_b64') or request.data.get('photo_b64')
        barcode_in = request.data.get('barcode', '').strip()

        if not card_file and not image_b64 and not barcode_in:
            return Response({
                'success': False,
                'error': 'Please provide an ID card image (file or base64) or barcode value.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            input_source = card_file if card_file else image_b64
            if input_source:
                parsed = parse_id_card_data(input_source)
            else:
                # Fallback if only barcode is provided
                parsed = {
                    'success': True,
                    'student_id': barcode_in,
                    'barcode': barcode_in,
                    'first_name': '',
                    'last_name': '',
                    'full_name': '',
                    'course': 'MCA',
                    'department': 'Faculty of Engineering and Technology',
                    'semester': 3,
                    'contact_phone': '',
                    'blood_group': '',
                    'photo_b64': '',
                }

            # Check if this student or barcode is already enrolled in the DB
            sid = parsed.get('student_id') or barcode_in
            existing = StudentProfile.objects.filter(student_id=sid).first()
            if not existing and parsed.get('barcode'):
                bc_match = BarcodeIdentity.objects.filter(barcode_value=parsed.get('barcode')).first()
                if bc_match and bc_match.student:
                    existing = bc_match.student

            if existing:
                parsed['already_enrolled'] = True
                parsed['existing_name'] = existing.full_name
                # Prioritize freshly extracted card details, fallback to existing DB fields
                parsed['first_name'] = parsed.get('first_name') or existing.first_name
                parsed['last_name'] = parsed.get('last_name') or existing.last_name
                parsed['course'] = parsed.get('course') or existing.course
                parsed['department'] = parsed.get('department') or existing.department
                parsed['contact_phone'] = parsed.get('contact_phone') or existing.contact_phone
                if existing.photo and not parsed.get('photo_b64'):
                    parsed['photo_url'] = existing.photo.url
            else:
                parsed['already_enrolled'] = False

            return Response(parsed, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Failed to parse ID card")
            return Response({
                'success': False,
                'error': f'Failed to parse ID card: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

