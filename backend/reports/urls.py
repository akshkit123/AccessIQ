from django.urls import path
from .views import (
    AccessLogsExportCSVView,
    AccessLogsExportExcelView,
    AccessLogsExportPDFView,
    SecurityAlertsExportCSVView,
    VisitorsExportCSVView,
    IssuesExportCSVView,
)

urlpatterns = [
    path('access/csv/', AccessLogsExportCSVView.as_view(), name='report_access_csv'),
    path('access/excel/', AccessLogsExportExcelView.as_view(), name='report_access_excel'),
    path('access/pdf/', AccessLogsExportPDFView.as_view(), name='report_access_pdf'),
    path('alerts/csv/', SecurityAlertsExportCSVView.as_view(), name='report_alerts_csv'),
    path('visitors/csv/', VisitorsExportCSVView.as_view(), name='report_visitors_csv'),
    path('issues/csv/', IssuesExportCSVView.as_view(), name='report_issues_csv'),
]
