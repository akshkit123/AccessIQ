import base64
from rest_framework import serializers
from .models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    face_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'student_id', 'first_name', 'last_name', 'full_name',
            'department', 'course', 'semester', 'contact_email',
            'contact_phone', 'parent_phone', 'status', 'photo',
            'face_enrolled', 'created_at'
        ]

    def get_face_enrolled(self, obj):
        return hasattr(obj, 'face_profile') and bool(obj.face_profile.registered_photo)


class StaffProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    face_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = [
            'id', 'staff_id', 'first_name', 'last_name', 'full_name',
            'department', 'designation', 'contact_email', 'contact_phone',
            'status', 'photo', 'face_enrolled', 'created_at'
        ]

    def get_face_enrolled(self, obj):
        return hasattr(obj, 'face_profile') and bool(obj.face_profile.registered_photo)


class BarcodeIdentitySerializer(serializers.ModelSerializer):
    associated_name = serializers.SerializerMethodField()

    class Meta:
        model = BarcodeIdentity
        fields = ['id', 'barcode_value', 'code_type', 'identity_type', 'is_active', 'associated_name', 'issued_at']

    def get_associated_name(self, obj):
        person = obj.get_associated_person()
        return person.full_name if person else None


class FaceProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceProfile
        fields = ['id', 'enrollment_status', 'sample_count', 'enrolled_at', 'updated_at']
