from django.urls import path
from .views import (
    dashboard_home,
    live_verification_station,
    users_directory,
    quick_enroll_view,
    visitors_console,
    alerts_audit,
    reports_center,
    DashboardAnalyticsAPIView,
)
from security.bouncer_views import (
    bouncer_dashboard,
    bouncer_login,
    bouncer_logout,
    portal_register,
)

urlpatterns = [
    # Admin / Supervisor Command Center
    path('', dashboard_home, name='dashboard_home'),
    path('terminal/', live_verification_station, name='live_verification_station'),
    path('users/', users_directory, name='dashboard_users'),
    path('enroll/', quick_enroll_view, name='quick_enroll'),
    path('visitors/', visitors_console, name='dashboard_visitors'),
    path('alerts/', alerts_audit, name='dashboard_alerts'),
    path('reports/', reports_center, name='dashboard_reports'),
    path('api/analytics/dashboard-stats/', DashboardAnalyticsAPIView.as_view(), name='api_dashboard_stats'),

    # ========================================================
    # AUTHENTICATION & ACCESS (ADMIN & BOUNCER)
    # ========================================================
    path('login/', bouncer_login, name='bouncer_login'),
    path('register/', portal_register, name='portal_register'),
    path('logout/', bouncer_logout, name='bouncer_logout'),

    # ========================================================
    # DEDICATED BOUNCER / SECURITY STAFF PORTAL
    # ========================================================
    path('bouncer/', bouncer_dashboard, name='bouncer_dashboard'),
    path('security/portal/', bouncer_dashboard, name='bouncer_portal_alias'),
]
