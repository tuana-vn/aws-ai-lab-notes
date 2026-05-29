import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from common.approval_repository import ApprovalRepository
from common.incident_report_repository import IncidentReportRepository
from common.logging import get_logger, log_audit_event
from common.policy import AccessDeniedError, assert_permission_allowed, resolve_access_context
from common.response import json_response

ACTION_APPROVALS_TABLE_NAME = os.environ.get("ACTION_APPROVALS_TABLE_NAME", "")
INCIDENT_REPORTS_TABLE_NAME = os.environ.get("INCIDENT_REPORTS_TABLE_NAME", "")
VALID_DECISIONS = {"approved", "rejected"}
LOGGER = get_logger(__name__)


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


def _get_request_id(event):
    request_context = event.get("requestContext") or {}
    request_id = request_context.get("requestId")
    if isinstance(request_id, str) and request_id.strip():
        return request_id.strip()
    return None


def _log_approval_audit_event(
    event_type,
    message,
    request_id,
    approval_id,
    path,
    user_id=None,
    route_category="approval",
    **fields,
):
    audit_fields = {
        "approvalId": approval_id,
        "path": path,
        "routeCategory": route_category,
        **fields,
    }
    if user_id:
        audit_fields["userId"] = user_id

    log_audit_event(
        LOGGER,
        logging.INFO,
        event_type,
        message,
        request_id=request_id,
        **audit_fields,
    )


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
    request_id = _get_request_id(event)
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

        access_context = None
        try:
            access_context = resolve_access_context(event)
            assert_permission_allowed("approvals:decide", access_context)
        except AccessDeniedError as exc:
            return json_response(403, {"message": str(exc)})

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
        _log_approval_audit_event(
            "approval_decided",
            "Approval decision recorded without executing the action.",
            request_id,
            approval_id,
            path,
            user_id=access_context.user_id,
            status=updated_approval.get("status"),
            decision=updated_approval.get("decision"),
            executionStatus=updated_approval.get("execution_status"),
            actionType=(updated_approval.get("proposed_action") or {}).get("actionType"),
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
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                status="denied",
                policyReason="approval record not found",
            )
            return json_response(404, {"message": "Approval record not found."})

        access_context = None
        try:
            access_context = resolve_access_context(event)
            assert_permission_allowed("approvals:execute", access_context)
        except AccessDeniedError as exc:
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                user_id=access_context.user_id if access_context else None,
                status="denied",
                executionStatus=approval.get("execution_status"),
                actionType=(approval.get("proposed_action") or {}).get("actionType"),
                policyReason="missing approvals:execute permission",
            )
            return json_response(403, {"message": str(exc)})

        try:
            execute_request = _parse_execute_body(event)
        except ValueError as exc:
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                user_id=access_context.user_id,
                status="denied",
                executionStatus=approval.get("execution_status"),
                actionType=(approval.get("proposed_action") or {}).get("actionType"),
                policyReason="invalid execute request body",
            )
            return json_response(400, {"message": str(exc)})

        _log_approval_audit_event(
            "approval_execute_requested",
            "Approval execution was requested.",
            request_id,
            approval_id,
            path,
            user_id=access_context.user_id,
            status="requested",
            executionStatus=approval.get("execution_status"),
            actionType=(approval.get("proposed_action") or {}).get("actionType"),
        )

        if approval.get("status") != "approved":
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                user_id=access_context.user_id,
                status="denied",
                executionStatus=approval.get("execution_status"),
                actionType=(approval.get("proposed_action") or {}).get("actionType"),
                policyReason="approval is not approved",
            )
            return json_response(409, {"message": "Approval record is not in approved status."})
        if approval.get("execution_status") != "approved_not_executed":
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                user_id=access_context.user_id,
                status="denied",
                executionStatus=approval.get("execution_status"),
                actionType=(approval.get("proposed_action") or {}).get("actionType"),
                policyReason="approval is not ready for execution",
            )
            return json_response(409, {"message": "Approval record is not ready for execution."})

        proposed_action = approval.get("proposed_action", {})
        if proposed_action.get("actionType") != "create_incident_report":
            _log_approval_audit_event(
                "approval_execute_denied",
                "Approval execution was denied before internal action execution.",
                request_id,
                approval_id,
                path,
                user_id=access_context.user_id,
                status="denied",
                executionStatus=approval.get("execution_status"),
                actionType=proposed_action.get("actionType"),
                policyReason="unsupported action type for execution",
            )
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
        _log_approval_audit_event(
            "incident_report_created",
            "Internal incident report record was created from an approved action.",
            request_id,
            approval_id,
            path,
            user_id=access_context.user_id,
            route_category="incident_report",
            reportId=report_id,
            status="created",
            actionType="create_incident_report",
            executionStatus=approval.get("execution_status"),
        )
        repository.mark_executed(approval_id, report_id)
        _log_approval_audit_event(
            "approval_executed",
            "Approved internal action executed by creating an incident report record.",
            request_id,
            approval_id,
            path,
            user_id=access_context.user_id,
            reportId=report_id,
            status="executed",
            executionStatus="executed",
            actionType="create_incident_report",
        )

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