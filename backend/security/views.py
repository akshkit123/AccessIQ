from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from .models import SecurityAlert, AuditLog, IssueReport, AlertStatus, IssueStatus
from .serializers import SecurityAlertSerializer, AuditLogSerializer, IssueReportSerializer


class SecurityAlertListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        alerts = SecurityAlert.objects.all().select_related('location', 'resolved_by').order_by('-timestamp')[:50]
        serializer = SecurityAlertSerializer(alerts, many=True)
        return Response(serializer.data)


class SecurityAlertResolveAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            alert = SecurityAlert.objects.get(pk=pk)
            alert.status = AlertStatus.RESOLVED
            alert.resolved_by = request.user if request.user.is_authenticated else None
            alert.resolved_at = timezone.now()
            alert.save()
            return Response({'success': True, 'message': 'Alert marked as resolved'})
        except SecurityAlert.DoesNotExist:
            return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)


class AuditLogListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        logs = AuditLog.objects.all().select_related('user').order_by('-timestamp')[:100]
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class IssueReportListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        issues = IssueReport.objects.all().select_related('reporter', 'location', 'resolved_by').order_by('-created_at')[:50]
        serializer = IssueReportSerializer(issues, many=True)
        return Response(serializer.data)
