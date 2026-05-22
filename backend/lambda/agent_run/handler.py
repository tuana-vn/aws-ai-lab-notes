import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.agent import (
    ALLOWED_TOOLS,
    ANSWER_QUESTION_TASK,
    INSPECT_TRACE_TASK,
    READ_ONLY_AGENT_MODE,
    build_plan,
    build_tool_call,
)
from common.logging import get_logger, log_json
from common.policy import resolve_access_context
from common.rag_service import normalize_filters, run_rag_query
from common.response import json_response
from common.trace_lookup import lookup_trace
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")


def _serialize_trace_value(value):
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        return [_serialize_trace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_trace_value(item) for key, item in value.items()}
    return value


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
    if task == ANSWER_QUESTION_TASK:
        question = body.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Field 'question' is required and must be a non-empty string.")

        return {
            "task": task,
            "question": question.strip(),
            "filters": normalize_filters(body.get("filters", {})),
        }

    if task == INSPECT_TRACE_TASK:
        target_request_id = body.get("requestId")
        if not isinstance(target_request_id, str) or not target_request_id.strip():
            raise ValueError("Field 'requestId' is required and must be a non-empty string.")

        return {
            "task": task,
            "requestId": target_request_id.strip(),
        }

    raise ValueError("Unsupported agent task.")


def _save_agent_trace(request_id, path, task, user_id, question, filters, plan, tool_calls, status, latency_ms, answer_preview):
    trace_record = {
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
    TraceRepository(TRACE_TABLE_NAME).save_trace(_serialize_trace_value(trace_record))


def _save_inspect_trace_agent_trace(
    request_id,
    path,
    user_id,
    target_request_id,
    plan,
    tool_calls,
    status,
    latency_ms,
    answer_preview,
):
    trace_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "task": INSPECT_TRACE_TASK,
        "user_id": user_id,
        "target_request_id": target_request_id,
        "agent_mode": READ_ONLY_AGENT_MODE,
        "plan": plan,
        "tool_calls": tool_calls,
        "status": status,
        "latency_ms": latency_ms,
        "answer_preview": answer_preview[:500],
    }
    TraceRepository(TRACE_TABLE_NAME).save_trace(_serialize_trace_value(trace_record))


def _summarize_trace_result(trace_record):
    status = trace_record.get("status")
    if status == "blocked":
        matched_rule = trace_record.get("guardrail_matched_rule") or "unknown"
        return f"The request was blocked by the input guardrail because it matched rule {matched_rule}."
    if status == "no_source":
        return "The request completed with no source because no eligible chunk passed retrieval."
    if status == "completed":
        source_count = int(trace_record.get("source_count", 0) or 0)
        return f"The request completed successfully with {source_count} source(s)."
    return f"The trace record was found with status {status}."


def _build_trace_summary(target_request_id, trace_record):
    return {
        "targetRequestId": target_request_id,
        "path": trace_record.get("path"),
        "userId": trace_record.get("user_id"),
        "status": trace_record.get("status"),
        "question": trace_record.get("question"),
        "guardrailAction": trace_record.get("guardrail_action"),
        "guardrailReason": trace_record.get("guardrail_reason"),
        "guardrailMatchedRule": trace_record.get("guardrail_matched_rule"),
        "outputGuardrailAction": trace_record.get("output_guardrail_action"),
        "outputGuardrailReason": trace_record.get("output_guardrail_reason"),
        "retrievalMode": trace_record.get("retrieval_mode"),
        "sourceCount": int(trace_record.get("source_count", 0) or 0),
        "eligibleChunkCount": int(trace_record.get("eligible_chunk_count", 0) or 0),
        "latencyMs": int(trace_record.get("latency_ms", 0) or 0),
        "answerPreview": trace_record.get("answer_preview"),
    }


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
    plan = build_plan(payload["task"])
    user_id = resolve_access_context(event)["user_id"]

    if payload["task"] == ANSWER_QUESTION_TASK:
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

        tool_calls = [build_tool_call("rag_query", rag_body.get("status", "completed"))]
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

    if "trace_lookup" not in ALLOWED_TOOLS:
        log_json(
            LOGGER,
            logging.ERROR,
            "trace lookup tool not allowlisted",
            request_id=request_id,
            path=path,
            user_id=user_id,
            task=payload["task"],
        )
        return json_response(500, {"message": "trace_lookup tool is not configured."})

    trace_record = lookup_trace(payload["requestId"], TRACE_TABLE_NAME)
    if trace_record is None:
        tool_calls = [build_tool_call("trace_lookup", "not_found")]
        answer = "No trace record was found for the provided requestId."
        latency_ms = int((perf_counter() - started_at) * 1000)
        _save_inspect_trace_agent_trace(
            request_id,
            path,
            user_id,
            payload["requestId"],
            plan,
            tool_calls,
            "not_found",
            latency_ms,
            answer,
        )
        return json_response(
            404,
            {
                "requestId": request_id,
                "agentMode": READ_ONLY_AGENT_MODE,
                "task": payload["task"],
                "toolCalls": tool_calls,
                "answer": answer,
                "status": "not_found",
            },
        )

    tool_calls = [build_tool_call("trace_lookup", "completed")]
    trace_summary = _build_trace_summary(payload["requestId"], trace_record)
    answer = _summarize_trace_result(trace_record)
    response_body = {
        "requestId": request_id,
        "agentMode": READ_ONLY_AGENT_MODE,
        "task": payload["task"],
        "plan": plan,
        "toolCalls": tool_calls,
        "trace": trace_summary,
        "answer": answer,
        "status": "completed",
    }
    latency_ms = int((perf_counter() - started_at) * 1000)
    _save_inspect_trace_agent_trace(
        request_id,
        path,
        user_id,
        payload["requestId"],
        plan,
        tool_calls,
        "completed",
        latency_ms,
        answer,
    )

    log_json(
        LOGGER,
        logging.INFO,
        "agent trace inspection completed",
        request_id=request_id,
        path=path,
        user_id=user_id,
        task=payload["task"],
        target_request_id=payload["requestId"],
        agent_mode=READ_ONLY_AGENT_MODE,
        tool_calls=tool_calls,
        status=response_body["status"],
        latency_ms=latency_ms,
    )
    return json_response(200, response_body)