# Agent Run Auth Evidence

## Purpose

This document captures the expected evidence for protecting `POST /agent/run` with the existing Cognito authorizer.

Phase 8K extends the Cognito-protected boundary to the agent entrypoint while leaving approval routes and incident report lookup unchanged for now.

## Protected Route

| Route | Protection | Notes |
| --- | --- | --- |
| `POST /agent/run` | Cognito protected | Reuses the existing API Gateway Cognito authorizer. |

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| no-token `/agent/run` rejected by API Gateway | `curl -i -sS -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -d '{"task":"answer_question","question":"What does API Gateway do?","filters":{"projectId":"learning","customerId":"internal"}}'` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token `answer_question` completes | `curl -i -sS -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"task":"answer_question","question":"What does API Gateway do?","filters":{"projectId":"learning","customerId":"internal"}}'` | HTTP `200` and `status=completed` | `[fill after deployment]` | `[fill]` |
| valid-token `investigate_recent_blocks` completes | `curl -i -sS -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"task":"investigate_recent_blocks","minutes":120}'` | HTTP `200` and `status=completed` | `[fill after deployment]` | `[fill]` |
| valid-token `propose_incident_report` requires approval | `curl -i -sS -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"task":"propose_incident_report","minutes":120}'` | HTTP `200` and `status=approval_required` | `[fill after deployment]` | `[fill]` |
| token-mode eval still passes | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | token-mode eval passes with expected skip behavior | `[fill after deployment]` | `[fill]` |

## Notes

- `POST /rag/query` remains protected.
- `POST /documents` remains protected.
- `GET /health` remains public.
- Approval routes and incident report lookup remain intentionally unchanged in this phase.