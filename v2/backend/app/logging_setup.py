"""Structured JSON logging with a PII-redaction filter on the handler."""

import json
import logging
from datetime import UTC, datetime
from typing import IO, Any

from app.guardrails.redaction import RedactingFilter

_RESERVED = set(vars(logging.makeLogRecord({})))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in vars(record).items() if k not in _RESERVED})
        if record.exc_text:
            payload["exc"] = record.exc_text
        return json.dumps(payload, default=str)


def configure_logging(level: str, stream: IO[str] | None = None) -> None:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
