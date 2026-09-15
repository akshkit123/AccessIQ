from django.contrib import admin
from .models import AccessLocation, AccessLog


@admin.register(AccessLocation)
class AccessLocationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'building', 'floor', 'security_level', 'is_active', 'created_at']
    list_filter = ['security_level', 'is_active', 'building']
    search_fields = ['code', 'name', 'building', 'description']


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'scanned_barcode', '__str__', 'location', 'direction', 'face_verified', 'final_decision']
    list_filter = ['final_decision', 'direction', 'barcode_verified', 'face_verified', 'location', 'timestamp']
    search_fields = ['scanned_barcode', 'student__first_name', 'student__student_id', 'staff__first_name', 'visitor_name', 'failure_reason']
    date_hierarchy = 'timestamp'
