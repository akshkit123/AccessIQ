import os
import sys
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.abspath('backend'))
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from accounts.models import UserProfile, UserRole
from security.models import SecurityStaffProfile, SecurityAlert, IssueReport, IssueType, IssueStatus, AuditLog
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection
from identity.models import StudentProfile, BarcodeIdentity, FaceProfile
from visitors.models import Visitor, TemporaryPass, VisitorStatus, PassStatus
import base64

def run_tests():
    print("=" * 60)
    print("ACCESSIQ COMPREHENSIVE END-TO-END VALIDATION TEST")
    print("=" * 60)

    client = Client()

    # TEST 1: Register as Bouncer / Security Staff
    print("\n[1] Testing Registration as Bouncer...")
    User.objects.filter(username__in=['test_bouncer_99', 'test_admin_99']).delete()
    
    loc = AccessLocation.objects.first()
    res = client.post('/register/', {
        'role': 'SECURITY_STAFF',
        'username': 'test_bouncer_99',
        'first_name': 'Vikram',
        'last_name': 'Rathore',
        'email': 'vikram@campus.edu',
        'badge_number': 'SEC-999',
        'location_id': loc.id if loc else '',
        'password': 'password123',
        'password_confirm': 'password123'
    }, follow=False)
    
    assert res.status_code == 302, f"Expected 302 redirect on register, got {res.status_code}"
    assert res['Location'] == '/bouncer/', f"Expected redirect to /bouncer/, got {res['Location']}"
    
    user_bouncer = User.objects.get(username='test_bouncer_99')
    assert user_bouncer.security_profile.badge_number == 'SEC-999'
    print("  -> Bouncer registered successfully and redirected to /bouncer/!")

    # TEST 2: Register as Admin
    print("\n[2] Testing Registration as Administrator...")
    client.logout()
    res = client.post('/register/', {
        'role': 'ADMIN',
        'username': 'test_admin_99',
        'first_name': 'Anita',
        'last_name': 'Desai',
        'email': 'anita@campus.edu',
        'password': 'password123',
        'password_confirm': 'password123'
    }, follow=False)

    assert res.status_code == 302, f"Expected 302 redirect, got {res.status_code}"
    assert res['Location'] == '/', f"Expected redirect to /, got {res['Location']}"
    user_admin = User.objects.get(username='test_admin_99')
    assert user_admin.is_staff is True
    print("  -> Admin registered successfully and redirected to / (Admin Dashboard)!")

    # TEST 3: Login routing (Bouncer -> /bouncer/, Admin -> /)
    print("\n[3] Testing Login Routing...")
    client.logout()
    res = client.post('/login/', {'username': 'test_bouncer_99', 'password': 'password123'}, follow=False)
    assert res['Location'] == '/bouncer/'
    print("  -> Bouncer login correctly redirects to /bouncer/!")

    client.logout()
    res = client.post('/login/', {'username': 'test_admin_99', 'password': 'password123'}, follow=False)
    assert res['Location'] == '/'
    print("  -> Admin login correctly redirects to /!")

    # TEST 4: Bouncer ID Card Scan
    print("\n[4] Testing Bouncer Scan ID API...")
    # Seed a test student with photo
    photo_path = os.path.join('backend', 'media', 'identity_photos', 'test_photo_crop.jpg')
    with open(photo_path, 'rb') as f:
        img_bytes = f.read()
    b64_img = 'data:image/jpeg;base64,' + base64.b64encode(img_bytes).decode('utf-8')

    student, _ = StudentProfile.objects.get_or_create(
        student_id='STU-TEST-001',
        defaults={'first_name': 'Aarav', 'last_name': 'Sharma', 'department': 'Computer Eng'}
    )
    student.photo = 'identity_photos/test_photo_crop.jpg'
    student.save()

    BarcodeIdentity.objects.get_or_create(
        barcode_value='CARD-TEST-001',
        defaults={'student': student, 'identity_type': 'STUDENT'}
    )
    
    # Login as bouncer
    client.login(username='test_bouncer_99', password='password123')
    res = client.post('/api/bouncer/scan-id/', {'barcode': 'CARD-TEST-001'}, content_type='application/json')
    assert res.status_code == 200, f"Scan ID failed: {res.content}"
    data = res.json()
    assert data['success'] is True
    assert data['identity']['name'] == 'Aarav Sharma'
    assert data['identity']['type'] == 'STUDENT'
    print(f"  -> Scanned CARD-TEST-001 -> Identified student: {data['identity']['name']}")

    # TEST 5: Verify Dual Verification without Permission restrictions
    print("\n[5] Testing Dual Verification Flow...")
    res = client.post('/api/bouncer/verify-access/', {
        'barcode': 'CARD-TEST-001',
        'direction': 'ENTRY',
        'live_face': b64_img,
        'location_code': loc.code if loc else 'GATE-01'
    }, content_type='application/json')
    assert res.status_code == 200, f"Verify access failed: {res.content}"
    data = res.json()
    assert data['decision'] == 'GRANTED', f"Decision should be GRANTED without permission checks, got {data['decision']}"
    print(f"  -> Dual verification decision: {data['decision']} (Entry recorded, verified by test_bouncer_99)")

    # Check AccessLog entry
    latest_log = AccessLog.objects.filter(scanned_barcode='CARD-TEST-001').first()
    assert latest_log is not None
    assert latest_log.direction == 'ENTRY'
    assert latest_log.final_decision == 'GRANTED'
    print(f"  -> AccessLog verified: Direction={latest_log.direction}, Result={latest_log.final_decision}")

    # TEST 6: Visitor Registration by Bouncer
    print("\n[6] Testing Visitor Registration & Pass Creation...")
    res = client.post('/api/bouncer/visitors/register/', {
        'full_name': 'Mr. Ramesh Gupta',
        'contact_phone': '9876543210',
        'person_to_visit': 'Dr. Kulkarni (Dean)',
        'purpose_of_visit': 'Curriculum Review Meeting',
        'organization': 'Academic Council',
        'valid_hours': 3
    }, content_type='application/json')
    assert res.status_code == 201, f"Visitor register failed: {res.content}"
    v_data = res.json()
    assert v_data['success'] is True
    visitor_id = v_data['visitor']['id']
    pass_code = v_data['pass']['pass_code']
    print(f"  -> Visitor registered: {v_data['visitor']['name']}, Pass Code: {pass_code}")

    # TEST 7: Active Visitors List
    print("\n[7] Testing Active Visitors List...")
    res = client.get('/api/bouncer/visitors/active/')
    assert res.status_code == 200
    active_visitors = res.json().get('visitors', [])
    found = any(v['id'] == visitor_id for v in active_visitors)
    assert found, "Registered visitor not in active visitors list"
    print(f"  -> Found active visitor {visitor_id} in active list (total: {len(active_visitors)})")

    # TEST 8: Visitor Checkout / Mark Exit
    print("\n[8] Testing Visitor Checkout...")
    res = client.post('/api/bouncer/visitors/checkout/', {'visitor_id': visitor_id}, content_type='application/json')
    assert res.status_code == 200
    assert res.json()['success'] is True
    v_obj = Visitor.objects.get(id=visitor_id)
    assert v_obj.status == VisitorStatus.CHECKED_OUT
    print("  -> Visitor marked as EXITED successfully!")

    # TEST 9: Bouncer Issue Reporting
    print("\n[9] Testing Bouncer Issue Reporting...")
    res = client.post('/api/bouncer/issues/', {
        'issue_type': 'BARCODE_SCAN',
        'description': 'Student ID card barcode barcode smudge causes optical reader error.',
        'location_code': loc.code if loc else 'GATE-01'
    }, content_type='application/json')
    assert res.status_code == 201
    assert res.json()['success'] is True
    print("  -> Operational issue submitted to administrators!")

    # TEST 10: Admin Reviewing Reports & Dashboards
    print("\n[10] Testing Admin Dashboard & Review...")
    client.login(username='test_admin_99', password='password123')
    res = client.get('/')
    assert res.status_code == 200
    assert 'Campus Security Command Center' in res.content.decode()
    print("  -> Admin Dashboard loaded successfully!")

    res = client.get('/alerts/')
    assert res.status_code == 200
    assert 'Reported Issues' in res.content.decode()
    print("  -> Security Alerts, Issues & Compliance page loaded successfully!")

    # TEST 11: Reports Exporting
    print("\n[11] Testing Reports CSV Exports...")
    res = client.get('/reports/access/csv/')
    assert res.status_code == 200
    assert res['Content-Type'] == 'text/csv'
    print("  -> Verification Report CSV export: OK")

    res = client.get('/reports/visitors/csv/')
    assert res.status_code == 200
    assert res['Content-Type'] == 'text/csv'
    print("  -> Visitor Report CSV export: OK")

    res = client.get('/reports/issues/csv/')
    assert res.status_code == 200
    assert res['Content-Type'] == 'text/csv'
    print("  -> Issue Report CSV export: OK")

    # TEST 12: Bouncer Dashboard Rendering
    print("\n[12] Testing Bouncer Dashboard Rendering...")
    client.login(username='test_bouncer_99', password='password123')
    res = client.get('/bouncer/')
    assert res.status_code == 200
    assert 'Security Staff Operational Portal' in res.content.decode()
    print("  -> Bouncer Dashboard rendered successfully!")

    # Clean up test accounts
    User.objects.filter(username__in=['test_bouncer_99', 'test_admin_99']).delete()

    print("\n" + "=" * 60)
    print("ALL 12 TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
