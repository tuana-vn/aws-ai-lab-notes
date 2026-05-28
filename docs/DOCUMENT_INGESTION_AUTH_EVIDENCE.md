# Document Ingestion Auth Evidence

## Purpose

This document captures the expected evidence for protecting `POST /documents` with the existing Cognito authorizer.

Phase 8J extends the first Cognito-protected route rollout by protecting document ingestion as well as RAG query. This file is an evidence placeholder for deployment-time capture.

## Protected Route

| Route | Protection | Notes |
| --- | --- | --- |
| `POST /documents` | Cognito protected | Added by reusing the existing API Gateway Cognito authorizer. |

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| no-token `/documents` rejected by API Gateway | `curl -i -sS -X POST "$API_BASE_URL/documents" -H "Content-Type: application/json" -d @test-data/requests/demo-document-request.json` | HTTP `401` or `403` before Lambda | `[fill after deployment]` | `[fill]` |
| valid-token `/documents` returns indexed | `curl -i -sS -X POST "$API_BASE_URL/documents" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d @test-data/requests/demo-document-request.json` | HTTP `200` and `status=indexed` | `[fill after deployment]` | `[fill]` |
| token-mode eval still passes | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | `15/15` passed and `1` skipped | `[fill after deployment]` | `[fill]` |

## Notes

- `POST /rag/query` remains protected.
- `GET /health` remains public.
- Other routes remain intentionally unchanged in this phase.
- Trusted headers still exist for local compatibility on unprotected routes.