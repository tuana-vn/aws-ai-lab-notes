import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.agent import ALLOWED_TOOLS, ANSWER_QUESTION_TASK, READ_ONLY_AGENT_MODE, READ_ONLY_PLAN, build_tool_call
from common.logging import get_logger, log_json
from common.policy import resolve_access_context
from common.rag_service import normalize_filters, run_rag_query
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

    task = body.get("task")
    question = body.get("question")
    if task != ANSWER_QUESTION_TASK:
        raise ValueError("Unsupported agent task.")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Field 'question' is required and must be a non-empty string.")

    return {
        "task": task,
        "question": question.strip(),
        "filters": normalize_filters(body.get("filters", {})),
    }


def _save_agent_trace(request_id, path, task, user_id, question, filters, plan, tool_calls, status, latency_ms, answer_preview):
    TraceRepository(TRACE_TABLE_NAME).save_trace(
        {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "task": task,
            "user_id": user_id,
            "question": question,
            "filters": filters,
            "agent_mode": READ_ONLY_AGENT_MODE,
            "plan": plan,
            "tool_calls": tool_calls,
            "status": status,
            "latency_ms": latency_ms,
            "answer_preview": answer_preview[:500],
        }
    )


def lambda_handler(event, context):
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/agent/run"

    try:
        payload = _parse_body(event)
    except ValueError as exc:
        status_code = 400 if str(exc) != "Unsupported agent task." else 400
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid agent run request",
            request_id=request_id,
            path=path,
            error=str(exc),
        )
        return json_response(status_code, {"message": str(exc)})

    started_at = perf_counter()
    plan = list(READ_ONLY_PLAN)
    tool_calls = []
    user_id = resolve_access_context(event)["user_id"]

    rag_result = run_rag_query(
        payload["question"],
        payload["filters"],
        event,
        request_id,
        path,
        save_trace=False,
    )
    status_code = rag_result["statusCode"]
    rag_body = rag_result["body"]

    if status_code == 403:
        latency_ms = int((perf_counter() - started_at) * 1000)
        _save_agent_trace(
            request_id,
            path,
            payload["task"],
            user_id,
            payload["question"],
            payload["filters"],
            plan,
            [],
            "denied",
            latency_ms,
            rag_body.get("message", ""),
        )
        return json_response(status_code, rag_body)

    tool_calls = [build_tool_call(ALLOWED_TOOLS[0], rag_body.get("status", "completed"))]
    response_body = {
        "requestId": request_id,
        "agentMode": READ_ONLY_AGENT_MODE,
        "task": payload["task"],
        "plan": plan,
        "toolCalls": tool_calls,
        "answer": rag_body.get("answer"),
        "sources": rag_body.get("sources", []),
        "guardrail": rag_body.get("guardrail"),
        "outputGuardrail": rag_body.get("outputGuardrail"),
        "status": rag_body.get("status"),
    }

    latency_ms = int((perf_counter() - started_at) * 1000)
    _save_agent_trace(
        request_id,
        path,
        payload["task"],
        user_id,
        payload["question"],
        payload["filters"],
        plan,
        tool_calls,
        response_body["status"],
        latency_ms,
        response_body.get("answer", ""),
    )

    log_json(
        LOGGER,
        logging.INFO,
        "agent run completed",
        request_id=request_id,
        path=path,
        user_id=user_id,
        task=payload["task"],
        agent_mode=READ_ONLY_AGENT_MODE,
        tool_calls=tool_calls,
        status=response_body["status"],
        latency_ms=latency_ms,
    )
    return json_response(status_code, response_body)