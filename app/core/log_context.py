"""Request ID context storage for correlating logs within a single API call.

This module provides a way to store and retrieve the current request's
unique ID from anywhere in the codebase — without having to pass it as
a function argument through every layer of the code.

It uses Python's ContextVar, which works like a thread-local variable
that stores data for the current request. In an async web server, many
requests are handled concurrently on the same thread, but ContextVar
keeps each request's data separate and isolated, so request A's ID
never leaks into request B's logs.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

# The ContextVar that holds the request ID for the current request.
# The default value "-" is used when no request is active (e.g., during
# startup or background tasks).
REQUEST_ID_CONTEXT: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> Token:
    """Store a request ID in the current context.

    Called at the start of every incoming HTTP request by the
    RequestIDMiddleware. Returns a Token that can be used later to
    restore the previous value (important for cleanup).

    Args:
        request_id: The unique identifier for the current request.

    Returns:
        A Token object that must be passed to reset_request_id() when
        the request is finished.
    """
    return REQUEST_ID_CONTEXT.set(request_id)


def get_request_id() -> str:
    """Retrieve the request ID for the current context.

    Can be called from anywhere in the codebase (route handlers, service
    layers, logging filters, etc.) to get the ID of the request currently
    being processed. Returns "-" if no request is active.
    """
    return REQUEST_ID_CONTEXT.get()


def reset_request_id(token: Token) -> None:
    """Restore the request ID context to its previous value.

    Called at the end of every incoming HTTP request (in a finally block)
    to clean up. The token was returned by a previous call to
    set_request_id() and tells Python what value to revert to.

    Args:
        token: The Token returned by the corresponding set_request_id() call.
    """
    REQUEST_ID_CONTEXT.reset(token)
