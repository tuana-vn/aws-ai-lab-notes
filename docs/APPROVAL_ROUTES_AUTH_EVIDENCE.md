# Approval Routes Auth Evidence

## Purpose

This document captures the expected evidence for protecting the approval workflow routes with the existing Cognito authorizer.

Phase 8L adds authentication to:

- `GET /approvals/{approvalId}`
- `POST /approvals/{approvalId}/decision`
- `POST /approvals/{approvalId}/execute`

This phase adds authentication only. It does not add approver or executor role enforcement yet.

## Protected Routes

| Route | Protection | Notes |
| --- | --- | --- |
| `GET /approvals/{approvalId}` | Cognito protected | Reuses the existing API Gateway Cognito authorizer. |
| `POST /approvals/{approvalId}/decision` | Cognito protected | Authentication added only; business validation remains in the approval handler. |
| `POST /approvals/{approvalId}/execute` | Cognito protected | Authentication added only; approval state and action validation still apply. |

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| no-token approval GET rejected | `curl -i -sS -X GET "$API_BASE_URL/approvals/$APPROVAL_ID"` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| no-token approval decision rejected | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" -H "Content-Type: application/json" -d '{"decision":"approved","decidedBy":"tuan"}'` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| no-token approval execute rejected | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" -H "Content-Type: application/json" -d '{"executedBy":"tuan"}'` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token proposal still returns approval_required | `curl -i -sS -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"task":"propose_incident_report","minutes":120}'` | HTTP `200` and `status=approval_required` | `[fill after deployment]` | `[fill]` |
| valid-token approval GET returns pending approval record | `curl -i -sS -X GET "$API_BASE_URL/approvals/$APPROVAL_ID" -H "Authorization: Bearer $AUTH_TOKEN"` | HTTP `200` and approval record shows pending state | `[fill after deployment]` | `[fill]` |
| valid-token approval decision returns approved state | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"decision":"approved","decidedBy":"tuan"}'` | HTTP `200` and approval status becomes `approved` or `approved_not_executed` | `[fill after deployment]` | `[fill]` |
| valid-token approval execute returns executed and reportId | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"executedBy":"tuan"}'` | HTTP `200` and result shows `executed` with `reportId` | `[fill after deployment]` | `[fill]` |
| token-mode eval still passes | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | token-mode eval passes with expected skip behavior | `[fill after deployment]` | `[fill]` |

## Notes

- `POST /rag/query` remains protected.
- `POST /documents` remains protected.
- `POST /agent/run` remains protected.
- `GET /health` remains public.
- `/echo`, `/chat`, and `/incident-reports/*` remain intentionally unchanged in this phase.
- Approval business logic still enforces approval state and action validation after authentication.