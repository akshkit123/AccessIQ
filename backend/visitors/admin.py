from django.contrib import admin
from .models import Visitor, TemporaryPass


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'organization', 'person_to_meet', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['full_name', 'phone', 'organization', 'person_to_meet']


@admin.register(TemporaryPass)
class TemporaryPassAdmin(admin.ModelAdmin):
    list_display = ['pass_code', 'visitor', 'valid_from', 'valid_until', 'status']
    list_filter = ['status', 'valid_until']
    search_fields = ['pass_code', 'visitor__full_name']
