# Phase 8 Final Authentication and Authorization Evidence

## Purpose

This document closes Phase 8 by consolidating the implemented authentication and authorization evidence for the AWS AI Platform PoC.

It summarizes the Cognito authentication boundary, the `AccessContext` claims mapping model used on protected routes, the final protected route posture, the backend RAG policy boundary, the approval permission boundary, and the regression evaluation result.

This document does not claim full production readiness.

## Final Route Protection Posture

| Route | Method | Protection | Notes |
| --- | --- | --- | --- |
| `/health` | `GET` | public | Public by design while the response remains non-sensitive. |
| `/echo` | `POST` | Cognito protected | Debug-only endpoint. Protected, but still not a production-facing business route. |
| `/chat` | `POST` | Cognito protected | Smoke-test endpoint only. It is not the controlled enterprise RAG path. |
| `/documents` | `POST` | Cognito protected | Protected by the Cognito authorizer before Lambda invocation. |
| `/rag/query` | `POST` | Cognito protected | Protected by Cognito, with backend project and customer policy checks still enforced after authentication. |
| `/agent/run` | `POST` | Cognito protected | Protected by Cognito. Task validation and workflow logic still happen in the backend. |
| `/approvals/{approvalId}` | `GET` | Cognito protected | Protected by Cognito. No route-level permission check is implemented yet for approval read. |
| `/approvals/{approvalId}/decision` | `POST` | Cognito protected plus permission check | Requires authentication and `approvals:decide`. |
| `/approvals/{approvalId}/execute` | `POST` | Cognito protected plus permission check | Requires authentication and `approvals:execute`. |
| `/incident-reports/{reportId}` | `GET` | Cognito protected | Protected by Cognito. No separate route-level permission scope is implemented yet for this route. |

## Implemented Permission Boundary

| Action | Required permission | Allowed group | Denied group | Business validation that still applies |
| --- | --- | --- | --- | --- |
| Approval decision | `approvals:decide` | `ai-approver` | `ai-operator` | Approval must still be in a state that allows decision, and decision payload validation still applies. |
| Approval execute | `approvals:execute` | `ai-operator` | `ai-approver` | Approval must still be ready for execution, and existing approval state and action validation still apply. |

`ai-admin` remains an allowed administrative group because it grants all current route permissions, but it should not be the main evidence user because it can hide permission bugs.

## Test Users and Groups

Do not include passwords or full JWTs in this document.

| Test user purpose | Group |
| --- | --- |
| admin or eval user | `ai-admin` |
| approver user | `ai-approver` |
| operator user | `ai-operator` |

If specific usernames were captured during rollout, they can be recorded alongside these groups later without adding secrets.

## Evidence Matrix

| Evidence item | Expected result | Observed result | Status |
| --- | --- | --- | --- |
| `/health` public | HTTP `200` without token | Public by design and documented as intentionally unauthenticated | PASS |
| protected routes reject no-token requests | Non-health protected routes return HTTP `401` or `403` before Lambda | Captured across the Phase 8 route-protection evidence set for protected routes | PASS |
| valid token `/documents` indexes document | HTTP `200` with indexing success response | Captured in the document-ingestion auth evidence for authenticated requests | PASS |
| valid token `/rag/query` returns `completed` or `no_source` as appropriate | HTTP `200` with grounded response outcome based on retrieval result | Captured in RAG auth evidence and token-mode regression evaluation behavior | PASS |
| wrong project or customer denied by backend RAG policy | HTTP `403` after authentication when requested scope is outside allowed claims | Captured as the backend policy deny path after successful authentication | PASS |
| valid token `/agent/run` works | HTTP `200` for supported authenticated task flow | Captured in agent-run auth evidence | PASS |
| valid token `/chat` works as smoke test only | HTTP `200` with smoke-test response | Captured in chat auth evidence as authenticated smoke-test behavior only | PASS |
| valid token `/echo` works with correct payload `{"message":"hello world"}` | HTTP `200` with expected debug echo response | HTTP `200` with the correct payload; payloads such as `{"hello":"world"}` reach Lambda but fail request validation with HTTP `400`, which is not an authentication failure | PASS |
| no-token incident report read rejected | HTTP `401` or `403` before Lambda | Captured in incident-report auth evidence | PASS |
| valid token incident report read succeeds | HTTP `200` with incident report payload | Captured in incident-report auth evidence | PASS |
| operator cannot decide approval | HTTP `403` permission denied | Observed HTTP `403` for operator decision attempt | PASS |
| approver can decide approval | HTTP `200` when approval state permits decision | Observed HTTP `200` for approver decision attempt | PASS |
| approver cannot execute approval | HTTP `403` permission denied | Observed HTTP `403` for approver execute attempt | PASS |
| operator can execute approved action | HTTP `200` when approval is ready and execution validation passes | Observed HTTP `200` for operator execute attempt on approved action | PASS |
| eval token mode passes `15/15` with `Q006` skipped | Expected token-mode output is produced | Observed token-mode result: `15/15` passed and `1` skipped | PASS |

## Important Interpretation

Cognito authentication rejects unauthenticated requests before Lambda for protected routes.

Protected routes use authorizer claims to build `AccessContext`, which means the active authority in token mode is the verified Cognito authorizer claim set rather than caller-supplied trusted headers.

`X-Allowed-*` headers do not override Cognito-derived claims in token mode.

The backend RAG project and customer policy boundary still matters after authentication. A caller can be authenticated and still be denied when the requested `projectId` or `customerId` is outside the allowed scope in `AccessContext`.

Approval permission checks do not replace existing approval workflow validation. Route-level permission checks control who may attempt decision or execution, while approval state and action validation still control whether the requested transition is valid.

`/chat` remains a smoke-test endpoint and should not be presented as controlled enterprise RAG.

`/echo` remains a debug-only endpoint and may be removed or restricted further in a later phase. Valid-token success evidence for `/echo` uses payload `{"message":"hello world"}`. A payload such as `{"hello":"world"}` can still reach Lambda and fail request validation with HTTP `400`; that is an input-shape failure, not an authentication failure.

## Regression Evaluation Summary

Expected token-mode result:

```text
Skipping Q006 in token mode because trusted-header spoofing is not the active auth source.
RAG evaluation complete: 15/15 cases passed.
Skipped cases: 1
```

`Q006` is skipped because it is a trusted-header spoofing test, while token mode uses Cognito claims as the active authority. In that mode, spoofed `X-Allowed-*` headers should not override verified claims, so the test is intentionally not part of the active regression expectation.

## Remaining Limitations

- only approval decision and approval execute currently have route-level permission checks
- other protected routes are authenticated but not yet permission-scoped
- ID token is used for PoC convenience
- no production IdP federation is implemented
- no route-level OAuth scope enforcement is implemented yet
- `trusted_headers` fallback still exists for local compatibility
- no WAF, CloudTrail, or security dashboard hardening is implemented yet
- `/health` remains public by design
- `/chat` and `/echo` are protected but remain smoke-test and debug endpoints
- no environment-based disabling of `/chat` or `/echo` exists yet

## Acceptance Criteria

Phase 8 is acceptable when:

- all non-health routes require a Cognito token
- approval decision requires `approvals:decide`
- approval execute requires `approvals:execute`
- backend RAG policy still denies wrong project or customer requests
- token-mode evaluation passes with the documented `Q006` skip
- no production-readiness overclaim is made

## Recommended Next Phase

Phase 9A - Observability and Security Audit Dashboard Design
