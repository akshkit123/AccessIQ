from django.urls import path
from .views import (
    SecurityAlertListAPIView,
    SecurityAlertResolveAPIView,
    AuditLogListAPIView,
    IssueReportListAPIView,
)
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
    # General Security APIs
    path('alerts/', SecurityAlertListAPIView.as_view(), name='api_security_alerts'),
    path('alerts/<int:pk>/resolve/', SecurityAlertResolveAPIView.as_view(), name='api_security_alert_resolve'),
    path('audit-logs/', AuditLogListAPIView.as_view(), name='api_audit_logs'),
    path('issues/', IssueReportListAPIView.as_view(), name='api_issues'),

    # ========================================================
    # DEDICATED BOUNCER / SECURITY STAFF OPERATIONAL APIS
    # ========================================================
    path('bouncer/scan-id/', BouncerScanIDAPIView.as_view(), name='api_bouncer_scan_id'),
    path('bouncer/verify-access/', BouncerVerifyAccessAPIView.as_view(), name='api_bouncer_verify_access'),
    path('bouncer/visitors/register/', BouncerVisitorRegisterAPIView.as_view(), name='api_bouncer_visitor_register'),
    path('bouncer/visitors/active/', BouncerActiveVisitorsAPIView.as_view(), name='api_bouncer_visitors_active'),
    path('bouncer/visitors/<int:pk>/checkout/', BouncerVisitorCheckoutAPIView.as_view(), name='api_bouncer_visitor_checkout_pk'),
    path('bouncer/visitors/checkout/', BouncerVisitorCheckoutAPIView.as_view(), name='api_bouncer_visitor_checkout'),
    path('bouncer/alerts/', BouncerAlertsAPIView.as_view(), name='api_bouncer_alerts'),
    path('bouncer/alerts/<int:pk>/acknowledge/', BouncerAlertAcknowledgeAPIView.as_view(), name='api_bouncer_alert_ack'),
    path('bouncer/issues/', BouncerIssueReportAPIView.as_view(), name='api_bouncer_issues'),
    path('bouncer/my-activity/', BouncerMyActivityAPIView.as_view(), name='api_bouncer_my_activity'),
    path('bouncer/stats/', BouncerStatsAPIView.as_view(), name='api_bouncer_stats'),
]

