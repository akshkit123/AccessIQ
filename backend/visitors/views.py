import uuid
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from .models import Visitor, TemporaryPass, VisitorStatus, PassStatus
from .serializers import VisitorSerializer, TemporaryPassSerializer
from security.models import AuditLog, AuditAction


class VisitorListCreateAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        visitors = Visitor.objects.all().order_by('-created_at')
        serializer = VisitorSerializer(visitors, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = VisitorSerializer(data=request.data)
        if serializer.is_valid():
            visitor = serializer.save()
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=AuditAction.CREATE,
                entity_type='Visitor',
                entity_id=str(visitor.id),
                details=f"Visitor registered: {visitor.full_name} to meet {visitor.person_to_meet}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VisitorApproveAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            visitor = Visitor.objects.get(pk=pk)
            visitor.status = VisitorStatus.APPROVED
            visitor.entry_time = timezone.now()
            visitor.save()

            # Auto-create Temporary Pass for 8 hours validity
            pass_code = f"PASS-{uuid.uuid4().hex[:8].upper()}"
            temp_pass = TemporaryPass.objects.create(
                visitor=visitor,
                pass_code=pass_code,
                valid_from=timezone.now(),
                valid_until=timezone.now() + timezone.timedelta(hours=8),
                status=PassStatus.ACTIVE
            )

            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=AuditAction.APPROVE,
                entity_type='Visitor',
                entity_id=str(visitor.id),
                details=f"Visitor {visitor.full_name} approved. Generated Pass Code {pass_code}.",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            return Response({
                'success': True,
                'message': f"Visitor {visitor.full_name} approved.",
                'pass_code': pass_code,
                'valid_until': temp_pass.valid_until,
            })
        except Visitor.DoesNotExist:
            return Response({'error': 'Visitor not found'}, status=status.HTTP_404_NOT_FOUND)


class TemporaryPassListCreateAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        passes = TemporaryPass.objects.all().select_related('visitor').order_by('-created_at')
        serializer = TemporaryPassSerializer(passes, many=True)
        return Response(serializer.data)

    def post(self, request):
        visitor_id = request.data.get('visitor')
        valid_hours = int(request.data.get('valid_hours', 8))
        allowed_locations = request.data.get('allowed_locations', [])

        try:
            visitor = Visitor.objects.get(pk=visitor_id)
            pass_code = f"PASS-{uuid.uuid4().hex[:8].upper()}"
            temp_pass = TemporaryPass.objects.create(
                visitor=visitor,
                pass_code=pass_code,
                valid_from=timezone.now(),
                valid_until=timezone.now() + timezone.timedelta(hours=valid_hours),
                status=PassStatus.ACTIVE,
                notes=request.data.get('notes', '')
            )
            if allowed_locations:
                temp_pass.allowed_locations.set(allowed_locations)

            serializer = TemporaryPassSerializer(temp_pass)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Visitor.DoesNotExist:
            return Response({'error': 'Visitor not found'}, status=status.HTTP_404_NOT_FOUND)
