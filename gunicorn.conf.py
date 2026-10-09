"""gunicorn settings for a small student-demo deployment.

Every value can be overridden by the host with environment variables.
Each worker thread opens at most one MySQL connection per request, so the
maximum number of database connections is WEB_CONCURRENCY * GUNICORN_THREADS
(default 2 * 4 = 8), far below MySQL's default max_connections (151).
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 30                    # a request that takes longer is stopped
graceful_timeout = 20
keepalive = 5
max_requests = 1000             # recycle workers now and then (guards against slow leaks)
max_requests_jitter = 100
limit_request_line = 4094       # reject oversized request lines and headers
limit_request_fields = 60
limit_request_field_size = 8190
accesslog = "-"                 # to stdout: the host collects logs
errorlog = "-"
# Access log without query strings, so search text never reaches the logs.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
# Make the app import fail loudly at start-up (e.g. missing SECRET_KEY)
# instead of in the first request.
preload_app = True
