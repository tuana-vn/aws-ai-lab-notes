import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from common.approval_repository import ApprovalRepository
from common.incident_report_repository import IncidentReportRepository
from common.response import json_response

ACTION_APPROVALS_TABLE_NAME = os.environ.get("ACTION_APPROVALS_TABLE_NAME", "")
INCIDENT_REPORTS_TABLE_NAME = os.environ.get("INCIDENT_REPORTS_TABLE_NAME", "")
VALID_DECISIONS = {"approved", "rejected"}


def _approval_repository() -> ApprovalRepository:
    return ApprovalRepository(ACTION_APPROVALS_TABLE_NAME)


def _incident_report_repository() -> IncidentReportRepository:
    return IncidentReportRepository(INCIDENT_REPORTS_TABLE_NAME)


def _get_approval_id(event):
    path_parameters = event.get("pathParameters") or {}
    approval_id = path_parameters.get("approvalId")
    if isinstance(approval_id, str) and approval_id.strip():
        return approval_id.strip()
    return None


def _get_method(event):
    request_context = event.get("requestContext") or {}
    http_context = request_context.get("http") or {}
    method = http_context.get("method") or event.get("httpMethod")
    return method.upper() if isinstance(method, str) else ""


def _parse_decision_body(event):
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

    decision = body.get("decision")
    decided_by = body.get("decidedBy")
    comment = body.get("comment")

    if not isinstance(decision, str) or decision not in VALID_DECISIONS:
        raise ValueError("Field 'decision' must be 'approved' or 'rejected'.")
    if not isinstance(decided_by, str) or not decided_by.strip():
        raise ValueError("Field 'decidedBy' is required and must be a non-empty string.")
    if comment is not None and not isinstance(comment, str):
        raise ValueError("Field 'comment' must be a string when provided.")

    return {
        "decision": decision,
        "decidedBy": decided_by.strip(),
        "comment": comment,
    }


def _parse_execute_body(event):
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

    executed_by = body.get("executedBy")
    if not isinstance(executed_by, str) or not executed_by.strip():
        raise ValueError("Field 'executedBy' is required and must be a non-empty string.")

    return {"executedBy": executed_by.strip()}


def lambda_handler(event, context):
    if not ACTION_APPROVALS_TABLE_NAME:
        return json_response(500, {"message": "Action approvals table is not configured."})

    approval_id = _get_approval_id(event)
    if not approval_id:
        return json_response(400, {"message": "approvalId path parameter is required."})

    method = _get_method(event)
    path = event.get("rawPath") or event.get("path") or ""
    repository = _approval_repository()

    if method == "GET" and not path.endswith("/decision"):
        approval = repository.get_approval(approval_id)
        if approval is None:
            return json_response(404, {"message": "Approval record not found."})
        return json_response(200, approval)

    if method == "POST" and path.endswith("/decision"):
        approval = repository.get_approval(approval_id)
        if approval is None:
            return json_response(404, {"message": "Approval record not found."})

        try:
            decision_request = _parse_decision_body(event)
        except ValueError as exc:
            return json_response(400, {"message": str(exc)})

        updated_approval = repository.update_decision(
            approval_id,
            decision_request["decision"],
            decision_request["decidedBy"],
            decision_request["comment"],
        )
        return json_response(
            200,
            {
                "approvalId": approval_id,
                "status": updated_approval.get("status"),
                "decision": updated_approval.get("decision"),
                "executionStatus": updated_approval.get("execution_status"),
            },
        )

    if method == "POST" and path.endswith("/execute"):
        if not INCIDENT_REPORTS_TABLE_NAME:
            return json_response(500, {"message": "Incident reports table is not configured."})

        approval = repository.get_approval(approval_id)
        if approval is None:
            return json_response(404, {"message": "Approval record not found."})

        try:
            execute_request = _parse_execute_body(event)
        except ValueError as exc:
            return json_response(400, {"message": str(exc)})

        if approval.get("status") != "approved":
            return json_response(409, {"message": "Approval record is not in approved status."})
        if approval.get("execution_status") != "approved_not_executed":
            return json_response(409, {"message": "Approval record is not ready for execution."})

        proposed_action = approval.get("proposed_action", {})
        if proposed_action.get("actionType") != "create_incident_report":
            return json_response(400, {"message": "Unsupported proposed action for execution."})

        report_id = f"report-{uuid4()}"
        report_record = {
            "report_id": report_id,
            "approval_id": approval_id,
            "source_request_id": approval.get("request_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": execute_request["executedBy"],
            "title": proposed_action.get("title"),
            "summary": proposed_action.get("summary"),
            "severity": proposed_action.get("severity"),
            "recommended_next_steps": proposed_action.get("recommendedNextSteps"),
            "status": "created",
        }
        _incident_report_repository().create_report(report_record)
        repository.mark_executed(approval_id, report_id)

        return json_response(
            200,
            {
                "approvalId": approval_id,
                "reportId": report_id,
                "status": "executed",
                "executionStatus": "executed",
                "message": "Approved action executed by creating an internal incident report record.",
            },
        )

    return json_response(404, {"message": "Approval route not found."})