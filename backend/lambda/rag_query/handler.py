import logging
import json
from uuid import uuid4

from common.logging import get_logger, log_json
from common.rag_service import normalize_filters, run_rag_query
from common.response import json_response

LOGGER = get_logger(__name__)


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

    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Field 'question' is required and must be a non-empty string.")

    return {
        "question": question.strip(),
        "filters": normalize_filters(body.get("filters", {})),
    }


def lambda_handler(event, context):
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/rag/query"

    try:
        request_payload = _parse_body(event)
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid rag query request",
            request_id=request_id,
            path=path,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})

    result = run_rag_query(
        request_payload["question"],
        request_payload["filters"],
        event,
        request_id,
        path,
    )
    return json_response(result["statusCode"], result["body"])