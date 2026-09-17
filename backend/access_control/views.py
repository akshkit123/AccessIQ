from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import AccessLocation, AccessLog, AccessDecision
from .serializers import AccessLocationSerializer, AccessLogSerializer
from .services import DualAuthenticationService


class DualAccessVerifyAPIView(APIView):
    """
    Primary AccessIQ Dual-Authentication Endpoint.
    Combines: Barcode/QR identification + Live Face Verification + Location Permissions.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        barcode = request.data.get('barcode') or request.data.get('cardNumber')
        live_face = request.data.get('live_face') or request.data.get('live_face_image') or request.data.get('image') or request.data.get('img2')
        location_code = request.data.get('location_code') or request.data.get('location') or 'GATE-MAIN'
        device_id = request.data.get('device_id') or request.data.get('imei')
        direction = request.data.get('direction', 'ENTRY')

        demo_auto_face = request.data.get('demo_auto_face', False) or request.data.get('use_enrolled_face', False)

        if not barcode:
            return Response({
                'decision': AccessDecision.DENIED,
                'access_granted': False,
                'error': 'Barcode or Card Number is required',
                'failure_reason': 'Missing barcode/QR identifier'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if an actual live face image was provided
        has_real_face = bool(live_face and len(str(live_face).strip()) > 100 and live_face not in ['USE_ENROLLED', 'AUTO'])

        # Only use enrolled photo if NO real live face was supplied and demo mode is requested, or explicitly requested
        if not has_real_face and (demo_auto_face or live_face in ['USE_ENROLLED', 'AUTO']):
            from identity.models import BarcodeIdentity, StudentProfile, StaffProfile
            import base64, os
            clean_b = str(barcode).strip()
            barcode_id = BarcodeIdentity.objects.filter(barcode_value__iexact=clean_b, is_active=True).first()
            student = barcode_id.student if barcode_id else StudentProfile.objects.filter(student_id__iexact=clean_b).first()
            staff = barcode_id.staff if barcode_id else StaffProfile.objects.filter(staff_id__iexact=clean_b).first()
            person = student or staff
            if person and hasattr(person, 'face_profile') and person.face_profile and person.face_profile.registered_photo:
                try:
                    photo_path = person.face_profile.registered_photo.path
                    if os.path.exists(photo_path):
                        with open(photo_path, 'rb') as f:
                            live_face = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode('utf-8')
                except Exception:
                    pass

        if not live_face:
            return Response({
                'decision': AccessDecision.DENIED,
                'access_granted': False,
                'error': 'Live face image (base64) is required for dual-factor verification. Please capture from webcam or click Use Enrolled Photo.',
                'failure_reason': 'Missing live face capture'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = DualAuthenticationService.verify_access(
            barcode_value=barcode,
            live_face_image_base64=live_face,
            location_code=location_code,
            device_id=device_id,
            direction=direction,
            verified_by=request.user if request.user.is_authenticated else None
        )

        result['access_granted'] = (result.get('decision') == AccessDecision.GRANTED)
        http_status = status.HTTP_200_OK if result['access_granted'] else status.HTTP_403_FORBIDDEN
        return Response(result, status=http_status)


class AccessLocationListCreateAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        locations = AccessLocation.objects.filter(is_active=True).order_by('name')
        serializer = AccessLocationSerializer(locations, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AccessLocationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class AccessLogListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = AccessLog.objects.all().select_related('location', 'student', 'staff', 'device').order_by('-timestamp')

        location_id = request.query_params.get('location')
        decision = request.query_params.get('decision')

        if location_id:
            queryset = queryset.filter(location_id=location_id)
        if decision:
            queryset = queryset.filter(final_decision=decision.upper())

        # Limit to last 50 for quick API queries
        logs = queryset[:50]
        serializer = AccessLogSerializer(logs, many=True)
        return Response(serializer.data)
