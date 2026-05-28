# Route Protection Matrix

## Purpose

This document defines the current and target authentication and authorization posture for API routes after protecting `POST /rag/query` and `POST /documents`.

It is a planning document for safe route-protection expansion. It does not claim that additional routes are already protected. Current state, target state, and future phases are intentionally separated.

## Current Protected Boundaries

The current protected boundaries are:

- `POST /rag/query` is protected by Cognito.
- `POST /documents` is protected by Cognito.
- the backend policy gate still validates `projectId` and `customerId` for RAG query
- trusted-header fallback remains for local and unprotected-route compatibility
- other routes remain unchanged in the current phase

What this means in practice:

- the two main RAG boundaries now have a real API authentication boundary
- the backend still performs scope validation after authentication for RAG query
- routes outside those two boundaries still need an explicit protection decision in future phases

## Route Matrix

| Route | Method | Current protection | Target protection | Candidate permission or scope | Risk if public | Recommended priority | Evidence needed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/health` | `GET` | public | public or internal-only ops route | `ops:health` if protected later | low if response remains non-sensitive | low | if protected later: unauthenticated request rejected and authenticated ops request succeeds |
| `/echo` | `POST` | unchanged | protect or remove | `debug:echo` | moderate because it exposes request reflection and trace behavior useful for debugging | low after agent and approval routes | decision evidence: either removal or authenticated debug-only access |
| `/chat` | `POST` | unchanged | protect or remove | `chat:invoke` | moderate because it invokes Bedrock and could become an unintended public smoke endpoint | medium after agent and approval routes | no-token rejection if protected, valid-token success, and clear decision whether route remains needed |
| `/documents` | `POST` | Cognito protected | stay Cognito protected | `documents:write` | high because public ingestion would let unauthenticated callers modify indexed content | already protected | no-token rejected by API Gateway, valid token indexes document, regression eval still passes |
| `/rag/query` | `POST` | Cognito protected | stay Cognito protected | `rag:query` | high because it exposes retrieval and model-backed answer generation | already protected | no-token rejected by API Gateway, valid token succeeds, mismatched project denied by backend policy |
| `/agent/run` | `POST` | unchanged | Cognito protected next | `agent:run` | high because the agent can inspect traces, logs, and propose approval-required actions | highest next priority | no-token rejected by API Gateway, valid token succeeds, read-only and approval-required paths still behave correctly |
| `/approvals/{approvalId}` | `GET` | unchanged | Cognito protected | `approvals:read` | high because approval records reveal proposed internal actions and workflow state | high after `/agent/run` | no-token rejected, valid reader succeeds, unauthorized reader denied if role or scope model is added |
| `/approvals/{approvalId}/decision` | `POST` | unchanged | Cognito protected | `approvals:decide` | high because a public decision route would allow unauthorized approval outcomes | high after `/agent/run` | no-token rejected, authorized approver succeeds, unauthorized caller denied, workflow state validation still enforced |
| `/approvals/{approvalId}/execute` | `POST` | unchanged | Cognito protected | `approvals:execute` | high because execution can trigger internal actions after approval | high after `/agent/run` | no-token rejected, authorized executor succeeds, unauthorized caller denied, execution still validates approval state and action type |
| `/incident-reports/{reportId}` | `GET` | unchanged | Cognito protected | `incident-reports:read` | high because incident reports are operational data and should not be public | medium-high after approval routes | no-token rejected, valid authenticated reader succeeds, regression checks still pass |

## Recommended Expansion Order

Recommended expansion order:

1. Protect `POST /agent/run`
2. Protect approval routes
3. Protect `GET /incident-reports/{reportId}`
4. Decide whether to protect or remove `POST /chat`
5. Decide whether to keep, protect, or remove `POST /echo`
6. Decide whether `GET /health` stays public or becomes internal-only

Why this order is practical:

- it protects the highest operational-risk routes before low-risk debugging or smoke-test routes
- it keeps the approval workflow behind auth before broadening demo or diagnostics decisions
- it preserves a narrow and reviewable expansion path rather than protecting every remaining route at once

## Why /agent/run Next

`POST /agent/run` should be the next protected route.

Reasons:

- the agent can call tools
- the agent can inspect traces and logs
- the agent can propose approval-required actions
- even read-only tools reveal operational data
- the agent endpoint therefore should not remain public

It also has the clearest next-step value because it sits next to the already-protected RAG path and shares some of the same identity and trace expectations.

## Approval Route Protection Requirements

Approval route protection needs more than simple authentication.

- `GET /approvals/{approvalId}` requires an authenticated user and `approvals:read`
- `POST /approvals/{approvalId}/decision` requires approver permission or role
- `POST /approvals/{approvalId}/execute` requires executor permission or role
- approval does not automatically execute
- the executor must still validate approval state and action type
- route protection does not replace workflow state validation

Important design rule:

- API authentication decides who can reach the route
- workflow validation still decides whether the requested action is valid in the current approval state

## /chat and /echo Decision

The `/chat` and `/echo` routes should be treated as special-purpose utility endpoints, not as core protected business routes.

- `/chat` is a Bedrock smoke-test endpoint and should not be treated as enterprise controlled RAG
- `/chat` should either be protected or disabled before broader demo or customer exposure
- `/echo` is useful for debugging but should be removed or protected outside learning mode

These routes should not stay public by accident simply because they were helpful during early PoC development.

## Candidate Permission Names

Candidate permission names for future phases:

- `documents:write`
- `rag:query`
- `agent:run`
- `approvals:read`
- `approvals:decide`
- `approvals:execute`
- `incident-reports:read`
- `chat:invoke`
- `debug:echo`
- `ops:health`

These names are design candidates only. They are not implemented yet.

## Evidence Template Per Route

For each future protected route, evidence should include:

- no token request rejected by API Gateway
- valid token request succeeds
- valid token with insufficient role or scope denied if implemented
- route business validation still works
- regression evaluation still passes or has documented expected skips

This keeps route protection evidence separate from business logic evidence and makes it easier to prove that authentication did not bypass application validation.

## Non-goals

- no code change in this phase
- no new route protection in this phase
- no OAuth scope enforcement yet
- no production IdP federation
- no removal of trusted headers yet
- no full production readiness claim

## Proposed Next Phase

Phase 8K should protect `POST /agent/run`.
