import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.bedrock_client import BedrockClient, BedrockInvocationError
from common.logging import get_logger, log_json
from common.response import json_response
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


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
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/chat"

    try:
        message = _parse_body(event)
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid chat request",
            request_id=request_id,
            path=path,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})

    started_at = perf_counter()

    try:
        answer = BedrockClient().converse(BEDROCK_MODEL_ID, message)
        latency_ms = int((perf_counter() - started_at) * 1000)

        trace_record = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "message": message,
            "answer_preview": answer[:500],
            "model_id": BEDROCK_MODEL_ID,
            "status": "completed",
            "latency_ms": latency_ms,
        }
        TraceRepository(TRACE_TABLE_NAME).save_trace(trace_record)

        log_json(
            LOGGER,
            logging.INFO,
            "chat request completed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
            latency_ms=latency_ms,
            status="completed",
        )

        return json_response(
            200,
            {
                "requestId": request_id,
                "answer": answer,
                "modelId": BEDROCK_MODEL_ID,
                "status": "completed",
            },
        )
    except BedrockInvocationError as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_json(
            LOGGER,
            logging.ERROR,
            "bedrock chat invocation failed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
            latency_ms=latency_ms,
            status="failed",
            error=str(exc),
        )
        return json_response(502, {"message": "Bedrock invocation failed."})
    except Exception:
        latency_ms = int((perf_counter() - started_at) * 1000)
        LOGGER.exception(
            "unexpected chat failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": path,
                    "model_id": BEDROCK_MODEL_ID,
                    "latency_ms": latency_ms,
                    "status": "failed",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})