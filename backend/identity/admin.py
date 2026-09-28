from django.contrib import admin
from .models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'department', 'course', 'semester', 'status', 'contact_phone']
    list_filter = ['status', 'department', 'course', 'semester']
    search_fields = ['student_id', 'first_name', 'last_name', 'contact_email', 'contact_phone']


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ['staff_id', 'full_name', 'department', 'designation', 'status', 'contact_phone']
    list_filter = ['status', 'department']
    search_fields = ['staff_id', 'first_name', 'last_name', 'contact_email']


@admin.register(BarcodeIdentity)
class BarcodeIdentityAdmin(admin.ModelAdmin):
    list_display = ['barcode_value', 'code_type', 'identity_type', 'is_active', 'issued_at']
    list_filter = ['code_type', 'identity_type', 'is_active']
    search_fields = ['barcode_value', 'student__student_id', 'staff__staff_id']


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'enrollment_status', 'sample_count', 'enrolled_at', 'updated_at']
    list_filter = ['enrollment_status']
