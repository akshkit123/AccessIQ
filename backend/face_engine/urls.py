from django.urls import path
from .views import FaceVerifyAPIView

urlpatterns = [
    path('verify/', FaceVerifyAPIView.as_view(), name='api_face_verify'),
]
