"""Structured HTTP request logging middleware.

Automatically logs every incoming HTTP request with useful details such as
the HTTP method, URL path, response status code, duration in milliseconds,
and the client's IP address. This provides an audit trail and makes it easy
to diagnose slow or failing requests by searching the logs.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every HTTP request — code that runs before and after every request.

    For each request, it records:
      - The HTTP method (GET, POST, etc.) and URL path
      - The response status code (200, 404, 500, etc.)
      - How long the request took (in milliseconds)
      - The client's IP address

    If the request handler raises an unhandled exception, this middleware
    logs the error with full stack trace details before re-raising it,
    ensuring that failures are always recorded even when they crash.
    """

    async def dispatch(self, request: Request, call_next):
        # Record start time so we can calculate request duration later
        start = time.perf_counter()
        # Get the client IP; may be absent in some test environments
        client_ip = request.client.host if request.client else "unknown"
        try:
            response = await call_next(request)
        except Exception:
            # If the route handler throws an unhandled exception, we still
            # want a log entry. We record it as a 500 (server error) and
            # use logger.exception() which automatically includes the full
            # Python stack trace in the log output.
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                },
            )
            # Re-raise the exception so that the framework's error handling
            # can still produce an appropriate error response to the client.
            raise

        # Normal (non-error) path: log the completed request with its actual
        # status code and duration.
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": client_ip,
            },
        )
        return response
