"""Request ID tracking for correlating logs across a single API call.

Every time a request enters the system, it is assigned a unique identifier
(a UUID). This ID is attached to every log message produced while handling
that request, so you can search your logs for a single ID and see the
complete story of what happened during that one API call.

If the caller already provides an "X-Request-ID" header (common when
requests pass through API gateways or load balancers), that value is
reused instead of generating a new one.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.log_context import reset_request_id, set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to every incoming request.

    This is middleware — code that runs automatically before and after every
    HTTP request. It works in three steps:
      1. Check if the incoming request already has an "X-Request-ID" header.
         If not, generate a new random UUID.
      2. Store that ID in a context variable (like a thread-local variable
         that stores data for the current request) so that any code running
         during this request can access it — especially the logging system.
      3. After the request is done, add the same ID to the response headers
         so the client can reference it for debugging.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use the caller-provided request ID, or generate a new UUID if absent
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Store the request ID in a context variable so loggers can access it.
        # The returned token is needed later to restore the previous value.
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            # Always clean up the context variable, even if the request failed,
            # to avoid leaking the ID into unrelated requests.
            reset_request_id(token)
        # Echo the request ID back to the client in a response header
        response.headers["X-Request-ID"] = request_id
        return response
