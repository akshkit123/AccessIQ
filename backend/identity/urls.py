from django.urls import path
from .views import (
    BarcodeVerifyAPIView,
    FaceEnrollAPIView,
    StudentListAPIView,
    StaffListAPIView,
    StudentEnrollAPIView,
    ParseIdCardAPIView
)

urlpatterns = [
    path('verify/', BarcodeVerifyAPIView.as_view(), name='api_barcode_verify'),
    path('barcode/verify/', BarcodeVerifyAPIView.as_view(), name='api_barcode_verify_nested'),
    path('face/enroll/', FaceEnrollAPIView.as_view(), name='api_face_enroll'),
    path('parse-id-card/', ParseIdCardAPIView.as_view(), name='api_parse_id_card'),
    path('students/', StudentListAPIView.as_view(), name='api_students_list'),
    path('students/enroll/', StudentEnrollAPIView.as_view(), name='api_student_enroll'),
    path('enroll/', StudentEnrollAPIView.as_view(), name='api_enroll_alias'),
    path('staff/', StaffListAPIView.as_view(), name='api_staff_list'),
]
