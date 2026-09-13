from rest_framework import serializers
from .models import AccessLocation, AccessLog


class AccessLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessLocation
        fields = ['id', 'name', 'code', 'building', 'floor', 'description', 'security_level', 'is_active', 'created_at']


class AccessLogSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = AccessLog
        fields = [
            'id', 'scanned_barcode', 'user_name', 'user_type',
            'location', 'location_name', 'location_code', 'direction',
            'barcode_verified', 'face_verified', 'face_distance', 'face_similarity',
            'permission_granted', 'final_decision', 'failure_reason',
            'timestamp'
        ]

    def get_user_name(self, obj):
        if obj.student:
            return obj.student.full_name
        if obj.staff:
            return obj.staff.full_name
        return obj.visitor_name or "Unknown Presenter"

    def get_user_type(self, obj):
        if obj.student:
            return 'Student'
        if obj.staff:
            return 'Faculty/Staff'
        if obj.visitor_name:
            return 'Visitor'
        return 'Unknown'
