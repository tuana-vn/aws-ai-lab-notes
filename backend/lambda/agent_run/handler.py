import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.approval_repository import ApprovalRepository
from common.agent import (
    ALLOWED_TOOLS,
    APPROVAL_REQUIRED_AGENT_MODE,
    ANSWER_QUESTION_TASK,
    INSPECT_TRACE_TASK,
    INVESTIGATE_RECENT_BLOCKS_TASK,
    PROPOSE_INCIDENT_REPORT_TASK,
    SEARCH_LOGS_TASK,
    READ_ONLY_AGENT_MODE,
    build_plan,
    build_tool_call,
)
from common.action_proposal import build_incident_report_proposal
from common.investigation import extract_request_ids_from_log_events, summarize_investigation
from common.log_search import SUPPORTED_PRESETS, search_logs
from common.logging import get_logger, log_json
from common.policy import resolve_access_context
from common.rag_service import normalize_filters, run_rag_query
from common.response import json_response
from common.trace_lookup import lookup_trace
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")
RAG_QUERY_LOG_GROUP_NAME = os.environ.get("RAG_QUERY_LOG_GROUP_NAME", "")
ACTION_APPROVALS_TABLE_NAME = os.environ.get("ACTION_APPROVALS_TABLE_NAME", "")


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

    if task == SEARCH_LOGS_TASK:
        preset = body.get("preset", "raw")
        if not isinstance(preset, str) or preset.strip() not in SUPPORTED_PRESETS:
            raise ValueError("Field 'preset' must be one of: raw, blocked, no_source, errors.")

        minutes = body.get("minutes", 60)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1 or minutes > 1440:
            raise ValueError("Field 'minutes' must be an integer between 1 and 1440.")

        return {
            "task": task,
            "preset": preset.strip(),
            "minutes": minutes,
        }

    if task == INVESTIGATE_RECENT_BLOCKS_TASK:
        minutes = body.get("minutes", 120)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1 or minutes > 1440:
            raise ValueError("Field 'minutes' must be an integer between 1 and 1440.")

        return {
            "task": task,
            "minutes": minutes,
        }

    if task == PROPOSE_INCIDENT_REPORT_TASK:
        minutes = body.get("minutes", 120)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1 or minutes > 1440:
            raise ValueError("Field 'minutes' must be an integer between 1 and 1440.")

        return {
            "task": task,
            "minutes": minutes,
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


def _save_search_logs_agent_trace(
    request_id,
    path,
    user_id,
    plan,
    tool_calls,
    preset,
    minutes,
    matched_events,
    status,
    latency_ms,
    answer_preview,
):
    trace_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "task": SEARCH_LOGS_TASK,
        "user_id": user_id,
        "agent_mode": READ_ONLY_AGENT_MODE,
        "plan": plan,
        "tool_calls": tool_calls,
        "log_search_preset": preset,
        "log_search_minutes": minutes,
        "matched_events": matched_events,
        "status": status,
        "latency_ms": latency_ms,
        "answer_preview": answer_preview[:500],
    }
    TraceRepository(TRACE_TABLE_NAME).save_trace(_serialize_trace_value(trace_record))


def _save_investigation_agent_trace(
    request_id,
    path,
    user_id,
    plan,
    tool_calls,
    minutes,
    matched_events,
    inspected_trace_count,
    inspected_trace_statuses,
    status,
    latency_ms,
    answer_preview,
):
    trace_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "task": INVESTIGATE_RECENT_BLOCKS_TASK,
        "user_id": user_id,
        "agent_mode": READ_ONLY_AGENT_MODE,
        "plan": plan,
        "tool_calls": tool_calls,
        "log_search_preset": "blocked",
        "log_search_minutes": minutes,
        "matched_events": matched_events,
        "inspected_trace_count": inspected_trace_count,
        "inspected_trace_statuses": inspected_trace_statuses,
        "status": status,
        "latency_ms": latency_ms,
        "answer_preview": answer_preview[:500],
    }
    TraceRepository(TRACE_TABLE_NAME).save_trace(_serialize_trace_value(trace_record))


def _save_proposed_action_agent_trace(
    request_id,
    path,
    user_id,
    plan,
    tool_calls,
    matched_events,
    inspected_trace_count,
    proposed_action,
    latency_ms,
    answer_preview,
):
    trace_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "task": PROPOSE_INCIDENT_REPORT_TASK,
        "user_id": user_id,
        "agent_mode": APPROVAL_REQUIRED_AGENT_MODE,
        "plan": plan,
        "tool_calls": tool_calls,
        "matched_events": matched_events,
        "inspected_trace_count": inspected_trace_count,
        "proposed_action_type": proposed_action.get("actionType"),
        "proposed_action_requires_approval": proposed_action.get("requiresApproval"),
        "proposed_action_severity": proposed_action.get("severity"),
        "execution_status": proposed_action.get("executionStatus"),
        "status": APPROVAL_REQUIRED_AGENT_MODE,
        "latency_ms": latency_ms,
        "answer_preview": answer_preview[:500],
    }
    TraceRepository(TRACE_TABLE_NAME).save_trace(_serialize_trace_value(trace_record))


def _create_pending_approval(request_id, task, proposed_action):
    approval_id = f"approval-{uuid4()}"
    approval_record = {
        "approval_id": approval_id,
        "request_id": request_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "proposed_action": proposed_action,
        "status": "pending_approval",
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "comment": None,
        "execution_status": "pending_approval",
    }
    ApprovalRepository(ACTION_APPROVALS_TABLE_NAME).create_approval(approval_record)
    return approval_id


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


def _build_investigation_trace_summary(target_request_id, trace_record):
    if trace_record is None:
        return {
            "targetRequestId": target_request_id,
            "status": "not_found",
        }

    return {
        "targetRequestId": target_request_id,
        "status": trace_record.get("status"),
        "guardrailAction": trace_record.get("guardrail_action"),
        "guardrailReason": trace_record.get("guardrail_reason"),
        "guardrailMatchedRule": trace_record.get("guardrail_matched_rule"),
    }


def _build_tool_call_with_metadata(tool_name: str, status: str, **extra_fields) -> dict:
    tool_call = build_tool_call(tool_name, status)
    tool_call.update(extra_fields)
    return tool_call


def _tool_is_allowlisted(tool_name):
    return tool_name in ALLOWED_TOOLS


def _run_bounded_blocked_investigation(minutes: int):
    search_result = search_logs(
        RAG_QUERY_LOG_GROUP_NAME,
        "blocked",
        minutes,
        limit=10,
    )
    candidate_request_ids = extract_request_ids_from_log_events(search_result["events"], limit=3)
    inspected_traces = []
    inspected_trace_statuses = []
    for target_request_id in candidate_request_ids:
        trace_record = lookup_trace(target_request_id, TRACE_TABLE_NAME)
        trace_summary = _build_investigation_trace_summary(target_request_id, trace_record)
        inspected_traces.append(trace_summary)
        inspected_trace_statuses.append(trace_summary["status"])

    tool_calls = [
        build_tool_call("log_search", "completed"),
        _build_tool_call_with_metadata(
            "trace_lookup",
            "completed",
            targetRequestCount=len(candidate_request_ids),
        ),
    ]
    log_summary = {
        "preset": search_result["preset"],
        "minutes": search_result["minutes"],
        "matchedEvents": search_result["matchedEvents"],
    }
    return {
        "logSummary": log_summary,
        "inspectedTraces": inspected_traces,
        "inspectedTraceStatuses": inspected_trace_statuses,
        "toolCalls": tool_calls,
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

    if payload["task"] == INSPECT_TRACE_TASK:
        if not _tool_is_allowlisted("trace_lookup"):
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

    if payload["task"] == INVESTIGATE_RECENT_BLOCKS_TASK:
        if not _tool_is_allowlisted("log_search"):
            log_json(
                LOGGER,
                logging.ERROR,
                "log search tool not allowlisted",
                request_id=request_id,
                path=path,
                user_id=user_id,
                task=payload["task"],
            )
            return json_response(500, {"message": "log_search tool is not configured."})

        if not _tool_is_allowlisted("trace_lookup"):
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

        if not RAG_QUERY_LOG_GROUP_NAME:
            return json_response(500, {"message": "RAG query log group is not configured."})

        investigation_result = _run_bounded_blocked_investigation(payload["minutes"])
        log_summary = investigation_result["logSummary"]
        inspected_traces = investigation_result["inspectedTraces"]
        inspected_trace_statuses = investigation_result["inspectedTraceStatuses"]
        tool_calls = investigation_result["toolCalls"]
        answer = summarize_investigation(log_summary, inspected_traces)
        response_body = {
            "requestId": request_id,
            "agentMode": READ_ONLY_AGENT_MODE,
            "task": payload["task"],
            "plan": plan,
            "toolCalls": tool_calls,
            "logSummary": log_summary,
            "inspectedTraces": inspected_traces,
            "answer": answer,
            "status": "completed",
        }
        latency_ms = int((perf_counter() - started_at) * 1000)
        _save_investigation_agent_trace(
            request_id,
            path,
            user_id,
            plan,
            tool_calls,
            log_summary["minutes"],
            log_summary["matchedEvents"],
            len(inspected_traces),
            inspected_trace_statuses,
            response_body["status"],
            latency_ms,
            answer,
        )
        log_json(
            LOGGER,
            logging.INFO,
            "agent recent block investigation completed",
            request_id=request_id,
            path=path,
            user_id=user_id,
            task=payload["task"],
            log_search_preset=log_summary["preset"],
            log_search_minutes=log_summary["minutes"],
            matched_events=log_summary["matchedEvents"],
            inspected_trace_count=len(inspected_traces),
            agent_mode=READ_ONLY_AGENT_MODE,
            tool_calls=tool_calls,
            status=response_body["status"],
            latency_ms=latency_ms,
        )
        return json_response(200, response_body)

    if payload["task"] == PROPOSE_INCIDENT_REPORT_TASK:
        if not _tool_is_allowlisted("log_search"):
            log_json(
                LOGGER,
                logging.ERROR,
                "log search tool not allowlisted",
                request_id=request_id,
                path=path,
                user_id=user_id,
                task=payload["task"],
            )
            return json_response(500, {"message": "log_search tool is not configured."})

        if not _tool_is_allowlisted("trace_lookup"):
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

        if not RAG_QUERY_LOG_GROUP_NAME:
            return json_response(500, {"message": "RAG query log group is not configured."})
        if not ACTION_APPROVALS_TABLE_NAME:
            return json_response(500, {"message": "Action approvals table is not configured."})

        investigation_result = _run_bounded_blocked_investigation(payload["minutes"])
        log_summary = investigation_result["logSummary"]
        inspected_traces = investigation_result["inspectedTraces"]
        tool_calls = investigation_result["toolCalls"]
        investigation_answer = summarize_investigation(log_summary, inspected_traces)
        proposed_action = build_incident_report_proposal(
            payload["minutes"],
            log_summary,
            inspected_traces,
            investigation_answer,
        )
        proposed_action["executionStatus"] = "pending_approval"
        approval_id = _create_pending_approval(request_id, payload["task"], proposed_action)
        answer = "I prepared an incident report proposal. It has not been executed and requires human approval."
        response_body = {
            "requestId": request_id,
            "agentMode": APPROVAL_REQUIRED_AGENT_MODE,
            "task": payload["task"],
            "approvalId": approval_id,
            "plan": plan,
            "toolCalls": tool_calls,
            "investigation": {
                "logSummary": log_summary,
                "inspectedTraces": inspected_traces,
                "answer": investigation_answer,
            },
            "proposedAction": proposed_action,
            "answer": answer,
            "status": APPROVAL_REQUIRED_AGENT_MODE,
        }
        latency_ms = int((perf_counter() - started_at) * 1000)
        _save_proposed_action_agent_trace(
            request_id,
            path,
            user_id,
            plan,
            tool_calls,
            log_summary["matchedEvents"],
            len(inspected_traces),
            proposed_action,
            latency_ms,
            answer,
        )
        log_json(
            LOGGER,
            logging.INFO,
            "agent incident report proposal prepared",
            request_id=request_id,
            path=path,
            user_id=user_id,
            task=payload["task"],
            approval_id=approval_id,
            matched_events=log_summary["matchedEvents"],
            inspected_trace_count=len(inspected_traces),
            proposed_action_type=proposed_action["actionType"],
            proposed_action_requires_approval=proposed_action["requiresApproval"],
            proposed_action_severity=proposed_action["severity"],
            execution_status=proposed_action["executionStatus"],
            agent_mode=APPROVAL_REQUIRED_AGENT_MODE,
            tool_calls=tool_calls,
            status=response_body["status"],
            latency_ms=latency_ms,
        )
        return json_response(200, response_body)

    if not _tool_is_allowlisted("log_search"):
        log_json(
            LOGGER,
            logging.ERROR,
            "log search tool not allowlisted",
            request_id=request_id,
            path=path,
            user_id=user_id,
            task=payload["task"],
        )
        return json_response(500, {"message": "log_search tool is not configured."})

    if not RAG_QUERY_LOG_GROUP_NAME:
        return json_response(500, {"message": "RAG query log group is not configured."})

    search_result = search_logs(
        RAG_QUERY_LOG_GROUP_NAME,
        payload["preset"],
        payload["minutes"],
        limit=10,
    )
    tool_calls = [build_tool_call("log_search", "completed")]
    answer = (
        f"Found {search_result['matchedEvents']} matching log event(s) for preset "
        f"{search_result['preset']} in the last {search_result['minutes']} minutes."
    )
    response_body = {
        "requestId": request_id,
        "agentMode": READ_ONLY_AGENT_MODE,
        "task": payload["task"],
        "plan": plan,
        "toolCalls": tool_calls,
        "logSummary": {
            "preset": search_result["preset"],
            "minutes": search_result["minutes"],
            "matchedEvents": search_result["matchedEvents"],
        },
        "events": search_result["events"],
        "answer": answer,
        "status": "completed",
    }
    latency_ms = int((perf_counter() - started_at) * 1000)
    _save_search_logs_agent_trace(
        request_id,
        path,
        user_id,
        plan,
        tool_calls,
        search_result["preset"],
        search_result["minutes"],
        search_result["matchedEvents"],
        response_body["status"],
        latency_ms,
        answer,
    )
    log_json(
        LOGGER,
        logging.INFO,
        "agent log search completed",
        request_id=request_id,
        path=path,
        user_id=user_id,
        task=payload["task"],
        log_search_preset=search_result["preset"],
        log_search_minutes=search_result["minutes"],
        matched_events=search_result["matchedEvents"],
        agent_mode=READ_ONLY_AGENT_MODE,
        tool_calls=tool_calls,
        status=response_body["status"],
        latency_ms=latency_ms,
    )
    return json_response(200, response_body)