from django.urls import path
from .bouncer_api import (
    BouncerScanIDAPIView,
    BouncerVerifyAccessAPIView,
    BouncerVisitorRegisterAPIView,
    BouncerActiveVisitorsAPIView,
    BouncerVisitorCheckoutAPIView,
    BouncerAlertsAPIView,
    BouncerAlertAcknowledgeAPIView,
    BouncerIssueReportAPIView,
    BouncerMyActivityAPIView,
    BouncerStatsAPIView,
)

urlpatterns = [
    path('scan-id/', BouncerScanIDAPIView.as_view(), name='api_bouncer_scan_id'),
    path('verify-access/', BouncerVerifyAccessAPIView.as_view(), name='api_bouncer_verify_access'),
    path('visitors/register/', BouncerVisitorRegisterAPIView.as_view(), name='api_bouncer_visitor_register'),
    path('visitors/active/', BouncerActiveVisitorsAPIView.as_view(), name='api_bouncer_visitors_active'),
    path('visitors/<int:pk>/checkout/', BouncerVisitorCheckoutAPIView.as_view(), name='api_bouncer_visitor_checkout_pk'),
    path('visitors/checkout/', BouncerVisitorCheckoutAPIView.as_view(), name='api_bouncer_visitor_checkout'),
    path('alerts/', BouncerAlertsAPIView.as_view(), name='api_bouncer_alerts'),
    path('alerts/<int:pk>/acknowledge/', BouncerAlertAcknowledgeAPIView.as_view(), name='api_bouncer_alert_ack'),
    path('issues/', BouncerIssueReportAPIView.as_view(), name='api_bouncer_issues'),
    path('my-activity/', BouncerMyActivityAPIView.as_view(), name='api_bouncer_my_activity'),
    path('stats/', BouncerStatsAPIView.as_view(), name='api_bouncer_stats'),
]
