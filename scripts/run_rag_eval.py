import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


DOCUMENT_PATH = Path("test-data/rag-evaluation/documents/api-gateway-note.json")
QUESTIONS_PATH = Path("test-data/rag-evaluation/questions.json")
REPORTS_DIR = Path("reports")
RAW_RESULTS_PATH = REPORTS_DIR / "rag-eval-results.json"
MARKDOWN_REPORT_PATH = REPORTS_DIR / "rag-eval-report.md"
NO_ANSWER_TEXT = "I do not know based on the available documents"
DEFAULT_REQUEST_HEADERS = {
    "X-User-Id": "user-learning",
    "X-Allowed-Project-Ids": "learning",
    "X-Allowed-Customer-Ids": "internal",
}


def _require_api_base_url():
    api_base_url = os.environ.get("API_BASE_URL", "").strip()
    if not api_base_url:
        raise SystemExit("API_BASE_URL environment variable is required.")

    return api_base_url.rstrip("/")


def _load_json(path):
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _get_authorization_header():
    authorization_header = os.environ.get("AUTHORIZATION_HEADER", "").strip()
    if authorization_header:
        return authorization_header

    auth_token = os.environ.get("AUTH_TOKEN", "").strip()
    if auth_token:
        return f"Bearer {auth_token}"

    return ""


def _apply_authorization_header(headers=None):
    request_headers = dict(headers or {})
    authorization_header = _get_authorization_header()
    if authorization_header:
        request_headers["Authorization"] = authorization_header

    return request_headers


def _post_json(url, payload, headers=None):
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if isinstance(headers, dict):
        request_headers.update(headers)

    http_request = request.Request(
        url,
        data=body,
        headers=request_headers,
        method="POST",
    )

    try:
        with request.urlopen(http_request) as http_response:
            response_text = http_response.read().decode("utf-8")
            response_body = json.loads(response_text) if response_text else {}
            return {
                "httpStatusCode": http_response.getcode(),
                "body": response_body,
            }
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8")
        try:
            response_body = json.loads(response_text) if response_text else {}
        except json.JSONDecodeError:
            response_body = {"rawBody": response_text}

        return {
            "httpStatusCode": exc.code,
            "body": response_body,
        }


def _get_json(url, headers=None):
    request_headers = {"Content-Type": "application/json"}
    if isinstance(headers, dict):
        request_headers.update(headers)

    http_request = request.Request(url, headers=request_headers, method="GET")

    try:
        with request.urlopen(http_request) as http_response:
            response_text = http_response.read().decode("utf-8")
            response_body = json.loads(response_text) if response_text else {}
            return {
                "httpStatusCode": http_response.getcode(),
                "body": response_body,
            }
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8")
        try:
            response_body = json.loads(response_text) if response_text else {}
        except json.JSONDecodeError:
            response_body = {"rawBody": response_text}

        return {
            "httpStatusCode": exc.code,
            "body": response_body,
        }


def _normalize_text(value):
    if not isinstance(value, str):
        return ""

    return value.casefold()


def _extract_source_document_ids(response_body):
    source_document_ids = []
    for source in response_body.get("sources", []):
        if isinstance(source, dict):
            document_id = source.get("documentId")
            if isinstance(document_id, str):
                source_document_ids.append(document_id)

    return source_document_ids


def _format_source_summaries(response_body):
    source_summaries = []
    for source in response_body.get("sources", []):
        if not isinstance(source, dict):
            continue

        document_id = source.get("documentId", "-")
        similarity = source.get("similarity")
        if similarity is None:
            source_summaries.append(str(document_id))
            continue

        source_summaries.append(f"{document_id} ({similarity})")

    return source_summaries


def _format_filters_for_markdown(response_body):
    filters = response_body.get("filters", {})
    if not isinstance(filters, dict) or not filters:
        return "-"

    return ", ".join(f"{key}={value}" for key, value in filters.items())


def _format_output_guardrail_for_markdown(response_body):
    output_guardrail = response_body.get("outputGuardrail", {})
    if not isinstance(output_guardrail, dict) or not output_guardrail:
        return "-"

    warnings = output_guardrail.get("warnings", [])
    warnings_text = ", ".join(str(item) for item in warnings) if warnings else "-"
    return (
        f"action={output_guardrail.get('action', '-')}, "
        f"reason={output_guardrail.get('reason', '-')}, "
        f"warnings={warnings_text}"
    )


def _answer_contains_any_keyword(answer, keywords):
    normalized_answer = _normalize_text(answer)
    for keyword in keywords:
        if _normalize_text(keyword) in normalized_answer:
            return True

    return False


def _evaluate_case(case_definition, response):
    response_body = response.get("body", {})
    response_status = response_body.get("status")
    answer = response_body.get("answer", "")
    source_document_ids = _extract_source_document_ids(response_body)
    notes = []
    case_type = case_definition.get("type")
    expected_http_status_code = case_definition.get("expectedHttpStatusCode", 200)

    if response.get("httpStatusCode") != expected_http_status_code:
        notes.append(
            f"expected HTTP {expected_http_status_code} but got {response.get('httpStatusCode')}"
        )

    if case_type in {"in_source", "semantic", "output_guardrail_observation", "agent_answer_question"}:
        expected_status = case_definition.get("expectedStatus")
        expected_document_id = case_definition.get("expectedDocumentId")
        expected_keywords = case_definition.get("expectedAnswerKeywords", [])

        status_matches = response_status == expected_status
        has_expected_source = expected_document_id in source_document_ids
        has_expected_keyword = _answer_contains_any_keyword(answer, expected_keywords)

        agent_mode = response_body.get("agentMode")
        task = response_body.get("task")
        tool_calls = response_body.get("toolCalls", [])
        has_rag_tool_call = any(
            isinstance(tool_call, dict)
            and tool_call.get("toolName") == "rag_query"
            and tool_call.get("readOnly") is True
            for tool_call in tool_calls
        )

        if not status_matches:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if not has_expected_source:
            notes.append(f"expected source '{expected_document_id}' not found")
        if expected_keywords and not has_expected_keyword:
            notes.append("answer did not contain any expected keyword")
        if case_type == "agent_answer_question" and agent_mode != "read_only":
            notes.append(f"expected agentMode 'read_only' but got '{agent_mode}'")
        if case_type == "agent_answer_question" and task != case_definition.get("task"):
            notes.append(f"expected task '{case_definition.get('task')}' but got '{task}'")
        if case_type == "agent_answer_question" and not has_rag_tool_call:
            notes.append("expected read-only rag_query tool call not found")

        passed = status_matches and has_expected_source and (
            has_expected_keyword if expected_keywords else True
        )
        if case_type == "agent_answer_question":
            passed = passed and agent_mode == "read_only" and task == case_definition.get("task") and has_rag_tool_call
    elif case_type == "agent_inspect_trace":
        expected_status = case_definition.get("expectedStatus")
        expected_tool_name = case_definition.get("expectedToolName")
        expected_trace_status = case_definition.get("expectedTraceStatus")
        tool_calls = response_body.get("toolCalls", [])
        trace = response_body.get("trace", {})

        has_expected_tool = any(
            isinstance(tool_call, dict) and tool_call.get("toolName") == expected_tool_name
            for tool_call in tool_calls
        )
        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if not has_expected_tool:
            notes.append(f"expected tool '{expected_tool_name}' not found")
        if trace.get("status") != expected_trace_status:
            notes.append(
                f"expected trace.status '{expected_trace_status}' but got '{trace.get('status')}'"
            )

        passed = (
            response_status == expected_status
            and has_expected_tool
            and trace.get("status") == expected_trace_status
        )
    elif case_type == "agent_search_logs":
        expected_status = case_definition.get("expectedStatus")
        expected_tool_name = case_definition.get("expectedToolName")
        expected_preset = case_definition.get("preset")
        tool_calls = response_body.get("toolCalls", [])
        log_summary = response_body.get("logSummary", {})

        has_expected_tool = any(
            isinstance(tool_call, dict) and tool_call.get("toolName") == expected_tool_name
            for tool_call in tool_calls
        )
        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if not has_expected_tool:
            notes.append(f"expected tool '{expected_tool_name}' not found")
        if log_summary.get("preset") != expected_preset:
            notes.append(f"expected logSummary.preset '{expected_preset}' but got '{log_summary.get('preset')}'")
        if "matchedEvents" not in log_summary:
            notes.append("expected logSummary.matchedEvents to exist")

        passed = (
            response_status == expected_status
            and has_expected_tool
            and log_summary.get("preset") == expected_preset
            and "matchedEvents" in log_summary
        )
    elif case_type == "agent_investigate_recent_blocks":
        expected_status = case_definition.get("expectedStatus")
        expected_tool_names = case_definition.get("expectedToolNames", [])
        tool_calls = response_body.get("toolCalls", [])
        log_summary = response_body.get("logSummary", {})
        inspected_traces = response_body.get("inspectedTraces")

        tool_names = {
            tool_call.get("toolName")
            for tool_call in tool_calls
            if isinstance(tool_call, dict)
        }
        missing_tool_names = [tool_name for tool_name in expected_tool_names if tool_name not in tool_names]
        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if missing_tool_names:
            notes.append(f"expected tools not found: {', '.join(missing_tool_names)}")
        if "matchedEvents" not in log_summary:
            notes.append("expected logSummary.matchedEvents to exist")
        if not isinstance(inspected_traces, list):
            notes.append("expected inspectedTraces to exist")

        passed = (
            response_status == expected_status
            and not missing_tool_names
            and "matchedEvents" in log_summary
            and isinstance(inspected_traces, list)
        )
    elif case_type == "agent_propose_incident_report":
        expected_status = case_definition.get("expectedStatus")
        expected_action_type = case_definition.get("expectedActionType")
        expected_requires_approval = case_definition.get("expectedRequiresApproval")
        expected_execution_status = case_definition.get("expectedExecutionStatus")
        tool_calls = response_body.get("toolCalls", [])
        proposed_action = response_body.get("proposedAction", {})

        tool_names = {
            tool_call.get("toolName")
            for tool_call in tool_calls
            if isinstance(tool_call, dict)
        }
        missing_tool_names = [tool_name for tool_name in ["log_search", "trace_lookup"] if tool_name not in tool_names]
        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if missing_tool_names:
            notes.append(f"expected tools not found: {', '.join(missing_tool_names)}")
        if proposed_action.get("actionType") != expected_action_type:
            notes.append(
                f"expected proposedAction.actionType '{expected_action_type}' but got '{proposed_action.get('actionType')}'"
            )
        if proposed_action.get("requiresApproval") is not expected_requires_approval:
            notes.append(
                f"expected proposedAction.requiresApproval '{expected_requires_approval}' but got '{proposed_action.get('requiresApproval')}'"
            )
        if proposed_action.get("executionStatus") != expected_execution_status:
            notes.append(
                f"expected proposedAction.executionStatus '{expected_execution_status}' but got '{proposed_action.get('executionStatus')}'"
            )

        passed = (
            response_status == expected_status
            and not missing_tool_names
            and proposed_action.get("actionType") == expected_action_type
            and proposed_action.get("requiresApproval") is expected_requires_approval
            and proposed_action.get("executionStatus") == expected_execution_status
        )
    elif case_type == "approval_workflow":
        expected_initial_status = case_definition.get("expectedInitialStatus")
        expected_approval_status = case_definition.get("expectedApprovalStatus")
        expected_execution_status = case_definition.get("expectedExecutionStatus")
        proposed_action = response_body.get("proposedAction", {})
        approval_record = response_body.get("approvalRecord", {})
        decision_result = response_body.get("decisionResult", {})
        approval_id = response_body.get("approvalId")
        approval_get_http_status_code = response.get("approvalGetHttpStatusCode")
        approval_decision_http_status_code = response.get("approvalDecisionHttpStatusCode")

        if response_status != expected_initial_status:
            notes.append(f"expected initial status '{expected_initial_status}' but got '{response_status}'")
        if not approval_id:
            notes.append("expected approvalId to exist")
        if approval_get_http_status_code != 200:
            notes.append(f"expected approval GET HTTP 200 but got {approval_get_http_status_code}")
        if approval_decision_http_status_code != 200:
            notes.append(f"expected approval decision HTTP 200 but got {approval_decision_http_status_code}")
        if approval_record.get("status") != "pending_approval":
            notes.append(f"expected approval record status 'pending_approval' but got '{approval_record.get('status')}'")
        if proposed_action.get("executionStatus") != "pending_approval":
            notes.append(
                f"expected proposedAction.executionStatus 'pending_approval' but got '{proposed_action.get('executionStatus')}'"
            )
        if decision_result.get("status") != expected_approval_status:
            notes.append(
                f"expected approval decision status '{expected_approval_status}' but got '{decision_result.get('status')}'"
            )
        if decision_result.get("executionStatus") != expected_execution_status:
            notes.append(
                f"expected execution status '{expected_execution_status}' but got '{decision_result.get('executionStatus')}'"
            )

        passed = (
            response_status == expected_initial_status
            and bool(approval_id)
            and approval_get_http_status_code == 200
            and approval_decision_http_status_code == 200
            and approval_record.get("status") == "pending_approval"
            and proposed_action.get("executionStatus") == "pending_approval"
            and decision_result.get("status") == expected_approval_status
            and decision_result.get("executionStatus") == expected_execution_status
        )
    elif case_type == "approval_execute_internal_report":
        expected_approval_status = case_definition.get("expectedApprovalStatus")
        expected_execution_status_after_decision = case_definition.get("expectedExecutionStatusAfterDecision")
        expected_execution_status_after_execute = case_definition.get("expectedExecutionStatusAfterExecute")
        expected_report_status = case_definition.get("expectedReportStatus")
        decision_result = response_body.get("decisionResult", {})
        execute_result = response_body.get("executeResult", {})
        report_record = response_body.get("reportRecord", {})
        approval_id = response_body.get("approvalId")
        report_id = execute_result.get("reportId")
        approval_decision_http_status_code = response.get("approvalDecisionHttpStatusCode")
        approval_execute_http_status_code = response.get("approvalExecuteHttpStatusCode")
        report_get_http_status_code = response.get("reportGetHttpStatusCode")

        if not approval_id:
            notes.append("expected approvalId to exist")
        if approval_decision_http_status_code != 200:
            notes.append(f"expected approval decision HTTP 200 but got {approval_decision_http_status_code}")
        if approval_execute_http_status_code != 200:
            notes.append(f"expected approval execute HTTP 200 but got {approval_execute_http_status_code}")
        if report_get_http_status_code != 200:
            notes.append(f"expected incident report GET HTTP 200 but got {report_get_http_status_code}")
        if decision_result.get("status") != expected_approval_status:
            notes.append(
                f"expected approval decision status '{expected_approval_status}' but got '{decision_result.get('status')}'"
            )
        if decision_result.get("executionStatus") != expected_execution_status_after_decision:
            notes.append(
                "expected execution status after decision "
                f"'{expected_execution_status_after_decision}' but got '{decision_result.get('executionStatus')}'"
            )
        if execute_result.get("status") != "executed":
            notes.append(f"expected execute response status 'executed' but got '{execute_result.get('status')}'")
        if execute_result.get("executionStatus") != expected_execution_status_after_execute:
            notes.append(
                "expected execution status after execute "
                f"'{expected_execution_status_after_execute}' but got '{execute_result.get('executionStatus')}'"
            )
        if not report_id:
            notes.append("expected reportId to exist")
        if report_record.get("status") != expected_report_status:
            notes.append(f"expected report status '{expected_report_status}' but got '{report_record.get('status')}'")
        if report_record.get("approval_id") != approval_id:
            notes.append(
                f"expected report approval_id '{approval_id}' but got '{report_record.get('approval_id')}'"
            )

        passed = (
            bool(approval_id)
            and approval_decision_http_status_code == 200
            and approval_execute_http_status_code == 200
            and report_get_http_status_code == 200
            and decision_result.get("status") == expected_approval_status
            and decision_result.get("executionStatus") == expected_execution_status_after_decision
            and execute_result.get("status") == "executed"
            and execute_result.get("executionStatus") == expected_execution_status_after_execute
            and bool(report_id)
            and report_record.get("status") == expected_report_status
            and report_record.get("approval_id") == approval_id
        )
    elif case_type in {"out_of_source", "metadata_boundary"}:
        normalized_answer = _normalize_text(answer)
        no_answer_detected = NO_ANSWER_TEXT.casefold() in normalized_answer
        expected_status = case_definition.get("expectedStatus", "no_source")
        no_source_status = response_status == expected_status
        no_sources_returned = not source_document_ids
        expected_sources_empty = case_definition.get("expectedSourcesEmpty", True)

        if not no_answer_detected:
            notes.append("response did not refuse the out-of-source question")
        if not no_source_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if expected_sources_empty and not no_sources_returned:
            notes.append("expected sources to be empty for no-source case")

        passed = no_answer_detected and no_source_status and (
            no_sources_returned if expected_sources_empty else True
        )
    elif case_type == "policy_denied":
        expected_error_message = case_definition.get("expectedErrorMessage", "")
        actual_message = response_body.get("message", "")
        has_expected_error = _normalize_text(expected_error_message) in _normalize_text(actual_message)
        answer_generated = "answer" in response_body and bool(response_body.get("answer"))

        if not has_expected_error:
            notes.append("response did not contain the expected access denied message")
        if answer_generated:
            notes.append("expected no answer to be generated for denied request")

        passed = has_expected_error and not answer_generated
    elif case_type == "guardrail_blocked":
        expected_status = case_definition.get("expectedStatus", "blocked")
        expected_guardrail_action = case_definition.get("expectedGuardrailAction", "block")
        expected_keywords = case_definition.get("expectedAnswerKeywords", [])
        guardrail = response_body.get("guardrail", {})
        guardrail_action = guardrail.get("action")
        has_expected_keyword = _answer_contains_any_keyword(answer, expected_keywords)
        sources_empty = not source_document_ids

        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if guardrail_action != expected_guardrail_action:
            notes.append(
                f"expected guardrail action '{expected_guardrail_action}' but got '{guardrail_action}'"
            )
        if not has_expected_keyword:
            notes.append("blocked answer did not contain any expected keyword")
        if not sources_empty:
            notes.append("expected sources to be empty for blocked request")

        passed = (
            response_status == expected_status
            and guardrail_action == expected_guardrail_action
            and has_expected_keyword
            and sources_empty
        )
    else:
        notes.append(f"unsupported case type '{case_type}'")
        passed = False

    if response.get("httpStatusCode", 0) >= 400 and case_type != "policy_denied":
        notes.append(f"HTTP {response['httpStatusCode']}")
        passed = False

    if response.get("httpStatusCode") != expected_http_status_code:
        passed = False

    return {
        "caseId": case_definition.get("caseId"),
        "type": case_type,
        "question": case_definition.get("question"),
        "expected": case_definition,
        "response": response,
        "pass": passed,
        "notes": "; ".join(notes) if notes else "OK",
    }


def _format_sources_for_markdown(response_body):
    source_summaries = _format_source_summaries(response_body)
    if not source_summaries:
        return "-"

    return ", ".join(source_summaries)


def _answer_snippet(answer, limit=240):
    compact_answer = " ".join(str(answer).split())
    if len(compact_answer) <= limit:
        return compact_answer

    return compact_answer[: limit - 3] + "..."


def _write_json_report(results_payload):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_RESULTS_PATH.open("w", encoding="utf-8") as file_handle:
        json.dump(results_payload, file_handle, indent=2)


def _get_case_request_id(results_by_case_id, case_id):
    result = results_by_case_id.get(case_id, {})
    response_body = result.get("response", {}).get("body", {})
    request_id = response_body.get("requestId")
    return request_id if isinstance(request_id, str) else ""


def _build_request_payload(case_definition, results_by_case_id):
    task = case_definition.get("task")
    if case_definition.get("type") == "agent_inspect_trace":
        return {
            "task": task,
            "requestId": _get_case_request_id(results_by_case_id, case_definition.get("targetCaseId")),
        }

    if case_definition.get("type") == "agent_search_logs":
        return {
            "task": task,
            "preset": case_definition.get("preset", "raw"),
            "minutes": case_definition.get("minutes", 60),
        }

    if case_definition.get("type") == "agent_investigate_recent_blocks":
        return {
            "task": task,
            "minutes": case_definition.get("minutes", 120),
        }

    if case_definition.get("type") == "agent_propose_incident_report":
        return {
            "task": task,
            "minutes": case_definition.get("minutes", 120),
        }

    if case_definition.get("type") == "approval_workflow":
        return {
            "task": task,
            "minutes": case_definition.get("minutes", 120),
        }

    if case_definition.get("type") == "approval_execute_internal_report":
        return {
            "task": task,
            "minutes": case_definition.get("minutes", 120),
        }

    payload = {"question": case_definition.get("question", "")}
    if isinstance(case_definition.get("filters"), dict):
        payload["filters"] = case_definition["filters"]
    if isinstance(task, str) and task.strip():
        payload["task"] = task.strip()
    return payload


def _run_approval_workflow_case(api_base_url, case_definition, request_headers):
    initial_payload = _build_request_payload(case_definition, {})
    initial_response = _post_json(
        f"{api_base_url}{case_definition.get('endpoint', '/agent/run')}",
        initial_payload,
        headers=request_headers,
    )
    initial_body = initial_response.get("body", {})
    approval_id = initial_body.get("approvalId")

    if not isinstance(approval_id, str) or not approval_id:
        return {
            "httpStatusCode": initial_response.get("httpStatusCode"),
            "body": {
                **initial_body,
                "approvalRecord": {},
                "decisionResult": {},
            },
            "approvalGetHttpStatusCode": None,
            "approvalDecisionHttpStatusCode": None,
        }

    approval_get_response = _get_json(
        f"{api_base_url}/approvals/{approval_id}",
        headers=request_headers,
    )
    approval_decision_response = _post_json(
        f"{api_base_url}/approvals/{approval_id}/decision",
        {
            "decision": case_definition.get("approvalDecision"),
            "decidedBy": case_definition.get("decidedBy"),
            "comment": case_definition.get("comment"),
        },
        headers=request_headers,
    )

    return {
        "httpStatusCode": initial_response.get("httpStatusCode"),
        "body": {
            **initial_body,
            "approvalRecord": approval_get_response.get("body", {}),
            "decisionResult": approval_decision_response.get("body", {}),
        },
        "approvalGetHttpStatusCode": approval_get_response.get("httpStatusCode"),
        "approvalDecisionHttpStatusCode": approval_decision_response.get("httpStatusCode"),
    }


def _run_approval_execute_internal_report_case(api_base_url, case_definition, request_headers):
    initial_payload = _build_request_payload(case_definition, {})
    initial_response = _post_json(
        f"{api_base_url}{case_definition.get('endpoint', '/agent/run')}",
        initial_payload,
        headers=request_headers,
    )
    initial_body = initial_response.get("body", {})
    approval_id = initial_body.get("approvalId")

    if not isinstance(approval_id, str) or not approval_id:
        return {
            "httpStatusCode": initial_response.get("httpStatusCode"),
            "body": {
                **initial_body,
                "decisionResult": {},
                "executeResult": {},
                "reportRecord": {},
            },
            "approvalDecisionHttpStatusCode": None,
            "approvalExecuteHttpStatusCode": None,
            "reportGetHttpStatusCode": None,
        }

    approval_decision_payload = {
        "decision": case_definition.get("approvalDecision"),
        "decidedBy": case_definition.get("decidedBy"),
    }
    if case_definition.get("comment") is not None:
        approval_decision_payload["comment"] = case_definition.get("comment")

    approval_decision_response = _post_json(
        f"{api_base_url}/approvals/{approval_id}/decision",
        approval_decision_payload,
        headers=request_headers,
    )
    execute_response = _post_json(
        f"{api_base_url}/approvals/{approval_id}/execute",
        {
            "executedBy": case_definition.get("executedBy"),
        },
        headers=request_headers,
    )
    execute_body = execute_response.get("body", {})
    report_id = execute_body.get("reportId")

    if not isinstance(report_id, str) or not report_id:
        return {
            "httpStatusCode": initial_response.get("httpStatusCode"),
            "body": {
                **initial_body,
                "decisionResult": approval_decision_response.get("body", {}),
                "executeResult": execute_body,
                "reportRecord": {},
            },
            "approvalDecisionHttpStatusCode": approval_decision_response.get("httpStatusCode"),
            "approvalExecuteHttpStatusCode": execute_response.get("httpStatusCode"),
            "reportGetHttpStatusCode": None,
        }

    report_get_response = _get_json(
        f"{api_base_url}/incident-reports/{report_id}",
        headers=request_headers,
    )

    return {
        "httpStatusCode": initial_response.get("httpStatusCode"),
        "body": {
            **initial_body,
            "decisionResult": approval_decision_response.get("body", {}),
            "executeResult": execute_body,
            "reportRecord": report_get_response.get("body", {}),
        },
        "approvalDecisionHttpStatusCode": approval_decision_response.get("httpStatusCode"),
        "approvalExecuteHttpStatusCode": execute_response.get("httpStatusCode"),
        "reportGetHttpStatusCode": report_get_response.get("httpStatusCode"),
    }


def _write_markdown_report(api_base_url, started_at, results):
    total_cases = len(results)
    passed_cases = sum(1 for result in results if result["pass"])
    failed_cases = total_cases - passed_cases

    lines = [
        "# RAG Evaluation Report",
        "",
        f"- API base URL: {api_base_url}",
        f"- timestamp: {started_at}",
        f"- total cases: {total_cases}",
        f"- passed cases: {passed_cases}",
        f"- failed cases: {failed_cases}",
        "",
        "| Case ID | Type | Endpoint | HTTP | Status | Question | Filters | Sources | Min Similarity | Output Guardrail | Pass/Fail | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for result in results:
        response_body = result["response"].get("body", {})
        http_status_code = result["response"].get("httpStatusCode", "-")
        status = response_body.get("status", "-")
        filters = _format_filters_for_markdown(response_body)
        sources = _format_sources_for_markdown(response_body)
        min_similarity_score = response_body.get("minSimilarityScore", "-")
        output_guardrail = _format_output_guardrail_for_markdown(response_body)
        pass_fail = "PASS" if result["pass"] else "FAIL"
        question = str(result["question"]).replace("|", "\\|")
        notes = str(result["notes"]).replace("|", "\\|")
        lines.append(
            f"| {result['caseId']} | {result['type']} | {result['expected'].get('endpoint', '/rag/query')} | {http_status_code} | {status} | {question} | {filters} | {sources} | {min_similarity_score} | {output_guardrail} | {pass_fail} | {notes} |"
        )

    lines.extend(["", "## Answer Snippets", ""])

    for result in results:
        response_body = result["response"].get("body", {})
        answer = response_body.get("answer", "")
        filters = _format_filters_for_markdown(response_body)
        sources = _format_sources_for_markdown(response_body)
        min_similarity_score = response_body.get("minSimilarityScore", "-")
        output_guardrail = _format_output_guardrail_for_markdown(response_body)
        lines.extend(
            [
                f"### {result['caseId']}",
                "",
                f"HTTP Status: {result['response'].get('httpStatusCode', '-')}",
                "",
                f"Endpoint: {result['expected'].get('endpoint', '/rag/query')}",
                "",
                f"Question: {result['question']}",
                "",
                f"Status: {response_body.get('status', '-')}",
                "",
                f"Filters: {filters}",
                "",
                f"Sources: {sources}",
                "",
                f"Min Similarity Score: {min_similarity_score}",
                "",
                f"Output Guardrail: {output_guardrail}",
                "",
                f"Answer: {_answer_snippet(answer) or '-'}",
                "",
            ]
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with MARKDOWN_REPORT_PATH.open("w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines))


def main():
    api_base_url = _require_api_base_url()
    started_at = datetime.now(timezone.utc).isoformat()

    script_directory = Path(__file__).resolve().parent
    repository_root = script_directory.parent
    document = _load_json(repository_root / DOCUMENT_PATH)
    questions = _load_json(repository_root / QUESTIONS_PATH)

    document_response = _post_json(
        f"{api_base_url}/documents",
        document,
        headers=_apply_authorization_header(),
    )
    if document_response["httpStatusCode"] >= 400:
        raise SystemExit(
            "Document indexing failed: "
            + json.dumps(document_response, indent=2)
        )

    results = []
    results_by_case_id = {}
    for case_definition in questions:
        request_headers = dict(DEFAULT_REQUEST_HEADERS)
        if isinstance(case_definition.get("headers"), dict):
            request_headers.update(case_definition["headers"])
        request_headers = _apply_authorization_header(request_headers)

        if case_definition.get("type") == "approval_workflow":
            response = _run_approval_workflow_case(api_base_url, case_definition, request_headers)
        elif case_definition.get("type") == "approval_execute_internal_report":
            response = _run_approval_execute_internal_report_case(api_base_url, case_definition, request_headers)
        else:
            request_payload = _build_request_payload(case_definition, results_by_case_id)
            endpoint = case_definition.get("endpoint", "/rag/query")
            response = _post_json(
                f"{api_base_url}{endpoint}",
                request_payload,
                headers=request_headers,
            )
        evaluation_result = _evaluate_case(case_definition, response)
        results.append(evaluation_result)
        results_by_case_id[evaluation_result["caseId"]] = evaluation_result

    results_payload = {
        "apiBaseUrl": api_base_url,
        "timestamp": started_at,
        "documentResponse": document_response,
        "results": results,
    }
    _write_json_report(results_payload)
    _write_markdown_report(api_base_url, started_at, results)

    total_cases = len(results)
    passed_cases = sum(1 for result in results if result["pass"])
    print(f"RAG evaluation complete: {passed_cases}/{total_cases} cases passed.")
    print(f"JSON results: {RAW_RESULTS_PATH}")
    print(f"Markdown report: {MARKDOWN_REPORT_PATH}")


if __name__ == "__main__":
    main()