from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAMBDA_ROOT = REPOSITORY_ROOT / "backend" / "lambda"
if str(LAMBDA_ROOT) not in sys.path:
    sys.path.insert(0, str(LAMBDA_ROOT))

if "boto3" not in sys.modules:
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.resource = lambda *args, **kwargs: None
    sys.modules["boto3"] = fake_boto3

from approvals import handler
from common.policy import AccessContext, AccessDeniedError


def _build_event(path: str, body: dict[str, object] | None = None) -> dict:
    return {
        "rawPath": path,
        "path": path,
        "body": None if body is None else json.dumps(body),
        "pathParameters": {"approvalId": "approval-123"},
        "requestContext": {
            "http": {"method": "POST"},
            "requestId": "request-123",
        },
    }


class ApprovalExecuteIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.execute_event = _build_event(
            "/approvals/approval-123/execute",
            {"executedBy": "operator-user"},
        )
        self.access_context = AccessContext(
            user_id="operator-user",
            principal_id="operator-user",
            allowed_project_ids=[],
            allowed_customer_ids=[],
            auth_source="mock_authorizer_claims",
            scopes=[],
            groups=["ai-operator"],
        )

    @patch.object(handler, "ACTION_APPROVALS_TABLE_NAME", "approvals-table")
    @patch.object(handler, "INCIDENT_REPORTS_TABLE_NAME", "incident-reports-table")
    @patch.object(handler, "_log_approval_audit_event")
    @patch.object(handler, "_incident_report_repository")
    @patch.object(handler, "resolve_access_context")
    @patch.object(handler, "assert_permission_allowed")
    @patch.object(handler, "_approval_repository")
    def test_execute_replay_returns_existing_report_without_new_write(
        self,
        approval_repository_factory,
        assert_permission_allowed,
        resolve_access_context,
        incident_report_repository_factory,
        log_approval_audit_event,
    ):
        approval_repository = approval_repository_factory.return_value
        approval_repository.get_approval.return_value = {
            "approval_id": "approval-123",
            "status": "approved",
            "execution_status": "executed",
            "proposed_action": {"actionType": "create_incident_report"},
            "execution_result": {"reportId": "report-123", "action": "create_incident_report"},
        }
        resolve_access_context.return_value = self.access_context

        response = handler.lambda_handler(self.execute_event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["approvalId"], "approval-123")
        self.assertEqual(body["reportId"], "report-123")
        self.assertEqual(body["status"], "executed")
        self.assertEqual(body["executionStatus"], "executed")
        self.assertIn("already executed", body["message"])
        incident_report_repository_factory.return_value.create_report.assert_not_called()
        approval_repository.mark_executed.assert_not_called()
        assert_permission_allowed.assert_called_once_with("approvals:execute", self.access_context)
        self.assertTrue(
            any(call.args[0] == "approval_execute_idempotent_replay" for call in log_approval_audit_event.call_args_list)
        )

    @patch.object(handler, "ACTION_APPROVALS_TABLE_NAME", "approvals-table")
    @patch.object(handler, "INCIDENT_REPORTS_TABLE_NAME", "incident-reports-table")
    @patch.object(handler, "_log_approval_audit_event")
    @patch.object(handler, "resolve_access_context")
    @patch.object(handler, "assert_permission_allowed")
    @patch.object(handler, "_approval_repository")
    def test_execute_replay_requires_permission_before_returning_report(
        self,
        approval_repository_factory,
        assert_permission_allowed,
        resolve_access_context,
        log_approval_audit_event,
    ):
        approval_repository_factory.return_value.get_approval.return_value = {
            "approval_id": "approval-123",
            "status": "approved",
            "execution_status": "executed",
            "proposed_action": {"actionType": "create_incident_report"},
            "execution_result": {"reportId": "report-123", "action": "create_incident_report"},
        }
        resolve_access_context.return_value = self.access_context
        assert_permission_allowed.side_effect = AccessDeniedError("Missing approvals:execute permission.")

        response = handler.lambda_handler(self.execute_event, None)

        self.assertEqual(response["statusCode"], 403)
        body = json.loads(response["body"])
        self.assertIn("Missing approvals:execute permission.", body["message"])
        self.assertFalse(
            any(call.args[0] == "approval_execute_idempotent_replay" for call in log_approval_audit_event.call_args_list)
        )

    @patch.object(handler, "ACTION_APPROVALS_TABLE_NAME", "approvals-table")
    @patch.object(handler, "INCIDENT_REPORTS_TABLE_NAME", "incident-reports-table")
    @patch.object(handler, "_log_approval_audit_event")
    @patch.object(handler, "resolve_access_context")
    @patch.object(handler, "assert_permission_allowed")
    @patch.object(handler, "_approval_repository")
    def test_execute_replay_does_not_apply_when_status_is_not_approved(
        self,
        approval_repository_factory,
        assert_permission_allowed,
        resolve_access_context,
        log_approval_audit_event,
    ):
        approval_repository_factory.return_value.get_approval.return_value = {
            "approval_id": "approval-123",
            "status": "rejected",
            "execution_status": "executed",
            "proposed_action": {"actionType": "create_incident_report"},
            "execution_result": {"reportId": "report-123", "action": "create_incident_report"},
        }
        resolve_access_context.return_value = self.access_context

        response = handler.lambda_handler(self.execute_event, None)

        self.assertEqual(response["statusCode"], 409)
        body = json.loads(response["body"])
        self.assertIn("not in approved status", body["message"])
        assert_permission_allowed.assert_called_once_with("approvals:execute", self.access_context)
        self.assertFalse(
            any(call.args[0] == "approval_execute_idempotent_replay" for call in log_approval_audit_event.call_args_list)
        )

    @patch.object(handler, "ACTION_APPROVALS_TABLE_NAME", "approvals-table")
    @patch.object(handler, "INCIDENT_REPORTS_TABLE_NAME", "incident-reports-table")
    @patch.object(handler, "_log_approval_audit_event")
    @patch.object(handler, "_incident_report_repository")
    @patch.object(handler, "resolve_access_context")
    @patch.object(handler, "assert_permission_allowed")
    @patch.object(handler, "_approval_repository")
    @patch.object(handler, "uuid4", return_value="generated-report-suffix")
    def test_first_execution_still_creates_report_and_marks_executed(
        self,
        _uuid4,
        approval_repository_factory,
        assert_permission_allowed,
        resolve_access_context,
        incident_report_repository_factory,
        log_approval_audit_event,
    ):
        approval_repository = approval_repository_factory.return_value
        approval_repository.get_approval.return_value = {
            "approval_id": "approval-123",
            "request_id": "request-origin-123",
            "status": "approved",
            "execution_status": "approved_not_executed",
            "proposed_action": {
                "actionType": "create_incident_report",
                "title": "Incident title",
                "summary": "Incident summary",
                "severity": "medium",
                "recommendedNextSteps": ["step-1"],
            },
        }
        resolve_access_context.return_value = self.access_context

        response = handler.lambda_handler(self.execute_event, None)

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["reportId"], "report-generated-report-suffix")
        incident_report_repository_factory.return_value.create_report.assert_called_once()
        approval_repository.mark_executed.assert_called_once_with(
            "approval-123", "report-generated-report-suffix"
        )
        assert_permission_allowed.assert_called_once_with("approvals:execute", self.access_context)
        self.assertTrue(any(call.args[0] == "approval_executed" for call in log_approval_audit_event.call_args_list))


if __name__ == "__main__":
    unittest.main()