from django.urls import path
from .views import LoginAPIView, LogoutAPIView, UserProfileAPIView, DeviceRegistrationAPIView, DeviceListAPIView

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='api_auth_login'),
    path('logout/', LogoutAPIView.as_view(), name='api_auth_logout'),
    path('profile/', UserProfileAPIView.as_view(), name='api_auth_profile'),
    path('devices/register/', DeviceRegistrationAPIView.as_view(), name='api_devices_register'),
    path('devices/', DeviceListAPIView.as_view(), name='api_devices_list'),
]
