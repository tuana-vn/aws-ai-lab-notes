# Chat and Echo Auth Evidence

## Purpose

This document captures the expected evidence for protecting the `/chat` and `/echo` routes with the existing Cognito authorizer.

Phase 8O adds authentication to:

- `POST /chat`
- `POST /echo`

This phase adds authentication only. It does not add route-level OAuth scopes or role enforcement.

## Protected Routes

| Route | Protection | Notes |
| --- | --- | --- |
| `POST /chat` | Cognito protected | Remains a smoke-test Bedrock endpoint only, not the controlled enterprise RAG path. |
| `POST /echo` | Cognito protected | Remains a debug endpoint; authentication is added without changing its current response shape. |

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| no-token `/chat` rejected | `curl -i -sS -X POST "$API_BASE_URL/chat" -H "Content-Type: application/json" -d '{"message":"Hello from unauthenticated smoke test"}'` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token `/chat` returns Bedrock response | `curl -i -sS -X POST "$API_BASE_URL/chat" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"message":"Hello from authenticated smoke test"}'` | HTTP `200` and a valid chat response | `[fill after deployment]` | `[fill]` |
| no-token `/echo` rejected | `curl -i -sS -X POST "$API_BASE_URL/echo" -H "Content-Type: application/json" -d '{"message":"Hello from unauthenticated echo test"}'` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token `/echo` returns expected echo response | `curl -i -sS -X POST "$API_BASE_URL/echo" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"message":"Hello from authenticated echo test"}'` | HTTP `200` and body echoes the request in the current debug format | `[fill after deployment]` | `[fill]` |
| token-mode eval still passes | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | token-mode eval passes with expected skip behavior | `[fill after deployment]` | `[fill]` |

## Notes

- `GET /health` remains public.
- `POST /rag/query`, `POST /documents`, `POST /agent/run`, the approval routes, and `GET /incident-reports/{reportId}` remain protected.
- `POST /chat` remains smoke-test only and should not be presented as the main platform path.
- `POST /echo` remains deployed in this phase; it is not removed or disabled here.
- No backend runtime code is changed for this phase.