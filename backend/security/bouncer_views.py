from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from accounts.models import UserProfile, UserRole, AuthorizedDevice
from accounts.permissions import is_security_staff, is_admin_user
from access_control.models import AccessLocation, AccessLog, AccessDecision, AccessDirection
from visitors.models import Visitor, TemporaryPass, VisitorStatus, PassStatus
from security.models import (
    SecurityAlert,
    AlertStatus,
    IssueReport,
    SecurityStaffProfile,
    AuditLog,
    AuditAction,
)


def _get_active_location(request, user):
    """Resolves the operational gate (College Main Gate)."""
    loc = AccessLocation.objects.filter(is_active=True).first()
    if not loc:
        loc, _ = AccessLocation.objects.get_or_create(
            code='GATE-MAIN',
            defaults={'name': 'College Main Gate', 'is_active': True}
        )
    return loc


def bouncer_dashboard(request):
    """
    Dedicated, Operational Dashboard for Security Staff / Bouncers.
    Strictly isolated from administrative analytics, user management, and sensitive academic databases.
    """
    user = request.user
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Resolve Staff Profile or default demo profile
    staff_profile = None
    badge_number = 'SEC-104'
    is_on_duty = True
    if user.is_authenticated:
        staff_profile = getattr(user, 'security_profile', None)
        if staff_profile:
            badge_number = staff_profile.badge_number
            is_on_duty = staff_profile.is_on_duty

    # Active Location: Always College Main Gate
    current_location = _get_active_location(request, user)
    available_locations = AccessLocation.objects.filter(is_active=True)

    # Operational Metrics (Today only)
    loc_query = Q(timestamp__gte=today_start)
    if current_location:
        loc_query &= Q(location=current_location)

    today_logs = AccessLog.objects.filter(loc_query)
    today_scans = today_logs.count()
    today_granted = today_logs.filter(final_decision=AccessDecision.GRANTED).count()
    today_denied = today_logs.filter(final_decision=AccessDecision.DENIED).count()

    active_visitors_count = Visitor.objects.filter(status=VisitorStatus.CHECKED_IN).count()
    open_alerts_count = SecurityAlert.objects.filter(
        Q(timestamp__gte=today_start, status=AlertStatus.NEW) &
        (Q(location=current_location) | Q(location__isnull=True))
    ).count()

    # Initial Active Visitors (Recent 10)
    recent_active_visitors = Visitor.objects.filter(
        status=VisitorStatus.CHECKED_IN
    ).prefetch_related('passes').order_by('-entry_time')[:10]

    # Initial Recent Security Alerts for current gate (Recent 10)
    recent_alerts = SecurityAlert.objects.filter(
        Q(timestamp__gte=today_start) & (Q(location=current_location) | Q(location__isnull=True))
    ).select_related('location').order_by('-timestamp')[:10]

    # Initial My Recent Activity (filtered to current user or recent gate logs)
    my_logs_query = Q(timestamp__gte=today_start)
    if user.is_authenticated and not user.is_superuser:
        my_logs_query &= (Q(verified_by=user) | Q(verified_by__isnull=True))
    if current_location:
        my_logs_query &= Q(location=current_location)

    my_recent_logs = AccessLog.objects.filter(my_logs_query).select_related('location', 'student', 'staff').order_by('-timestamp')[:15]

    context = {
        'page_title': 'Security Staff Operational Portal',
        'bouncer_user': user,
        'staff_name': (user.get_full_name() or user.username) if user.is_authenticated else 'Security Officer (Demo)',
        'badge_number': badge_number,
        'is_on_duty': is_on_duty,
        'current_location': current_location,
        'available_locations': available_locations,
        # Operational Stats
        'today_scans': today_scans,
        'today_granted': today_granted,
        'today_denied': today_denied,
        'active_visitors_count': active_visitors_count,
        'open_alerts_count': open_alerts_count,
        # Initial Lists
        'recent_active_visitors': recent_active_visitors,
        'recent_alerts': recent_alerts,
        'my_recent_logs': my_recent_logs,
    }
    return render(request, 'bouncer/bouncer_dashboard.html', context)


def bouncer_login(request):
    """
    Dedicated Security Portal Authentication.
    Directs Security Staff to Bouncer Dashboard and Admins to Command Center.
    """
    if request.user.is_authenticated:
        if is_security_staff(request.user) and not is_admin_user(request.user):
            return redirect('bouncer_dashboard')
        return redirect('dashboard_home')

    error_message = None
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # One-Click Demo Security Staff Login
        if action == 'demo_bouncer':
            from django.contrib.auth.models import User
            demo_user = User.objects.filter(username='officer_sharma').first()
            if not demo_user:
                # Create demo officer if not present
                demo_user = User.objects.create_user(
                    username='officer_sharma',
                    password='password123',
                    first_name='Rajesh',
                    last_name='Sharma',
                    is_staff=False,
                    is_superuser=False
                )
                UserProfile.objects.filter(user=demo_user).update(role=UserRole.SECURITY_STAFF)
                loc = AccessLocation.objects.first()
                SecurityStaffProfile.objects.create(
                    user=demo_user,
                    badge_number='SEC-104',
                    primary_location=loc,
                    shift_name='Gate 1 Morning Shift',
                    is_on_duty=True
                )
            login(request, demo_user)
            messages.success(request, f"Logged in as {demo_user.get_full_name()} (Security Staff).")
            return redirect('bouncer_dashboard')

        # One-Click Demo Admin Login
        if action == 'demo_admin':
            from django.contrib.auth.models import User
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                login(request, admin_user)
                return redirect('dashboard_home')

        # Standard Credentials Login
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            error_message = "Please enter both username and password."
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                if not user.is_active:
                    error_message = "This account is inactive. Contact the security administrator."
                else:
                    login(request, user)
                    AuditLog.objects.create(
                        user=user,
                        action=AuditAction.LOGIN,
                        entity_type='SecurityTerminal',
                        details=f"Security Portal Login by {user.username}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    if is_security_staff(user) and not is_admin_user(user):
                        return redirect('bouncer_dashboard')
                    return redirect('dashboard_home')
            else:
                error_message = "Invalid username or password."

    return render(request, 'bouncer/bouncer_login.html', {'error_message': error_message})


def bouncer_logout(request):
    """Logs out security personnel and returns to portal login."""
    logout(request)
    messages.info(request, "Security session terminated. Logged out successfully.")
    return redirect('bouncer_login')


def portal_register(request):
    """
    Campus Security Registration Portal.
    Allows registering as either a Security Officer (Bouncer) or Security Administrator.
    """
    if request.user.is_authenticated:
        if is_security_staff(request.user) and not is_admin_user(request.user):
            return redirect('bouncer_dashboard')
        return redirect('dashboard_home')

    locations = AccessLocation.objects.filter(is_active=True)
    error_message = None

    if request.method == 'POST':
        from django.contrib.auth.models import User
        role = request.POST.get('role', 'SECURITY_STAFF').strip().upper()
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        badge_number = request.POST.get('badge_number', '').strip()
        location_id = request.POST.get('location_id')
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()

        if not username or not password:
            error_message = "Username and password are required."
        elif len(password) < 6:
            error_message = "Password must be at least 6 characters."
        elif password != password_confirm:
            error_message = "Passwords do not match."
        elif User.objects.filter(username__iexact=username).exists():
            error_message = f"Username '{username}' is already taken. Please choose another."
        elif role == 'SECURITY_STAFF' and badge_number and SecurityStaffProfile.objects.filter(badge_number__iexact=badge_number).exists():
            error_message = f"Badge Number '{badge_number}' is already registered."
        else:
            is_admin = (role == 'ADMIN')
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_admin,
                is_superuser=False
            )
            
            user_role = UserRole.ADMIN if is_admin else UserRole.SECURITY_STAFF
            UserProfile.objects.get_or_create(user=user, defaults={'role': user_role})

            if not is_admin:
                if not badge_number:
                    badge_number = f"SEC-{user.id + 100}"
                loc = AccessLocation.objects.filter(is_active=True).first()
                if not loc:
                    loc, _ = AccessLocation.objects.get_or_create(
                        code='GATE-MAIN',
                        defaults={'name': 'College Main Gate', 'is_active': True}
                    )
                SecurityStaffProfile.objects.create(
                    user=user,
                    badge_number=badge_number,
                    primary_location=loc,
                    is_on_duty=True
                )

            AuditLog.objects.create(
                user=user,
                action=AuditAction.CREATE,
                entity_type='User',
                entity_id=str(user.id),
                details=f"User registered with role {user_role}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            login(request, user)
            messages.success(request, f"Welcome {user.get_full_name() or user.username}! Your account has been registered.")

            if is_admin:
                return redirect('dashboard_home')
            return redirect('bouncer_dashboard')

    default_loc = AccessLocation.objects.filter(is_active=True).first()
    return render(request, 'bouncer/bouncer_register.html', {
        'locations': locations,
        'default_location': default_loc,
        'error_message': error_message
    })
