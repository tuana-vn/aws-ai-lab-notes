# Auth Boundary Final Evidence

## Purpose

This document consolidates evidence for the Cognito-based authentication boundary after the progressive route-protection rollout across the AWS AI Platform PoC.

It summarizes the final intended route posture, the expected test evidence for the protected surfaces, the remaining application-level authorization behavior, and the current limitations of the PoC authentication boundary.

This document does not claim full production readiness.

## Final Route Protection Posture

| Route | Method | Current protection | Evidence status | Notes |
| --- | --- | --- | --- | --- |
| `/health` | `GET` | public | expected by design | Intended to remain public only while the response stays non-sensitive. |
| `/echo` | `POST` | Cognito protected | placeholder pending deployment capture | Debug endpoint only; may be removed later. |
| `/chat` | `POST` | Cognito protected | placeholder pending deployment capture | Smoke-test Bedrock endpoint only; not the controlled RAG path. |
| `/documents` | `POST` | Cognito protected | partially captured | Document ingestion should reject no-token requests and succeed with a valid token. |
| `/rag/query` | `POST` | Cognito protected | partially captured | Cognito authenticates the caller and backend policy still enforces RAG filter scope. |
| `/agent/run` | `POST` | Cognito protected | placeholder pending deployment capture | Authentication added only; task and workflow validation remain in the backend. |
| `/approvals/{approvalId}` | `GET` | Cognito protected | placeholder pending deployment capture | Approval-read auth added only; role rules are not implemented yet. |
| `/approvals/{approvalId}/decision` | `POST` | Cognito protected | placeholder pending deployment capture | Approval decision still depends on workflow-state validation in the backend. |
| `/approvals/{approvalId}/execute` | `POST` | Cognito protected | placeholder pending deployment capture | Execution auth added only; backend still validates approval state and action type. |
| `/incident-reports/{reportId}` | `GET` | Cognito protected | placeholder pending deployment capture | Incident report read auth added only; report-read role enforcement is not implemented yet. |

## Cognito Test User Evidence

Do not paste the full JWT token into this document.

Use captured rollout values where available, otherwise fill the placeholders below.

| Field | Value |
| --- | --- |
| username | `tuan` or `[fill deployed username]` |
| token_use | `id` |
| preferred_username | `tuan` or `[fill preferred_username]` |
| custom:project_ids | `learning` |
| custom:customer_ids | `internal` |

## Evidence Matrix

| Area | No-token expected result | Valid-token expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| `/documents` | HTTP `401` or `403` before Lambda | HTTP `200` and `status=indexed` | `[fill after deployment]` | `[fill]` |
| `/rag/query` | HTTP `401` or `403` before Lambda | HTTP `200` for allowed `learning/internal`; HTTP `403` for mismatched project or customer filters | unauthenticated `/rag/query` rejection observed; token-mode eval captured as passing | PARTIAL |
| `/agent/run` | HTTP `401` or `403` before Lambda | HTTP `200` for valid supported task such as `answer_question`, `investigate_recent_blocks`, or `propose_incident_report` | `[fill after deployment]` | `[fill]` |
| approval read | HTTP `401` or `403` before Lambda | HTTP `200` and approval record returned for valid token | `[fill after deployment]` | `[fill]` |
| approval decision | HTTP `401` or `403` before Lambda | HTTP `200` and approval transitions to `approved` or `approved_not_executed` where business validation passes | `[fill after deployment]` | `[fill]` |
| approval execute | HTTP `401` or `403` before Lambda | HTTP `200`, execution result shows `executed`, and response includes `reportId` where business validation passes | `[fill after deployment]` | `[fill]` |
| incident report read | HTTP `401` or `403` before Lambda | HTTP `200` and stored incident report record returned for valid token | `[fill after deployment]` | `[fill]` |
| `/chat` | HTTP `401` or `403` before Lambda | HTTP `200` and valid Bedrock chat response | `[fill after deployment]` | `[fill]` |
| `/echo` | HTTP `401` or `403` before Lambda | HTTP `200` and current echo response returned | `[fill after deployment]` | `[fill]` |

## RAG Policy Evidence

The Cognito authentication boundary proves identity at API Gateway, but it does not replace application-level authorization in the backend.

For `POST /rag/query`:

- a valid Cognito token authenticates the caller
- the backend policy still evaluates requested `projectId` and `customerId` filters against the claims-backed `AccessContext`
- a mismatched project or customer request is still denied after authentication

This is the important interpretation of the current PoC boundary:

- authentication proves who is calling the route
- backend policy still decides whether the requested RAG scope is allowed

`Q005` remains the key policy-denied evidence because it demonstrates that an authenticated caller can still receive a backend `403` when the requested filters are outside the allowed claim scope.

`Q006` is skipped in token mode because trusted-header spoofing is no longer the active auth source once Cognito claims are present on protected routes.

## Evaluation Evidence

Expected token-mode output:

```text
Skipping Q006 in token mode because trusted-header spoofing is not the active auth source.
RAG evaluation complete: 15/15 cases passed.
Skipped cases: 1
```

Interpretation:

- token-mode evaluation still passes for all evaluated cases
- the skipped case is intentional and should not be treated as a regression
- the skip exists because trusted `X-Allowed-*` header spoofing is no longer the active boundary when Cognito claims drive `AccessContext`

## Important Interpretation

After Cognito protection, trusted `X-Allowed-*` headers must not override verified authorizer claims on protected routes.

The active identity for protected routes comes from Cognito claims delivered through `requestContext.authorizer.claims`.

The `AccessContext` contract made this transition possible without changing the core RAG or agent business logic:

- route authentication moved to API Gateway and Cognito
- identity and allowed scope moved to verified claims for protected routes
- existing backend business logic could continue consuming a stable access-context abstraction

## Remaining Limitations

- no route-level OAuth scope enforcement yet
- no approver or executor role enforcement yet
- ID token is used for PoC convenience
- trusted_headers fallback still exists for local compatibility
- no production IdP federation
- no WAF, CloudTrail, or security-dashboard hardening yet
- `/health` remains public by design
- `/chat` is still smoke-test only and is not controlled RAG
- `/echo` is still debug only and may be removed later

## Acceptance Criteria

Phase 8 auth boundary is acceptable when:

- all non-health routes reject no-token requests
- valid-token requests succeed where business validation passes
- backend policy still denies out-of-scope RAG requests
- token-mode eval passes with the documented `Q006` skip
- no production-readiness overclaim is made

## Recommended Next Phase

Phase 8Q - Route-level Scope and Role Authorization Design