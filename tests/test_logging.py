from __future__ import annotations

import json
import logging

from app.core.log_context import reset_request_id, set_request_id
from app.core.logging import JsonFormatter, RequestIDFilter


def test_json_logging_includes_request_context_and_fields() -> None:
    token = set_request_id("req-123")
    try:
        logger = logging.getLogger("test.logger")
        record = logger.makeRecord(
            name="test.logger",
            level=logging.INFO,
            fn=__file__,
            lno=1,
            msg="request_completed",
            args=(),
            exc_info=None,
            extra={
                "method": "GET",
                "path": "/api/health/live",
                "status": 200,
                "duration_ms": 1.23,
            },
        )

        request_id_filter = RequestIDFilter()
        assert request_id_filter.filter(record)

        formatted = JsonFormatter().format(record)
        payload = json.loads(formatted)

        assert payload["message"] == "request_completed"
        assert payload["request_id"] == "req-123"
        assert payload["method"] == "GET"
        assert payload["path"] == "/api/health/live"
        assert payload["status"] == 200
        assert payload["duration_ms"] == 1.23
    finally:
        reset_request_id(token)
