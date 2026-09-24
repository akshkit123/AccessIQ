from rest_framework import serializers
from .models import SecurityAlert, AuditLog, IssueReport


class SecurityAlertSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)

    class Meta:
        model = SecurityAlert
        fields = [
            'id', 'alert_type', 'alert_type_display', 'severity',
            'location', 'location_name', 'user_identifier',
            'description', 'status', 'resolved_by', 'resolved_at',
            'timestamp'
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'username', 'action', 'entity_type', 'entity_id', 'details', 'ip_address', 'timestamp']


class IssueReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.username', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)

    class Meta:
        model = IssueReport
        fields = [
            'id', 'reporter', 'reporter_name', 'location', 'location_name',
            'issue_type', 'issue_type_display', 'description', 'status',
            'created_at', 'resolved_by', 'resolved_at'
        ]
