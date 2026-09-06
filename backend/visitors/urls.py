from django.urls import path
from .views import VisitorListCreateAPIView, VisitorApproveAPIView, TemporaryPassListCreateAPIView

urlpatterns = [
    path('', VisitorListCreateAPIView.as_view(), name='api_visitors_list_create'),
    path('<int:pk>/approve/', VisitorApproveAPIView.as_view(), name='api_visitors_approve'),
    path('temporary-passes/', TemporaryPassListCreateAPIView.as_view(), name='api_temporary_passes_list_create'),
]
