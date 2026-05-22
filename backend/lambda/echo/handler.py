import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from common.logging import get_logger, log_json
from common.response import json_response
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")


def _parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        raise ValueError("Request body is required.")

    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
    elif isinstance(raw_body, dict):
        body = raw_body
    else:
        raise ValueError("Request body must be a JSON object.")

    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Field 'message' is required and must be a non-empty string.")

    return message.strip()


def lambda_handler(event, context):
    # A generated request_id lets API clients, logs, and persistence all refer to the same request.
    request_id = str(uuid4())

    try:
        message = _parse_body(event)
        repository = TraceRepository(TRACE_TABLE_NAME)

        trace_record = {
            "request_id": request_id,
            # DynamoDB gives us a simple, durable request trace before Bedrock flows exist.
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": event.get("rawPath") or event.get("path") or "/echo",
            "message": message,
            "status": "recorded",
        }
        repository.save_trace(trace_record)

        log_json(
            LOGGER,
            logging.INFO,
            "echo request recorded",
            request_id=request_id,
            path=trace_record["path"],
            status=trace_record["status"],
        )

        return json_response(
            200,
            {
                "requestId": request_id,
                "message": message,
                "status": "recorded",
            },
        )
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid echo request",
            request_id=request_id,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})
    except Exception:
        LOGGER.exception(
            "unexpected echo failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": event.get("rawPath") or event.get("path") or "/echo",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})
