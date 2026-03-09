"""Application logging configuration with structured JSON output.

Sets up the Python logging system to produce either structured JSON logs
or plain-text logs, depending on the application's configuration.

Structured (JSON) logs are machine-readable, making it easy to search,
filter, and analyze them in tools like CloudWatch, Datadog, or the ELK
stack. Each log line is a JSON object with standard fields like timestamp,
level, message, and request_id.

Plain-text logs are more human-friendly and are typically used during
local development.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.log_context import get_request_id


class RequestIDFilter(logging.Filter):
    """A logging filter that attaches the current request ID to every log record.

    Python's logging system supports "filters" — small plugins that can
    inspect or modify a log record before it is written. This filter does
    not actually filter anything out (it always returns True). Instead, it
    enriches each log record by adding a 'request_id' field.

    This allows every log line to include the request ID, so you can search
    for a single ID and find all log messages related to that one API call.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Fetch the request ID that was stored for the current request
        # (see log_context.py) and attach it to the log record.
        record.request_id = get_request_id()
        # Always return True — we never want to suppress a log entry.
        return True


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Each log line becomes a JSON object like:
        {"timestamp": "...", "level": "INFO", "message": "...", "request_id": "..."}

    This structured format makes logs machine-readable, so you can easily
    query them in log aggregation tools (e.g., "show me all ERROR logs
    with request_id=abc-123").
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the base payload with fields that every log entry has
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        # Optionally include extra contextual fields if they were passed
        # via the "extra" dict when the log call was made (e.g., by the
        # request logging middleware).
        for field in ("method", "path", "status", "duration_ms", "client_ip", "action", "tenant_id", "user"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        # If the log was created with exception info (e.g., logger.exception()),
        # include the formatted stack trace in an "exception" field.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> None:
    """Initialize the application's logging system.

    This function is called once at application startup. It:
      1. Removes any pre-existing log handlers (to avoid duplicate output).
      2. Creates a new stream handler that writes to stdout/stderr.
      3. Attaches the RequestIDFilter so every log line includes the request ID.
      4. Chooses between JSON or plain-text formatting based on the
         application's log_format setting.
      5. Sets the minimum log level (DEBUG, INFO, WARNING, etc.) based on
         the application's log_level setting.
    """
    root = logging.getLogger()
    # Remove existing handlers to prevent duplicate log lines if this
    # function is called more than once (e.g., during testing).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    # Attach the request ID filter so every log record gets a request_id field
    stream_handler.addFilter(RequestIDFilter())
    if settings.log_format == "json":
        # Use JSON formatting for production — machine-readable and searchable
        stream_handler.setFormatter(JsonFormatter())
    else:
        # Use plain-text formatting for local development — easier to read
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(request_id)s | %(message)s")
        )

    root.addHandler(stream_handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
