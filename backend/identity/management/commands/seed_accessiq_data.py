import os
import shutil
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.core.files import File

from accounts.models import UserProfile, UserRole, AuthorizedDevice
from identity.models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile, IdentityStatus
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection, SecurityLevel
from visitors.models import Visitor, TemporaryPass, VisitorStatus, PassStatus
from security.models import SecurityAlert, AlertType, AlertSeverity, AlertStatus, AuditLog, AuditAction


class Command(BaseCommand):
    help = "Seeds initial campus identities, locations, permissions, equipment, and access logs."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Seeding AccessIQ database..."))

        # 1. Superuser / Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@accessiq.campus.edu',
                'first_name': 'Campus',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('admin123')
        admin_user.save()
        UserProfile.objects.get_or_create(user=admin_user, defaults={'role': UserRole.ADMIN, 'department': 'Campus Security Office'})
        self.stdout.write(self.style.SUCCESS("Admin user ready: admin / admin123"))

        # 2. Campus Access Locations - Dedicated College Main Gate
        loc_gate, _ = AccessLocation.objects.get_or_create(
            code='GATE-MAIN',
            defaults={
                'name': 'College Main Gate',
                'building': 'Campus Perimeter',
                'floor': 'Ground Floor',
                'description': 'Main College Campus Entrance & Exit Gate',
                'security_level': SecurityLevel.STANDARD,
                'is_active': True,
            }
        )
        loc_gate.name = 'College Main Gate'
        loc_gate.is_active = True
        loc_gate.save()

        # Deactivate any specific classroom or lab checkpoints so system is focused exclusively on College Gate Entry
        AccessLocation.objects.exclude(code='GATE-MAIN').update(is_active=False)
        self.stdout.write(self.style.SUCCESS("Initialized College Main Gate (classroom and lab checkpoints deactivated)."))

        # 3. Reference Image setup
        ref_src = os.path.join(settings.BASE_DIR.parent, 'assets', 'reference.jpg')
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'face_profiles'), exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'identity_photos'), exist_ok=True)
        ref_dest = os.path.join(settings.MEDIA_ROOT, 'face_profiles', 'hetvi_enrolled.jpg')
        has_ref = False
        if os.path.exists(ref_src):
            shutil.copyfile(ref_src, ref_dest)
            has_ref = True

        # 4. Students
        # Student 1: Hetvi Patel (Example from requirements: Barcode=Hetvi, Face=Hetvi, Perm=Yes)
        hetvi_user, _ = User.objects.get_or_create(username='hetvi', defaults={'first_name': 'Hetvi', 'last_name': 'Patel', 'email': 'hetvi.patel@campus.edu'})
        hetvi_student, _ = StudentProfile.objects.get_or_create(
            student_id='MITWPU20261234',
            defaults={
                'user': hetvi_user,
                'first_name': 'Hetvi',
                'last_name': 'Patel',
                'department': 'Computer Engineering',
                'course': 'B.Tech',
                'semester': 3,
                'contact_email': 'hetvi.patel@campus.edu',
                'contact_phone': '9876543210',
                'parent_phone': '9876500000',
                'status': IdentityStatus.ACTIVE,
            }
        )
        BarcodeIdentity.objects.get_or_create(
            barcode_value='MITWPU20261234',
            defaults={'student': hetvi_student, 'code_type': 'BARCODE', 'identity_type': 'STUDENT'}
        )
        if has_ref:
            hetvi_student.photo.name = 'face_profiles/hetvi_enrolled.jpg'
            hetvi_student.save()
            fp, _ = FaceProfile.objects.get_or_create(student=hetvi_student)
            fp.registered_photo.name = 'face_profiles/hetvi_enrolled.jpg'
            fp.enrollment_status = 'ENROLLED'
            fp.sample_count = 1
            fp.save()

        # Student 2: Aarav Sharma
        aarav_student, _ = StudentProfile.objects.get_or_create(
            student_id='MITWPU20261235',
            defaults={
                'first_name': 'Aarav',
                'last_name': 'Sharma',
                'department': 'AI & Data Science',
                'course': 'B.Tech',
                'semester': 3,
                'contact_email': 'aarav.sharma@campus.edu',
                'contact_phone': '9822012345',
                'status': IdentityStatus.ACTIVE,
            }
        )
        BarcodeIdentity.objects.get_or_create(
            barcode_value='MITWPU20261235',
            defaults={'student': aarav_student, 'code_type': 'BARCODE', 'identity_type': 'STUDENT'}
        )

        # Student 3: Ananya Deshmukh (Suspended / Blocked for testing)
        ananya_student, _ = StudentProfile.objects.get_or_create(
            student_id='MITWPU20261236',
            defaults={
                'first_name': 'Ananya',
                'last_name': 'Deshmukh',
                'department': 'Electronics & Communication',
                'course': 'B.Tech',
                'semester': 5,
                'contact_email': 'ananya.d@campus.edu',
                'status': IdentityStatus.SUSPENDED,
            }
        )
        BarcodeIdentity.objects.get_or_create(
            barcode_value='MITWPU20261236',
            defaults={'student': ananya_student, 'code_type': 'BARCODE', 'identity_type': 'STUDENT'}
        )

        # 5. Faculty / Staff
        rajesh_staff, _ = StaffProfile.objects.get_or_create(
            staff_id='STAFF-202601',
            defaults={
                'first_name': 'Dr. Rajesh',
                'last_name': 'Kulkarni',
                'department': 'Department of AI & Data Science',
                'designation': 'Professor & Lab Director',
                'contact_email': 'rajesh.kulkarni@campus.edu',
                'status': IdentityStatus.ACTIVE,
            }
        )
        BarcodeIdentity.objects.get_or_create(
            barcode_value='STAFF-202601',
            defaults={'staff': rajesh_staff, 'code_type': 'QR', 'identity_type': 'STAFF'}
        )
        self.stdout.write(self.style.SUCCESS("Created Students and Staff."))

        # 6. Authorized Devices
        AuthorizedDevice.objects.get_or_create(
            device_id='DEMO-IMEI-123456',
            defaults={
                'device_name': 'Security Handheld Scanner 01',
                'os_name': 'Android 14',
                'os_version': '14.0',
                'pin': '9421',
                'is_active': True,
                'last_active_at': timezone.now(),
            }
        )
        AuthorizedDevice.objects.get_or_create(
            device_id='TABLET-AIML-LAB',
            defaults={
                'device_name': 'AI Lab Entrance Tablet',
                'os_name': 'Android',
                'os_version': '13.0',
                'pin': '4582',
                'is_active': True,
                'last_active_at': timezone.now(),
            }
        )

        # 9. Visitors & Temporary Passes
        vis1, _ = Visitor.objects.get_or_create(
            full_name='Vikram Singhania',
            defaults={
                'phone': '9811223344',
                'email': 'vikram.s@techinnovate.com',
                'organization': 'TechInnovate Labs',
                'purpose_of_visit': 'Guest Lecture & AI Industry Research Review',
                'person_to_meet': 'Dr. Rajesh Kulkarni',
                'status': VisitorStatus.CHECKED_IN,
                'entry_time': timezone.now() - timedelta(hours=2),
            }
        )
        pass1, _ = TemporaryPass.objects.get_or_create(
            pass_code='PASS-QR-98214',
            defaults={
                'visitor': vis1,
                'valid_from': timezone.now() - timedelta(hours=2),
                'valid_until': timezone.now() + timedelta(hours=6),
                'status': PassStatus.ACTIVE,
                'notes': 'Authorized for College Main Gate perimeter entry',
            }
        )
        pass1.allowed_locations.add(loc_gate)

        # 10. Sample Access Logs and Alerts for Dashboard
        now = timezone.now()
        # Log 1: Hetvi at College Main Gate - GRANTED
        AccessLog.objects.get_or_create(
            scanned_barcode='MITWPU20261234',
            location=loc_gate,
            timestamp=now - timedelta(minutes=15),
            defaults={
                'student': hetvi_student,
                'barcode_verified': True,
                'face_verified': True,
                'face_distance': 0.18,
                'face_similarity': 0.86,
                'permission_granted': True,
                'final_decision': AccessDecision.GRANTED,
                'direction': AccessDirection.ENTRY,
            }
        )
        # Log 2: Suspended ID at College Main Gate - DENIED
        AccessLog.objects.get_or_create(
            scanned_barcode='MITWPU20261236',
            location=loc_gate,
            timestamp=now - timedelta(minutes=45),
            defaults={
                'student': ananya_student,
                'barcode_verified': True,
                'face_verified': False,
                'permission_granted': False,
                'final_decision': AccessDecision.DENIED,
                'failure_reason': 'Identity is SUSPENDED: Entry denied at College Main Gate',
                'direction': AccessDirection.ENTRY,
            }
        )
        # Log 3: Dr. Rajesh at College Main Gate - GRANTED
        AccessLog.objects.get_or_create(
            scanned_barcode='STAFF-202601',
            location=loc_gate,
            timestamp=now - timedelta(hours=1, minutes=10),
            defaults={
                'staff': rajesh_staff,
                'barcode_verified': True,
                'face_verified': True,
                'face_distance': 0.15,
                'permission_granted': True,
                'final_decision': AccessDecision.GRANTED,
                'direction': AccessDirection.ENTRY,
            }
        )
        # Log 4: Unknown Barcode at College Main Gate - DENIED
        AccessLog.objects.get_or_create(
            scanned_barcode='INVALID-UNKNOWN-999',
            location=loc_gate,
            timestamp=now - timedelta(hours=2),
            defaults={
                'barcode_verified': False,
                'face_verified': False,
                'permission_granted': False,
                'final_decision': AccessDecision.DENIED,
                'failure_reason': 'Invalid or unregistered Barcode / QR ID',
                'direction': AccessDirection.ENTRY,
            }
        )

        # Sample Security Alert
        SecurityAlert.objects.get_or_create(
            alert_type=AlertType.INVALID_BARCODE,
            location=loc_aiml,
            user_identifier='INVALID-UNKNOWN-999',
            defaults={
                'severity': AlertSeverity.HIGH,
                'description': "Attempted entry at AI & Deep Learning Research Lab using unregistered barcode 'INVALID-UNKNOWN-999'.",
                'status': AlertStatus.NEW,
            }
        )
        SecurityAlert.objects.get_or_create(
            alert_type=AlertType.UNAUTHORIZED_LOCATION,
            location=loc_srv,
            user_identifier='Hetvi Patel (MITWPU20261234)',
            defaults={
                'severity': AlertSeverity.MEDIUM,
                'description': "Access denied to Data Center & Server Room: student role lacks high-security authorization.",
                'status': AlertStatus.NEW,
            }
        )

        AuditLog.objects.create(
            user=admin_user,
            action=AuditAction.CREATE,
            entity_type='DatabaseSeed',
            entity_id='AccessIQ-Init',
            details='Initial AccessIQ campus dataset seeded successfully.',
        )

        self.stdout.write(self.style.SUCCESS("AccessIQ database seeding completed successfully!"))
