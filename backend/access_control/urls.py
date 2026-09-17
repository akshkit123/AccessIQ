from django.urls import path
from .views import (
    DualAccessVerifyAPIView,
    AccessLocationListCreateAPIView,
    AccessLogListAPIView,
)

urlpatterns = [
    path('verify/', DualAccessVerifyAPIView.as_view(), name='api_access_verify'),
    path('locations/', AccessLocationListCreateAPIView.as_view(), name='api_access_locations'),
    path('logs/', AccessLogListAPIView.as_view(), name='api_access_logs'),
]
