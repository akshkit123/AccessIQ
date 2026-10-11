from django.contrib import admin
from .models import UserProfile, AuthorizedDevice


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'phone', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone', 'department']


@admin.register(AuthorizedDevice)
class AuthorizedDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'device_id', 'pin', 'os_name', 'is_active', 'last_active_at', 'registered_at']
    list_filter = ['is_active', 'os_name']
    search_fields = ['device_name', 'device_id', 'pin']
