from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.log_context import get_request_id


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        for field in ("method", "path", "status", "duration_ms", "client_ip", "action", "tenant_id", "user"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(RequestIDFilter())
    if settings.log_format == "json":
        stream_handler.setFormatter(JsonFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(request_id)s | %(message)s")
        )

    root.addHandler(stream_handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
