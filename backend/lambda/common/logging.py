import json
import logging as pylogging
from typing import Any


class JsonFormatter(pylogging.Formatter):
    def format(self, record: pylogging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }

        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id

        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def get_logger(name: str) -> pylogging.Logger:
    logger = pylogging.getLogger(name)

    if not logger.handlers:
        handler = pylogging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(pylogging.INFO)
        logger.propagate = False

    return logger


def log_json(
    logger: pylogging.Logger,
    level: int,
    message: str,
    request_id: str | None = None,
    **fields: Any,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "request_id": request_id,
            "extra_fields": fields,
        },
    )
