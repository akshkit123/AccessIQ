from django.contrib import admin
from .models import (
    SecurityAlert,
    AuditLog,
    IssueReport,
    SecurityStaffProfile,
)


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'alert_type', 'severity', 'location', 'user_identifier', 'status']
    list_filter = ['severity', 'status', 'alert_type', 'timestamp']
    search_fields = ['user_identifier', 'description']
    date_hierarchy = 'timestamp'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'entity_type', 'entity_id', 'ip_address']
    list_filter = ['action', 'entity_type', 'timestamp']
    search_fields = ['entity_id', 'details', 'user__username']
    date_hierarchy = 'timestamp'


@admin.register(IssueReport)
class IssueReportAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'reporter', 'location', 'issue_type', 'status']
    list_filter = ['issue_type', 'status', 'created_at']
    search_fields = ['description', 'reporter__username']


@admin.register(SecurityStaffProfile)
class SecurityStaffProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'badge_number', 'primary_location', 'is_on_duty', 'created_at']
    list_filter = ['is_on_duty', 'primary_location']
    search_fields = ['badge_number', 'user__username', 'user__first_name', 'user__last_name']

