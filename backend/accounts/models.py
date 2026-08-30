from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    SECURITY_STAFF = 'security_staff', 'Security Staff'
    FACULTY_STAFF = 'faculty_staff', 'Faculty / Staff'
    STUDENT = 'student', 'Student'
    VISITOR = 'visitor', 'Visitor'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserRole.ADMIN if instance.is_superuser else UserRole.STUDENT
        UserProfile.objects.get_or_create(user=instance, defaults={'role': role})
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class AuthorizedDevice(models.Model):
    """
    Authorized Device Management (evolved from legacy DeviceRegestration).
    Tracks handheld terminals, security verification phones, and gate readers.
    """
    device_id = models.CharField(max_length=120, unique=True, db_index=True, help_text="IMEI or Device Unique ID")
    device_name = models.CharField(max_length=100, default='Handheld Scanner')
    os_name = models.CharField(max_length=50, blank=True, default='Android')
    os_version = models.CharField(max_length=50, blank=True, default='1.0')
    pin = models.CharField(max_length=64, help_text="Device security PIN for terminal verification")
    assigned_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='authorized_devices')
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Authorized Device'
        verbose_name_plural = 'Authorized Devices'
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.device_name} ({self.device_id}) - {'Active' if self.is_active else 'Deactivated'}"

    def update_last_active(self):
        self.last_active_at = timezone.now()
        self.save(update_fields=['last_active_at'])
