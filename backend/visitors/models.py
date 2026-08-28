import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from access_control.models import AccessLocation


class VisitorStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    CHECKED_IN = 'CHECKED_IN', 'Checked In'
    CHECKED_OUT = 'CHECKED_OUT', 'Checked Out'
    REJECTED = 'REJECTED', 'Rejected'


class Visitor(models.Model):
    """
    Campus Visitor Registration and Management.
    """
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    organization = models.CharField(max_length=120, blank=True, help_text="Company or Institution")
    purpose_of_visit = models.TextField(help_text="Reason for campus visit")
    person_to_meet = models.CharField(max_length=120, help_text="Faculty or Staff member to meet")
    id_proof_type = models.CharField(max_length=50, default='National ID / Aadhaar')
    id_proof_number = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to='visitor_photos/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=VisitorStatus.choices, default=VisitorStatus.PENDING)
    entry_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    registered_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='registered_visitors')
    checked_out_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='checked_out_visitors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Visitor'
        verbose_name_plural = 'Visitors'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.organization or 'Individual'}) - {self.get_status_display()}"


class PassStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRED = 'EXPIRED', 'Expired'
    REVOKED = 'REVOKED', 'Revoked'
    USED = 'USED', 'Used'


class TemporaryPass(models.Model):
    """
    Time-bound QR/Barcode pass issued to visitors or guest researchers.
    """
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='passes')
    pass_code = models.CharField(max_length=60, unique=True, db_index=True, help_text="Scannable QR/Barcode string")
    allowed_locations = models.ManyToManyField(AccessLocation, related_name='temporary_passes', blank=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    status = models.CharField(max_length=20, choices=PassStatus.choices, default=PassStatus.ACTIVE)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Temporary Access Pass'
        verbose_name_plural = 'Temporary Access Passes'
        ordering = ['-created_at']

    def __str__(self):
        return f"Pass {self.pass_code} for {self.visitor.full_name} [{self.status}]"

    def is_valid(self):
        now = timezone.now()
        if self.status != PassStatus.ACTIVE:
            return False
        return self.valid_from <= now <= self.valid_until

    def check_and_update_status(self):
        if self.status == PassStatus.ACTIVE and timezone.now() > self.valid_until:
            self.status = PassStatus.EXPIRED
            self.save(update_fields=['status'])
            return False
        return self.is_valid()
