import random
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, AuthorizedDevice, UserRole
from .serializers import UserProfileSerializer, AuthorizedDeviceSerializer, DeviceRegistrationRequestSerializer
from security.models import AuditLog, AuditAction


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username') or request.data.get('Username')
        password = request.data.get('password') or request.data.get('Password')

        if not username or not password:
            return Response({'error': 'Username and password are required', 'MessageStatus': False}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                return Response({'error': 'Account is inactive', 'MessageStatus': False}, status=status.HTTP_403_FORBIDDEN)

            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user)

            AuditLog.objects.create(
                user=user,
                action=AuditAction.LOGIN,
                entity_type='User',
                entity_id=str(user.id),
                details=f"Successful login by {user.username} with role {profile.role}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            return Response({
                'success': True,
                'MessageStatus': True,
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.get_full_name() or user.username,
                    'role': profile.role,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
            })
        else:
            return Response({'error': 'Invalid credentials', 'MessageStatus': False, 'Message': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request)
        return Response({'success': True, 'message': 'Logged out successfully'})


class UserProfileAPIView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)


class DeviceRegistrationAPIView(APIView):
    """
    Registers or authenticates a verification terminal device.
    Supports both standard REST and legacy format expected by the React Native client.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        device_id = data.get('IdentificationNo') or data.get('device_id') or data.get('imei')
        device_name = data.get('PhoneName') or data.get('device_name') or 'Handheld Scanner'
        os_name = data.get('OS') or data.get('os_name') or 'Android'
        os_version = data.get('Verson') or data.get('os_version') or '1.0'

        if not device_id:
            return Response({
                'MessageStatus': False,
                'Message': 'Device identification number (IMEI/UUID) is required',
                'error': 'device_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate or retrieve device PIN
        pin = str(random.randint(1000, 9999))
        device, created = AuthorizedDevice.objects.get_or_create(
            device_id=device_id.strip(),
            defaults={
                'device_name': device_name,
                'os_name': os_name,
                'os_version': os_version,
                'pin': pin,
                'is_active': True,
                'last_active_at': timezone.now(),
            }
        )

        if not created:
            device.device_name = device_name
            device.os_name = os_name
            device.os_version = os_version
            device.last_active_at = timezone.now()
            device.save()
            pin = device.pin

        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=AuditAction.CREATE if created else AuditAction.UPDATE,
            entity_type='AuthorizedDevice',
            entity_id=device.device_id,
            details=f"Device '{device.device_name}' ({device.device_id}) registered with PIN {pin}.",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        # Return hybrid payload satisfying both legacy and REST clients
        return Response({
            'MessageStatus': True,
            'MessageCode': pin,
            'Message': 'Device registered successfully',
            'device': {
                'id': device.id,
                'device_id': device.device_id,
                'device_name': device.device_name,
                'pin': pin,
                'is_active': device.is_active,
                'status': 'Active' if device.is_active else 'Deactivated'
            }
        }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


class DeviceListAPIView(APIView):
    def get(self, request):
        devices = AuthorizedDevice.objects.all().order_by('-last_active_at')
        serializer = AuthorizedDeviceSerializer(devices, many=True)
        return Response(serializer.data)
