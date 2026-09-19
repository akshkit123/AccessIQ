from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from access_control.models import AccessLocation


class AlertType(models.TextChoices):
    INVALID_BARCODE = 'INVALID_BARCODE', 'Invalid Barcode / QR'
    UNKNOWN_ID = 'UNKNOWN_ID', 'Unknown Identity'
    BLOCKED_ID = 'BLOCKED_ID', 'Blocked / Suspended ID'
    FACE_MISMATCH = 'FACE_MISMATCH', 'Face Verification Mismatch'
    UNKNOWN_FACE = 'UNKNOWN_FACE', 'Unknown Face Detected'
    EXPIRED_PASS = 'EXPIRED_PASS', 'Expired Temporary Pass'
    UNAUTHORIZED_LOCATION = 'UNAUTHORIZED_LOCATION', 'Unauthorized Location Access'
    MULTIPLE_FAILURES = 'MULTIPLE_FAILURES', 'Multiple Failed Attempts'


class AlertSeverity(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    CRITICAL = 'CRITICAL', 'Critical'


class AlertStatus(models.TextChoices):
    NEW = 'NEW', 'New / Unreviewed'
    INVESTIGATING = 'INVESTIGATING', 'Under Investigation'
    RESOLVED = 'RESOLVED', 'Resolved'
    DISMISSED = 'DISMISSED', 'Dismissed / False Positive'


class SecurityAlert(models.Model):
    """
    Automated and operator security alerts triggered by anomalies and access failures.
    """
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity = models.CharField(max_length=15, choices=AlertSeverity.choices, default=AlertSeverity.MEDIUM)
    location = models.ForeignKey(AccessLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name='alerts')
    user_identifier = models.CharField(max_length=120, blank=True, help_text="Scanned code or user name")
    description = models.TextField()
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.NEW)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Security Alert'
        verbose_name_plural = 'Security Alerts'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.severity}] {self.get_alert_type_display()} - {self.user_identifier or 'Unknown'} ({self.status})"


class AuditAction(models.TextChoices):
    CREATE = 'CREATE', 'Created'
    UPDATE = 'UPDATE', 'Updated'
    DELETE = 'DELETE', 'Deleted'
    LOGIN = 'LOGIN', 'User Login'
    APPROVE = 'APPROVE', 'Approved'
    REVOKE = 'REVOKE', 'Revoked'
    ENROLL_FACE = 'ENROLL_FACE', 'Face Biometrics Enrolled'
    OVERRIDE = 'OVERRIDE', 'Security Override'


class AuditLog(models.Model):
    """
    Administrative and security audit trail.
    """
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_actions')
    action = models.CharField(max_length=20, choices=AuditAction.choices)
    entity_type = models.CharField(max_length=80, help_text="e.g. StudentProfile, Location, TemporaryPass")
    entity_id = models.CharField(max_length=80, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        user_name = self.user.username if self.user else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_name} -> {self.action} on {self.entity_type} ({self.entity_id})"


class IssueType(models.TextChoices):
    BARCODE_SCAN = 'BARCODE_SCAN', 'Barcode / QR Not Scanning'
    ID_DAMAGED = 'ID_DAMAGED', 'ID Card Damaged / Defaced'
    FACE_VERIFY = 'FACE_VERIFY', 'Face Verification Problem'
    CAMERA_DEVICE = 'CAMERA_DEVICE', 'Camera / Device / Hardware Issue'
    VISITOR_PASS = 'VISITOR_PASS', 'Visitor Pass Problem'
    SECURITY_CONCERN = 'SECURITY_CONCERN', 'Security Concern'
    OTHER = 'OTHER', 'Other Problem'


class IssueStatus(models.TextChoices):
    OPEN = 'OPEN', 'Open / Submitted'
    INVESTIGATING = 'INVESTIGATING', 'Under Investigation'
    RESOLVED = 'RESOLVED', 'Resolved'


class IssueReport(models.Model):
    """
    Operational problems reported by Security Staff / Bouncers to administrators.
    """
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_issues')
    location = models.ForeignKey(AccessLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name='reported_issues')
    issue_type = models.CharField(max_length=30, choices=IssueType.choices, default=IssueType.OTHER)
    description = models.TextField(help_text="Detailed description of the issue")
    status = models.CharField(max_length=20, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_issues')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Issue Report'
        verbose_name_plural = 'Issue Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.get_issue_type_display()} by {self.reporter.username} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class SecurityStaffProfile(models.Model):
    """
    Operational profile for Security Staff / Bouncers stationed at College Main Gate.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_profile')
    badge_number = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g. SEC-104")
    primary_location = models.ForeignKey(AccessLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name='primary_security_staff')
    is_on_duty = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Security Staff Profile'
        verbose_name_plural = 'Security Staff Profiles'

    def __str__(self):
        loc = self.primary_location.code if self.primary_location else 'College Main Gate'
        return f"{self.user.get_full_name() or self.user.username} [Badge: {self.badge_number}] - {loc}"
