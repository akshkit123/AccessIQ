from django.test import TestCase, Client
from django.urls import reverse
import json
import base64
import numpy as np
import cv2

from accounts.models import AuthorizedDevice
from identity.models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile
from access_control.models import AccessLocation, AccessLog, AccessDecision
from security.models import SecurityAlert


def make_dummy_face_b64(color=(120, 180, 220)):
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:] = color
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')


class AccessIQIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Location
        self.location = AccessLocation.objects.create(
            name='College Main Gate',
            code='GATE-MAIN',
            security_level='STANDARD',
            is_active=True
        )

        # Create Student
        self.student = StudentProfile.objects.create(
            student_id='MITWPU20261234',
            first_name='Hetvi',
            last_name='Patel',
            department='Computer Engineering',
            status='ACTIVE'
        )

        # Create Barcode
        self.barcode = BarcodeIdentity.objects.create(
            barcode_value='MITWPU20261234',
            student=self.student,
            is_active=True
        )

        # Create Face Profile
        self.dummy_face_b64 = make_dummy_face_b64()
        from django.core.files.base import ContentFile
        img_bytes = base64.b64decode(self.dummy_face_b64)
        self.face_profile = FaceProfile.objects.create(
            student=self.student,
            enrollment_status='ENROLLED'
        )
        self.face_profile.registered_photo.save('ref.jpg', ContentFile(img_bytes), save=True)

    def test_device_registration_endpoint(self):
        # Legacy format
        resp = self.client.post('/DeviceRegestration', data=json.dumps({
            'Username': 'CardTest',
            'IdentificationNo': 'TEST-DEV-777',
            'PhoneName': 'Samsung Galaxy S22',
            'OS': 'Android',
            'Verson': '14.0'
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data['MessageStatus'])
        self.assertTrue('MessageCode' in data)

        device = AuthorizedDevice.objects.get(device_id='TEST-DEV-777')
        self.assertEqual(device.device_name, 'Samsung Galaxy S22')

    def test_barcode_lookup_legacy_and_rest(self):
        # REST Endpoint
        resp_rest = self.client.post('/api/barcode/verify/', data=json.dumps({
            'barcode': 'MITWPU20261234'
        }), content_type='application/json')
        self.assertEqual(resp_rest.status_code, 200)
        self.assertEqual(resp_rest.json()['StudentName'], 'Hetvi Patel')

        # Legacy Endpoint
        resp_legacy = self.client.get('/CardVerify?sIdentificationNo=TEST-DEV-777&sPinNo=1234&lCardNo=MITWPU20261234')
        self.assertEqual(resp_legacy.status_code, 200)
        self.assertTrue(resp_legacy.json()['MessageStatus'])
        self.assertEqual(resp_legacy.json()['StudentName'], 'Hetvi Patel')

    def test_dual_authentication_granted(self):
        # Present barcode + face matching reference at College Main Gate
        resp = self.client.post('/api/access/verify/', data=json.dumps({
            'barcode': 'MITWPU20261234',
            'live_face': self.dummy_face_b64,
            'location_code': 'GATE-MAIN',
            'direction': 'ENTRY'
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['decision'], 'GRANTED')
        self.assertTrue(data['access_granted'])
        self.assertTrue(data['barcode_verified'])
        self.assertTrue(data['face_verified'])
        self.assertTrue(data['permission_granted'])

        # Check access log recorded
        log = AccessLog.objects.latest('timestamp')
        self.assertEqual(log.final_decision, 'GRANTED')
        self.assertEqual(log.student, self.student)

    def test_dual_authentication_suspended_student_denied(self):
        # Present barcode + face, but student account is suspended
        self.student.status = 'SUSPENDED'
        self.student.save()

        resp = self.client.post('/api/access/verify/', data=json.dumps({
            'barcode': 'MITWPU20261234',
            'live_face': self.dummy_face_b64,
            'location_code': 'GATE-MAIN',
            'direction': 'ENTRY'
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertEqual(data['decision'], 'DENIED')
        self.assertFalse(data['access_granted'])
        self.assertTrue(data['barcode_verified'])
        self.assertFalse(data['permission_granted'])

        # Check Security Alert generated
        alert = SecurityAlert.objects.filter(location=self.location).first()
        self.assertIsNotNone(alert)

    def test_dual_authentication_invalid_barcode_denied(self):
        resp = self.client.post('/api/access/verify/', data=json.dumps({
            'barcode': 'FAKE-BARCODE-999',
            'live_face': self.dummy_face_b64,
            'location_code': 'GATE-MAIN',
        }), content_type='application/json')

        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertEqual(data['decision'], 'DENIED')
        self.assertFalse(data['barcode_verified'])

    def test_report_downloads(self):
        # CSV
        resp_csv = self.client.get('/api/reports/access/csv/')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv['Content-Type'], 'text/csv')

        # Excel
        resp_xlsx = self.client.get('/api/reports/access/excel/')
        self.assertEqual(resp_xlsx.status_code, 200)
        self.assertEqual(resp_xlsx['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # PDF
        resp_pdf = self.client.get('/api/reports/access/pdf/')
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf['Content-Type'], 'application/pdf')
