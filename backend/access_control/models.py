from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import AuthorizedDevice, UserRole
from identity.models import StudentProfile, StaffProfile


class SecurityLevel(models.TextChoices):
    STANDARD = 'STANDARD', 'Standard / General Access'
    RESTRICTED = 'RESTRICTED', 'Restricted / Department Only'
    HIGH_SECURITY = 'HIGH_SECURITY', 'High Security / Authorized Only'


class AccessLocation(models.Model):
    """
    Campus access points and secured facilities.
    """
    name = models.CharField(max_length=120, unique=True, help_text="e.g. AI/ML Research Lab")
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g. LAB-AIML")
    building = models.CharField(max_length=100, default='Main Academic Block')
    floor = models.CharField(max_length=50, default='1st Floor')
    description = models.TextField(blank=True)
    security_level = models.CharField(max_length=20, choices=SecurityLevel.choices, default=SecurityLevel.STANDARD)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Access Location'
        verbose_name_plural = 'Access Locations'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"




class AccessDecision(models.TextChoices):
    GRANTED = 'GRANTED', 'Access Granted'
    DENIED = 'DENIED', 'Access Denied'


class AccessDirection(models.TextChoices):
    ENTRY = 'ENTRY', 'Entry'
    EXIT = 'EXIT', 'Exit'


class AccessLog(models.Model):
    """
    Access event log (Audit & Security access tracking, strictly NOT attendance).
    """
    scanned_barcode = models.CharField(max_length=100, db_index=True)
    student = models.ForeignKey(StudentProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='access_logs')
    staff = models.ForeignKey(StaffProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='access_logs')
    visitor_name = models.CharField(max_length=120, blank=True)
    location = models.ForeignKey(AccessLocation, on_delete=models.CASCADE, related_name='logs')
    device = models.ForeignKey(AuthorizedDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name='access_logs')
    direction = models.CharField(max_length=10, choices=AccessDirection.choices, default=AccessDirection.ENTRY)
    barcode_verified = models.BooleanField(default=False)
    face_verified = models.BooleanField(default=False)
    face_distance = models.FloatField(null=True, blank=True)
    face_similarity = models.FloatField(null=True, blank=True)
    permission_granted = models.BooleanField(default=False)
    final_decision = models.CharField(max_length=15, choices=AccessDecision.choices, default=AccessDecision.DENIED)
    failure_reason = models.CharField(max_length=255, blank=True)
    captured_face_image = models.ImageField(upload_to='captured_faces/', null=True, blank=True)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_access_logs', help_text="Security staff / Bouncer who operated the station")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Access Log'
        verbose_name_plural = 'Access Logs'
        ordering = ['-timestamp']

    @property
    def display_user_name(self):
        if self.student:
            return self.student.full_name
        if self.staff:
            return self.staff.full_name
        if self.visitor_name:
            return self.visitor_name
        return self.scanned_barcode

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.location.code} - {self.display_user_name}: {self.final_decision}"
