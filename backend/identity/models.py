from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class IdentityStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active / Study Continue'
    ALUMNI = 'ALUMNI', 'Alumni / Completed'
    DROPPED = 'DROPPED', 'Dropped / Inactive'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique Student ID (e.g. MITWPU20261234)")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=120, default='Computer Engineering')
    course = models.CharField(max_length=120, default='B.Tech')
    semester = models.IntegerField(default=3)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True, help_text="Parent contact number")
    status = models.CharField(max_length=20, choices=IdentityStatus.choices, default=IdentityStatus.ACTIVE)
    photo = models.ImageField(upload_to='identity_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['student_id']

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_profile')
    staff_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Faculty / Staff ID (e.g. STAFF-2026)")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=120, default='School of Computer Science')
    designation = models.CharField(max_length=100, default='Assistant Professor')
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=IdentityStatus.choices, default=IdentityStatus.ACTIVE)
    photo = models.ImageField(upload_to='identity_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering = ['staff_id']

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.designation}, {self.staff_id})"


class CodeType(models.TextChoices):
    BARCODE = 'BARCODE', 'Barcode (Printed 1D)'
    QR = 'QR', 'QR Code (2D Matrix)'
    RFID_NFC = 'RFID_NFC', 'RFID / NFC (Future Scope)'


class IdentityType(models.TextChoices):
    STUDENT = 'STUDENT', 'Student'
    STAFF = 'STAFF', 'Faculty / Staff'
    VISITOR = 'VISITOR', 'Visitor / Temporary'


class BarcodeIdentity(models.Model):
    """
    Maps physical printed Barcode / QR values to registered users.
    Replaces mandatory RFID hardware with ubiquitous camera-based scanning.
    """
    barcode_value = models.CharField(max_length=100, unique=True, db_index=True, help_text="Scanned code value (e.g. MITWPU20261234)")
    code_type = models.CharField(max_length=20, choices=CodeType.choices, default=CodeType.BARCODE)
    identity_type = models.CharField(max_length=20, choices=IdentityType.choices, default=IdentityType.STUDENT)
    student = models.ForeignKey(StudentProfile, null=True, blank=True, on_delete=models.CASCADE, related_name='barcodes')
    staff = models.ForeignKey(StaffProfile, null=True, blank=True, on_delete=models.CASCADE, related_name='barcodes')
    is_active = models.BooleanField(default=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Barcode Identity'
        verbose_name_plural = 'Barcode Identities'

    def __str__(self):
        owner = self.student.full_name if self.student else (self.staff.full_name if self.staff else 'Unassigned')
        return f"[{self.code_type}] {self.barcode_value} -> {owner} ({'Active' if self.is_active else 'Inactive'})"

    def get_associated_person(self):
        if self.student:
            return self.student
        elif self.staff:
            return self.staff
        return None


class EnrollmentStatus(models.TextChoices):
    ENROLLED = 'ENROLLED', 'Enrolled & Verified'
    PENDING = 'PENDING', 'Pending Enrollment'
    REJECTED = 'REJECTED', 'Quality Rejected'


class FaceProfile(models.Model):
    """
    Stores enrolled facial data and reference templates securely.
    Supports dual-factor comparison against live camera captures.
    """
    student = models.OneToOneField(StudentProfile, null=True, blank=True, on_delete=models.CASCADE, related_name='face_profile')
    staff = models.OneToOneField(StaffProfile, null=True, blank=True, on_delete=models.CASCADE, related_name='face_profile')
    registered_photo = models.ImageField(upload_to='face_profiles/', null=True, blank=True)
    embedding_vector = models.JSONField(null=True, blank=True, help_text="Calculated facial embedding array")
    enrollment_status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ENROLLED)
    sample_count = models.PositiveIntegerField(default=1)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Face Profile'
        verbose_name_plural = 'Face Profiles'

    def __str__(self):
        owner = self.student.full_name if self.student else (self.staff.full_name if self.staff else 'Unknown')
        return f"Face Profile: {owner} [{self.enrollment_status}]"
