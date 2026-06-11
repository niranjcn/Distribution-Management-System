from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
from fastapi import Response
from typing import Dict
import time
import platform

# ──────────────────────────────────────────────
# HTTP Metrics
# ──────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    labelnames=["method"],
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors (status >= 400)",
    labelnames=["method", "endpoint", "status_code"],
)

# ──────────────────────────────────────────────
# Authentication Metrics
# ──────────────────────────────────────────────

login_attempts_total = Counter(
    "login_attempts_total",
    "Total login attempts",
    labelnames=["status"],  # success / failure
)

successful_logins_total = Counter(
    "successful_logins_total",
    "Total successful logins",
)

failed_logins_total = Counter(
    "failed_logins_total",
    "Total failed logins",
)

token_validation_failures_total = Counter(
    "token_validation_failures_total",
    "Total token validation failures",
)

# ──────────────────────────────────────────────
# Database Metrics
# ──────────────────────────────────────────────

mysql_queries_total = Counter(
    "mysql_queries_total",
    "Total MySQL queries executed",
    labelnames=["operation"],  # select / insert / update / delete / other
)

mysql_query_duration_seconds = Histogram(
    "mysql_query_duration_seconds",
    "MySQL query duration in seconds",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

mysql_query_failures_total = Counter(
    "mysql_query_failures_total",
    "Total MySQL query failures",
    labelnames=["operation"],
)

mysql_active_connections = Gauge(
    "mysql_active_connections",
    "Current number of active MySQL connections",
)

# ──────────────────────────────────────────────
# Business Metrics — Users
# ──────────────────────────────────────────────

total_users = Gauge("total_users", "Total number of users")
active_users = Gauge("active_users", "Number of active users")
new_users_created_total = Counter("new_users_created_total", "Total new users created")

# ──────────────────────────────────────────────
# Business Metrics — Operators
# ──────────────────────────────────────────────

total_operators = Gauge("total_operators", "Total number of operators")
active_operators = Gauge("active_operators", "Number of active operators")
operator_logins_total = Counter("operator_logins_total", "Total operator logins")

# ──────────────────────────────────────────────
# Business Metrics — Clusters
# ──────────────────────────────────────────────

total_clusters = Gauge("total_clusters", "Total number of clusters")
active_clusters = Gauge("active_clusters", "Number of active clusters")

# ──────────────────────────────────────────────
# Business Metrics — Sub Distributors
# ──────────────────────────────────────────────

total_sub_distributors = Gauge("total_sub_distributors", "Total number of sub distributors")
active_sub_distributors = Gauge("active_sub_distributors", "Number of active sub distributors")

# ──────────────────────────────────────────────
# Business Metrics — Inventory / Devices
# ──────────────────────────────────────────────

inventory_items_total = Gauge("inventory_items_total", "Total inventory items")
device_distributions_total = Counter(
    "device_distributions_total",
    "Total device distributions",
    labelnames=["status"],
)
low_stock_items_total = Gauge("low_stock_items_total", "Items below reorder level")

# ──────────────────────────────────────────────
# Business Metrics — Orders / Distributions
# ──────────────────────────────────────────────

distributions_created_total = Counter("distributions_created_total", "Total distributions created")
distributions_completed_total = Counter("distributions_completed_total", "Total distributions completed")
distributions_failed_total = Counter("distributions_failed_total", "Total distributions failed")

# ──────────────────────────────────────────────
# System Metrics
# ──────────────────────────────────────────────

app_info = Info("app", "Application metadata")
app_info.info({
    "name": "distribution-management-system",
    "framework": "fastapi",
    "python_version": platform.python_version(),
})

app_uptime_seconds = Gauge("app_uptime_seconds", "Application uptime in seconds")
_app_start_time = time.time()


def get_uptime_seconds() -> float:
    return time.time() - _app_start_time


# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def _classify_sql_operation(query: str) -> str:
    upper = query.strip().upper()
    if upper.startswith("SELECT"):
        return "select"
    if upper.startswith("INSERT"):
        return "insert"
    if upper.startswith("UPDATE"):
        return "update"
    if upper.startswith("DELETE"):
        return "delete"
    return "other"


class MetricsMiddleware:
    """ASGI middleware that records HTTP request metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/unknown")

        # Skip metrics endpoint itself to avoid recursive instrumentation
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        http_requests_in_progress.labels(method=method).inc()
        start = time.time()

        original_send = send

        async def _send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                duration = time.time() - start

                http_requests_total.labels(
                    method=method, endpoint=path, status_code=str(status_code)
                ).inc()
                http_request_duration_seconds.labels(
                    method=method, endpoint=path, status_code=str(status_code)
                ).observe(duration)

                if status_code >= 400:
                    http_errors_total.labels(
                        method=method, endpoint=path, status_code=str(status_code)
                    ).inc()

            await original_send(message)

        try:
            await self.app(scope, receive, _send_wrapper)
        finally:
            http_requests_in_progress.labels(method=method).dec()


async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics at /metrics."""
    app_uptime_seconds.set(get_uptime_seconds())
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
