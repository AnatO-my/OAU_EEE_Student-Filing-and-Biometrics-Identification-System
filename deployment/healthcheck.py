"""Local process liveness, without a database connection or credential output."""
import os
import urllib.request

request = urllib.request.Request(
    os.environ.get("HEALTHCHECK_URL", "http://127.0.0.1:8000/health/live/"),
    headers={"Host": "localhost", "X-Forwarded-Proto": "https"},
)
with urllib.request.urlopen(request, timeout=5) as response:
    if response.status != 200:
        raise SystemExit(1)
