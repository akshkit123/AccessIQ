from rest_framework.views import APIView
from rest_framework import permissions
from .services import (
    export_access_logs_csv,
    export_access_logs_excel,
    export_access_logs_pdf,
    export_security_alerts_csv,
    export_visitors_csv,
    export_issue_reports_csv,
)


class AccessLogsExportCSVView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_access_logs_csv()


class AccessLogsExportExcelView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_access_logs_excel()


class AccessLogsExportPDFView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_access_logs_pdf()


class SecurityAlertsExportCSVView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_security_alerts_csv()


class VisitorsExportCSVView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_visitors_csv()


class IssuesExportCSVView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return export_issue_reports_csv()
