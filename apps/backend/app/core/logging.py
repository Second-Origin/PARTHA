import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.observability import get_request_id, redact_mapping

LOG_RECORD_ATTRIBUTES = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in LOG_RECORD_ATTRIBUTES and key not in {"message", "asctime"}
        }
        if extra:
            payload["extra"] = redact_mapping(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str, log_format: str = "text") -> None:
    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
