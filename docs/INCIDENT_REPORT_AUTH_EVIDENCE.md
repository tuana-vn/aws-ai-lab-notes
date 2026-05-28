# Incident Report Read Auth Evidence

## Purpose

This document captures the expected evidence for protecting the incident report read route with the existing Cognito authorizer.

Phase 8M adds authentication to:

- `GET /incident-reports/{reportId}`

This phase adds authentication only. It does not add incident report read role or scope enforcement yet.

## Protected Route

| Route | Protection | Notes |
| --- | --- | --- |
| `GET /incident-reports/{reportId}` | Cognito protected | Reuses the existing API Gateway Cognito authorizer. |

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| valid-token approval execute creates reportId | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"executedBy":"tuan"}'` | HTTP `200` and response includes `reportId` | `[fill after deployment]` | `[fill]` |
| no-token incident report read rejected | `curl -i -sS -X GET "$API_BASE_URL/incident-reports/$REPORT_ID"` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token incident report read returns stored report | `curl -i -sS -X GET "$API_BASE_URL/incident-reports/$REPORT_ID" -H "Authorization: Bearer $AUTH_TOKEN"` | HTTP `200` and body returns the created incident report record | `[fill after deployment]` | `[fill]` |
| token-mode eval still passes | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | token-mode eval passes with expected skip behavior | `[fill after deployment]` | `[fill]` |

## Notes

- `POST /rag/query` remains protected.
- `POST /documents` remains protected.
- `POST /agent/run` remains protected.
- `GET /approvals/{approvalId}`, `POST /approvals/{approvalId}/decision`, and `POST /approvals/{approvalId}/execute` remain protected.
- `GET /health` remains public.
- `/echo` and `/chat` remain intentionally unchanged in this phase.
- Incident report business logic remains unchanged; authentication is added at API Gateway.