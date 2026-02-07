import time
from typing import Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.services.queue import get_redis_connection

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
INGEST_QUEUE_DEPTH = Gauge(
    "ingest_queue_depth",
    "Current depth of the ingest queue",
)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        path = _route_path(request)
        method = request.method
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

        return response


def metrics_response() -> Response:
    try:
        redis_conn = get_redis_connection()
        queue_depth = redis_conn.llen(f"rq:queue:{settings.ingest_queue_name}")
        INGEST_QUEUE_DEPTH.set(queue_depth)
    except Exception:
        # Metrics endpoint should stay available even if Redis is unavailable.
        pass

    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
