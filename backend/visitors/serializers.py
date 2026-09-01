import uuid
from rest_framework import serializers
from .models import Visitor, TemporaryPass
from access_control.models import AccessLocation
from access_control.serializers import AccessLocationSerializer


class VisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = [
            'id', 'full_name', 'phone', 'email', 'organization',
            'purpose_of_visit', 'person_to_meet', 'id_proof_type',
            'id_proof_number', 'photo', 'status', 'entry_time',
            'exit_time', 'created_at'
        ]


class TemporaryPassSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source='visitor.full_name', read_only=True)
    is_valid_now = serializers.SerializerMethodField()
    allowed_locations_details = AccessLocationSerializer(source='allowed_locations', many=True, read_only=True)

    class Meta:
        model = TemporaryPass
        fields = [
            'id', 'visitor', 'visitor_name', 'pass_code', 'allowed_locations',
            'allowed_locations_details', 'valid_from', 'valid_until',
            'status', 'is_valid_now', 'notes', 'created_at'
        ]
        read_only_fields = ['pass_code', 'created_at']

    def get_is_valid_now(self, obj):
        return obj.is_valid()
