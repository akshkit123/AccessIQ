from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Legacy views for backward-compatibility
from face_engine.views import FaceVerifyAPIView
from identity.views import LegacyCardVerifyAPIView, BarcodeVerifyAPIView, FaceEnrollAPIView
from accounts.views import DeviceRegistrationAPIView

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Web Dashboard (Bootstrap 5 + Chart.js + Security Command Center)
    path('', include('dashboard.urls')),

    # REST APIs
    path('api/auth/', include('accounts.urls')),
    path('api/identity/', include('identity.urls')),
    path('api/barcode/verify/', BarcodeVerifyAPIView.as_view(), name='api_barcode_verify_direct'),
    path('api/barcode/', include('identity.urls')),
    path('api/face/', include('face_engine.urls')),
    path('api/face/enroll/', FaceEnrollAPIView.as_view(), name='api_face_enroll_direct'),
    path('api/access/', include('access_control.urls')),
    path('api/visitors/', include('visitors.urls')),
    path('api/temporary-passes/', include('visitors.urls')),
    path('api/security/', include('security.urls')),
    path('api/bouncer/', include('security.bouncer_urls')),
    path('api/reports/', include('reports.urls')),
    path('reports/', include('reports.urls')),

    # ========================================================
    # LEGACY BACKWARD-COMPATIBILITY ROUTES
    # Seamless drop-in compatibility for existing React Native code
    # ========================================================
    path('verify', FaceVerifyAPIView.as_view(), name='legacy_verify'),
    path('verify/', FaceVerifyAPIView.as_view(), name='legacy_verify_slash'),
    path('CardVerify', LegacyCardVerifyAPIView.as_view(), name='legacy_card_verify'),
    path('CardVerify/', LegacyCardVerifyAPIView.as_view(), name='legacy_card_verify_slash'),
    path('DeviceRegestration', DeviceRegistrationAPIView.as_view(), name='legacy_device_regestration'),
    path('DeviceRegestration/', DeviceRegistrationAPIView.as_view(), name='legacy_device_regestration_slash'),
    path('DeviceRegistration', DeviceRegistrationAPIView.as_view(), name='legacy_device_registration'),
    path('DeviceRegistration/', DeviceRegistrationAPIView.as_view(), name='legacy_device_registration_slash'),

    # Matching legacy baseUrl paths: /api1/api/ForDevice/...
    path('api1/api/ForDevice/DeviceRegestration', DeviceRegistrationAPIView.as_view()),
    path('api1/api/ForDevice/CardVerify', LegacyCardVerifyAPIView.as_view()),
    path('api/ForDevice/DeviceRegestration', DeviceRegistrationAPIView.as_view()),
    path('api/ForDevice/CardVerify', LegacyCardVerifyAPIView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
