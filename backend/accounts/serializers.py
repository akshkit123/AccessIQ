from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, AuthorizedDevice


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone', 'department', 'avatar', 'is_active', 'created_at']


class AuthorizedDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedDevice
        fields = ['id', 'device_id', 'device_name', 'os_name', 'os_version', 'is_active', 'last_active_at', 'registered_at']
        read_only_fields = ['pin', 'registered_at', 'last_active_at']


class DeviceRegistrationRequestSerializer(serializers.Serializer):
    # Support both new REST format and legacy mobile app format
    Username = serializers.CharField(required=False, default='ScannerUser')
    Password = serializers.CharField(required=False, default='')
    IdentificationNo = serializers.CharField(required=False)
    device_id = serializers.CharField(required=False)
    PhoneName = serializers.CharField(required=False, default='Android Handheld')
    device_name = serializers.CharField(required=False)
    OS = serializers.CharField(required=False, default='Android')
    Verson = serializers.CharField(required=False, default='1.0')
