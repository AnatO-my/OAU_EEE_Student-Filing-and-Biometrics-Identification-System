"""Aiven's 20 connections include provider sessions: keep concurrency bounded."""
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = 1
worker_class = "gthread"
threads = 2
timeout = 90
graceful_timeout = 90
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = False
# The container is reachable only through our edge; it overwrites proxy headers.
forwarded_allow_ips = "*"
# Guardian access tokens may appear in URLs: do not log raw access requests.
accesslog = None
errorlog = "-"
capture_output = True
