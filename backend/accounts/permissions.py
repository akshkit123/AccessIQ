from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from rest_framework import permissions
from .models import UserRole


def is_admin_user(user) -> bool:
    """Checks if user has full administrative privileges."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == UserRole.ADMIN)


def is_security_staff(user) -> bool:
    """Checks if user has the dedicated SECURITY_STAFF / Bouncer role."""
    if not user or not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    if profile and profile.role == UserRole.SECURITY_STAFF:
        return True
    return hasattr(user, 'security_profile')


def is_security_staff_or_admin(user) -> bool:
    """Checks if user can access security station operational workflows."""
    return is_admin_user(user) or is_security_staff(user)


# ========================================================
# REST Framework Permission Classes
# ========================================================

class IsSecurityStaffOrAdmin(permissions.BasePermission):
    """
    Allows access to operational endpoints for Security Staff and Administrators.
    Students, faculty, and unauthorized roles are blocked.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_security_staff_or_admin(request.user))


class IsSecurityStaffOnly(permissions.BasePermission):
    """
    Restricts access strictly to operational Security Staff members.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_security_staff(request.user))


class IsAdminOnly(permissions.BasePermission):
    """
    Strictly prohibits Security Staff, Students, and unauthorized users from administrative APIs.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin_user(request.user))


# ========================================================
# Django Web View Decorators
# ========================================================

def security_staff_required(view_func):
    """
    Decorator for views reserved for Security Staff and Administrators.
    Redirects unauthenticated users to login; redirects non-staff to a 403 response.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        if not is_security_staff_or_admin(request.user):
            return HttpResponseForbidden("Access Denied: You do not have permissions to access the Security Station.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """
    Decorator for Admin Dashboards & Configuration Views.
    SECURITY_STAFF users are safely redirected to their dedicated Bouncer Dashboard.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # For backward-compatibility with open dev mode if no users exist, allow if DEBUG and no user logged in
            # but if logged in as security staff, redirect to bouncer portal!
            return redirect(f'/login/?next={request.path}')

        # If user is a bouncer/security staff, prevent access to admin and route to bouncer portal
        if is_security_staff(request.user) and not is_admin_user(request.user):
            messages.warning(request, "Access Restricted: Security personnel are directed to the Operational Security Portal.")
            return redirect('bouncer_dashboard')

        if not is_admin_user(request.user):
            return HttpResponseForbidden("Access Denied: Administrative privileges required.")

        return view_func(request, *args, **kwargs)
    return _wrapped_view
