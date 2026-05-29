from django.http import JsonResponse
from rest_framework.permissions import SAFE_METHODS


class DoubleSubmitCSRFMiddleware:
    """Validate CSRF token for cookie-authenticated API requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_api_request = request.path_info.startswith("/api/")

        if is_api_request and request.method not in SAFE_METHODS and request.COOKIES.get("access_token"):
            csrf_cookie = request.COOKIES.get("csrftoken")
            csrf_header = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")

            if not csrf_cookie or csrf_cookie != csrf_header:
                return JsonResponse({"detail": "CSRF validation failed."}, status=403)

        response = self.get_response(request)
        return response
