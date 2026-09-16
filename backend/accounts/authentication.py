from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication subclass that does not enforce CSRF.
    Enables smooth AJAX and API interactions for live terminal and bouncer portals
    while preserving authenticated session context.
    """
    def enforce_csrf(self, request):
        return  # Skip CSRF validation for REST API calls
