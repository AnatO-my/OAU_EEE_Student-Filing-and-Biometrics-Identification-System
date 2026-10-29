from django.http import JsonResponse


class DemoRequestLimits:
    """Give a useful API error before attempting an oversized demo upload."""
    max_request_bytes = 4 * 1024 * 1024

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            size = int(request.META.get("CONTENT_LENGTH") or "0")
        except ValueError:
            size = -1
        if size < 0 or size > self.max_request_bytes:
            response = JsonResponse({"detail": "Demo requests are limited to 4 MiB; use files up to 3 MiB."}, status=413)
            response["Cache-Control"] = "private, no-store"
            return response
        return self.get_response(request)
