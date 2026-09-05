from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

import base64
from django.core.files.base import ContentFile
from accounts.models import UserProfile, AuthorizedDevice
from identity.models import StudentProfile, StaffProfile, BarcodeIdentity, FaceProfile, IdentityStatus
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection
from visitors.models import Visitor, TemporaryPass, VisitorStatus, PassStatus
from security.models import SecurityAlert, AuditLog, IssueReport, AlertStatus, IssueStatus
from accounts.permissions import is_security_staff, is_admin_user


def _check_security_staff_redirect(request):
    """
    Ensures authentication and proper portal routing:
    - Unauthenticated users are redirected to login.
    - Security Staff / Bouncers are redirected to their dedicated operational portal.
    """
    if not request.user.is_authenticated:
        return redirect('bouncer_login')
    if is_security_staff(request.user) and not is_admin_user(request.user):
        return redirect('bouncer_dashboard')
    return None


def get_dashboard_metrics():
    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_students = StudentProfile.objects.count()
    total_staff = StaffProfile.objects.count()
    total_users = total_students + total_staff

    today_logs = AccessLog.objects.filter(timestamp__gte=today_start)
    today_attempts = today_logs.count()
    today_granted = today_logs.filter(final_decision=AccessDecision.GRANTED).count()
    today_denied = today_logs.filter(final_decision=AccessDecision.DENIED).count()
    today_entries = today_logs.filter(direction=AccessDirection.ENTRY, final_decision=AccessDecision.GRANTED).count()
    today_exits = today_logs.filter(direction=AccessDirection.EXIT, final_decision=AccessDecision.GRANTED).count()

    active_visitors = Visitor.objects.filter(status=VisitorStatus.CHECKED_IN).count()
    active_passes = TemporaryPass.objects.filter(status=PassStatus.ACTIVE, valid_until__gte=timezone.now()).count()
    recent_alerts = SecurityAlert.objects.filter(status=AlertStatus.NEW).count()
    open_issues = IssueReport.objects.filter(status=IssueStatus.OPEN).count()
    active_locations = AccessLocation.objects.filter(is_active=True).count()

    # 7-day trend
    daily_labels = []
    daily_granted = []
    daily_denied = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))

        day_logs = AccessLog.objects.filter(timestamp__range=(day_start, day_end))
        daily_labels.append(day.strftime('%b %d'))
        daily_granted.append(day_logs.filter(final_decision=AccessDecision.GRANTED).count())
        daily_denied.append(day_logs.filter(final_decision=AccessDecision.DENIED).count())

    # Location distribution
    location_stats = AccessLog.objects.values('location__name').annotate(total=Count('id')).order_by('-total')[:6]
    location_labels = [item['location__name'] for item in location_stats]
    location_counts = [item['total'] for item in location_stats]

    # Alert types distribution
    alert_stats = SecurityAlert.objects.values('alert_type').annotate(total=Count('id')).order_by('-total')[:5]
    alert_labels = [item['alert_type'].replace('_', ' ').title() for item in alert_stats]
    alert_counts = [item['total'] for item in alert_stats]

    # Hourly peak distribution
    hourly_counts = [0] * 24
    hourly_labels = [f'{h:02d}:00' for h in range(24)]
    for log in today_logs:
        h = log.timestamp.hour
        hourly_counts[h] += 1

    return {
        'total_users': total_users,
        'total_students': total_students,
        'total_staff': total_staff,
        'today_attempts': today_attempts,
        'today_granted': today_granted,
        'today_denied': today_denied,
        'today_entries': today_entries,
        'today_exits': today_exits,
        'active_visitors': active_visitors,
        'active_passes': active_passes,
        'recent_alerts': recent_alerts,
        'open_issues': open_issues,
        'active_locations': active_locations,
        'daily_labels': daily_labels,
        'daily_granted': daily_granted,
        'daily_denied': daily_denied,
        'location_labels': location_labels,
        'location_counts': location_counts,
        'alert_labels': alert_labels,
        'alert_counts': alert_counts,
        'hourly_counts': hourly_counts,
        'hourly_labels': hourly_labels,
    }


def dashboard_home(request):
    redirect_resp = _check_security_staff_redirect(request)
    if redirect_resp:
        return redirect_resp
    metrics = get_dashboard_metrics()
    recent_logs = AccessLog.objects.all().select_related('location', 'student', 'staff')[:12]
    unresolved_alerts = SecurityAlert.objects.filter(status=AlertStatus.NEW).select_related('location')[:6]
    locations = AccessLocation.objects.filter(is_active=True)

    context = {
        **metrics,
        'recent_logs': recent_logs,
        'unresolved_alerts': unresolved_alerts,
        'locations': locations,
        'page_title': 'Campus Security Command Center',
    }
    return render(request, 'dashboard/index.html', context)


def live_verification_station(request):
    locations = AccessLocation.objects.filter(is_active=True)
    recent_logs = AccessLog.objects.all().select_related('location', 'student', 'staff')[:8]
    context = {
        'locations': locations,
        'recent_logs': recent_logs,
        'page_title': 'Dual-Factor Access Verification Terminal',
    }
    return render(request, 'dashboard/verify_station.html', context)


def users_directory(request):
    redirect_resp = _check_security_staff_redirect(request)
    if redirect_resp:
        return redirect_resp
    if request.method == 'POST':
        identity_type = request.POST.get('identity_type', 'STUDENT')
        id_number = request.POST.get('id_number', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        department = request.POST.get('department', 'Computer Engineering').strip()
        course = request.POST.get('course', 'B.Tech').strip()
        semester = int(request.POST.get('semester', 3) or 3)
        contact_phone = request.POST.get('contact_phone', '').strip()
        barcode_value = request.POST.get('barcode', '').strip() or id_number
        photo_file = request.FILES.get('photo')

        if id_number and first_name:
            if identity_type == 'STUDENT':
                student, _ = StudentProfile.objects.get_or_create(
                    student_id=id_number,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'department': department,
                        'course': course,
                        'semester': semester,
                        'contact_phone': contact_phone,
                        'status': IdentityStatus.ACTIVE,
                    }
                )
                if photo_file:
                    student.photo = photo_file
                    student.save()

                # Link Barcode
                BarcodeIdentity.objects.get_or_create(
                    barcode_value=barcode_value,
                    defaults={'student': student, 'identity_type': 'STUDENT', 'is_active': True}
                )

                # Link Face Profile
                if photo_file:
                    fp, _ = FaceProfile.objects.get_or_create(student=student)
                    fp.registered_photo = photo_file
                    fp.enrollment_status = 'ENROLLED'
                    fp.save()

                # Face Profile registered

            else:
                staff, _ = StaffProfile.objects.get_or_create(
                    staff_id=id_number,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'department': department,
                        'designation': request.POST.get('designation', 'Assistant Professor'),
                        'contact_phone': contact_phone,
                        'status': IdentityStatus.ACTIVE,
                    }
                )
                if photo_file:
                    staff.photo = photo_file
                    staff.save()

                BarcodeIdentity.objects.get_or_create(
                    barcode_value=barcode_value,
                    defaults={'staff': staff, 'identity_type': 'STAFF', 'is_active': True}
                )
                if photo_file:
                    fp, _ = FaceProfile.objects.get_or_create(staff=staff)
                    fp.registered_photo = photo_file
                    fp.enrollment_status = 'ENROLLED'
                    fp.save()

            return redirect('dashboard_users')

    students = StudentProfile.objects.all().order_by('student_id')
    staff = StaffProfile.objects.all().order_by('staff_id')
    context = {
        'students': students,
        'staff': staff,
        'page_title': 'Identity & Biometrics Management',
    }
    return render(request, 'dashboard/users.html', context)


def quick_enroll_view(request):
    redirect_resp = _check_security_staff_redirect(request)
    if redirect_resp:
        return redirect_resp
    """
    Dedicated Mobile & Desktop Card Scanner & Biometrics Enrollment Station.
    Allows scanning a student ID card barcode with phone/webcam camera and capturing face biometrics.
    """
    enrolled_student = None
    error_message = None

    if request.method == 'POST':
        student_id = request.POST.get('id_number', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        department = request.POST.get('department', 'Computer Engineering').strip()
        course = request.POST.get('course', 'B.Tech').strip()
        try:
            semester = int(request.POST.get('semester', 3) or 3)
        except (ValueError, TypeError):
            semester = 3
        contact_phone = request.POST.get('contact_phone', '').strip()
        barcode_value = request.POST.get('barcode', '').strip() or student_id
        photo_file = request.FILES.get('photo')
        photo_b64 = request.POST.get('photo_b64', '').strip()

        if not student_id:
            error_message = "Student ID / Barcode number is required. Please scan the ID card."
        elif not first_name:
            error_message = "Student First Name is required."
        else:
            student, _ = StudentProfile.objects.get_or_create(
                student_id=student_id,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'department': department,
                    'course': course,
                    'semester': semester,
                    'contact_phone': contact_phone,
                    'status': IdentityStatus.ACTIVE,
                }
            )
            student.first_name = first_name
            student.last_name = last_name
            student.department = department
            student.course = course
            student.semester = semester
            if contact_phone:
                student.contact_phone = contact_phone

            saved_photo = None
            if photo_file:
                student.photo = photo_file
                student.save()
                saved_photo = student.photo
            elif photo_b64 and 'base64,' in photo_b64:
                try:
                    img_data = base64.b64decode(photo_b64.split('base64,')[1])
                    fname = f"student_{student_id}_{int(timezone.now().timestamp())}.jpg"
                    student.photo.save(fname, ContentFile(img_data), save=True)
                    saved_photo = student.photo
                except Exception:
                    pass
            student.save()

            # Link Barcode
            b_obj, _ = BarcodeIdentity.objects.get_or_create(
                barcode_value=barcode_value,
                defaults={'student': student, 'identity_type': 'STUDENT', 'is_active': True}
            )
            if b_obj.student != student:
                b_obj.student = student
                b_obj.save()

            # Face Profile
            if saved_photo:
                fp, _ = FaceProfile.objects.get_or_create(student=student)
                fp.registered_photo = saved_photo
                fp.enrollment_status = 'ENROLLED'
                fp.sample_count += 1
                fp.save()

            enrolled_student = student

    context = {
        'page_title': 'Scan & Enroll Student (Mobile / Barcode)',
        'enrolled_student': enrolled_student,
        'error_message': error_message,
    }
    return render(request, 'dashboard/quick_enroll.html', context)




def visitors_console(request):
    visitors = Visitor.objects.all().order_by('-created_at')
    passes = TemporaryPass.objects.all().select_related('visitor').order_by('-created_at')
    locations = AccessLocation.objects.filter(is_active=True)
    context = {
        'visitors': visitors,
        'passes': passes,
        'locations': locations,
        'page_title': 'Visitor & Temporary Pass Management',
    }
    return render(request, 'dashboard/visitors.html', context)


def alerts_audit(request):
    redirect_resp = _check_security_staff_redirect(request)
    if redirect_resp:
        return redirect_resp
    alerts = SecurityAlert.objects.all().select_related('location', 'resolved_by').order_by('-timestamp')[:50]
    audit_logs = AuditLog.objects.all().select_related('user').order_by('-timestamp')[:50]
    issues = IssueReport.objects.all().select_related('reporter', 'location', 'resolved_by').order_by('-created_at')[:50]
    context = {
        'alerts': alerts,
        'audit_logs': audit_logs,
        'issues': issues,
        'page_title': 'Security Alerts, Issues & Compliance Audit',
    }
    return render(request, 'dashboard/alerts.html', context)


def reports_center(request):
    redirect_resp = _check_security_staff_redirect(request)
    if redirect_resp:
        return redirect_resp
    context = {
        'page_title': 'Reports & Data Export Center',
    }
    return render(request, 'dashboard/reports.html', context)


class DashboardAnalyticsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        metrics = get_dashboard_metrics()
        return Response(metrics)
