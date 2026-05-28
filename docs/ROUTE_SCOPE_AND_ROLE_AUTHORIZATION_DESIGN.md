# Route Scope and Role Authorization Design

## Purpose

Cognito authentication is now in place for every current route except `GET /health`, but route-level authorization is the next boundary.

Authentication answers who the caller is.
Authorization answers what the caller is allowed to do.

This document describes the target design for route-level scope and role authorization after the current authentication rollout. It does not claim that route-level authorization is already implemented.

## Current State

Current state after the Phase 8 authentication rollout:

- all current routes except `GET /health` are Cognito protected
- `AccessContext` can read identity and claims from `requestContext.authorizer.claims`
- the backend RAG policy gate still checks `projectId` and `customerId` filters
- route-level permission checks are not implemented yet
- approval workflow logic still validates state and action type and that validation must remain

Phase 8R implementation note:

- `POST /approvals/{approvalId}/decision` now enforces `approvals:decide`
- `POST /approvals/{approvalId}/execute` now enforces `approvals:execute`
- broader route-level permission enforcement is still not implemented yet

This means the system currently has a real authentication boundary, but it does not yet have a separate route-permission boundary for authenticated callers.

## Problem Statement

Authenticated does not mean authorized for every action.

That matters because several authenticated routes carry different operational risks:

- approval decision and approval execute are high-risk actions
- document ingestion should require explicit write permission
- agent routes expose operational data and controlled tool behavior
- incident report lookup exposes internal operational records
- `/chat` and `/echo` should not be available to every authenticated user by default

The current boundary proves caller identity, but future phases need to prove that the caller also has the right permission or role for the requested route.

## Permission Model

| Permission | Meaning | Applies to route or action | Risk controlled |
| --- | --- | --- | --- |
| `documents:write` | Caller may create or replace indexed document content | `POST /documents` | prevents arbitrary authenticated ingestion changes |
| `rag:query` | Caller may perform grounded RAG retrieval and answer generation | `POST /rag/query` | limits access to protected retrieval and model usage |
| `agent:run` | Caller may invoke controlled agent tasks | `POST /agent/run` | limits access to operational tools and proposal workflows |
| `approvals:read` | Caller may read approval records | `GET /approvals/{approvalId}` | limits exposure of internal approval workflow data |
| `approvals:decide` | Caller may approve or reject pending approvals | `POST /approvals/{approvalId}/decision` | prevents unauthorized approval outcomes |
| `approvals:execute` | Caller may execute an already approved internal action | `POST /approvals/{approvalId}/execute` | prevents unauthorized execution of internal actions |
| `incident-reports:read` | Caller may read internal incident report records | `GET /incident-reports/{reportId}` | prevents broad access to operational incident data |
| `chat:invoke` | Caller may use the smoke-test Bedrock chat route | `POST /chat` | limits access to non-core model invocation surface |
| `debug:echo` | Caller may use the debug echo route | `POST /echo` | limits access to a debugging surface that may reflect request data |
| `ops:health` | Caller may access an internal-only health endpoint if health is later internalized | `GET /health` | protects operational health data if the route changes later |

## Route-to-Permission Matrix

| Route | Method | Current auth | Target permission | Notes |
| --- | --- | --- | --- | --- |
| `/health` | `GET` | public | `ops:health` only if internalized later | Current design keeps it public while the response remains non-sensitive. |
| `/echo` | `POST` | Cognito protected | `debug:echo` | Debug endpoint should not default to broad authenticated access. |
| `/chat` | `POST` | Cognito protected | `chat:invoke` | Smoke-test route only; not the controlled enterprise RAG path. |
| `/documents` | `POST` | Cognito protected | `documents:write` | Write path should require explicit write permission. |
| `/rag/query` | `POST` | Cognito protected | `rag:query` | Route permission must be additive to the existing RAG project and customer policy gate. |
| `/agent/run` | `POST` | Cognito protected | `agent:run` | Tool allowlist and task validation still remain separate. |
| `/approvals/{approvalId}` | `GET` | Cognito protected | `approvals:read` | Read access should eventually be narrower than broad authenticated access. |
| `/approvals/{approvalId}/decision` | `POST` | Cognito protected | `approvals:decide` | Must not replace workflow-state validation. |
| `/approvals/{approvalId}/execute` | `POST` | Cognito protected | `approvals:execute` | Must not replace approval-state or action-type validation. |
| `/incident-reports/{reportId}` | `GET` | Cognito protected | `incident-reports:read` | Report-read permission should be explicit rather than implied by authentication. |

## Role Model

| Role | Intended user | Permissions | Notes |
| --- | --- | --- | --- |
| `ai-user` | normal authenticated analyst or demo user | `rag:query`, `chat:invoke` | Lowest practical interactive role; may also be the main non-admin demo user. |
| `ai-data-admin` | document ingestion owner or content maintainer | `documents:write`, `rag:query`, `chat:invoke` | Separate write capability from broad operational approval rights. |
| `ai-approver` | reviewer allowed to decide approvals | `approvals:read`, `approvals:decide`, `rag:query`, `chat:invoke` | Can review and decide, but should not automatically execute. |
| `ai-operator` | operator allowed to execute approved actions and inspect resulting records | `approvals:read`, `approvals:execute`, `incident-reports:read`, `agent:run`, `rag:query`, `chat:invoke` | Can operate the workflow after approval, but should still depend on backend state validation. |
| `ai-admin` | platform administrator for setup, diagnostics, and emergency access | all permissions above plus `debug:echo` and optionally `ops:health` if internalized | Should not be the main demo user because overbroad access can hide permission bugs. |

`ai-admin` should not be used as the default or main demo identity. If every demo uses an all-powerful role, permission defects can remain invisible until later phases.

## Claim Strategy Options

Three practical options exist for route-permission claims in the PoC.

### Option A: use `scope` claim

Store coarse-grained permissions in the token `scope` claim.

Benefits:

- aligns with common OAuth-style permission naming
- straightforward to interpret for route checks

Limitations:

- can be awkward for custom PoC role composition in Cognito
- may be less convenient than groups for multi-role operational users

### Option B: use `cognito:groups` and backend mapping

Store group membership in `cognito:groups` and resolve permissions in the backend through a group-to-permission map.

Benefits:

- practical for Cognito-based PoC rollout
- keeps tokens relatively compact
- makes role composition clearer for test users such as approver, operator, and admin
- allows one backend mapping layer to evolve without redesigning every route

Limitations:

- adds a backend mapping layer that must stay in sync with group intent
- denied behavior depends on correct backend mapping, not only on token contents

### Option C: use `custom:permissions` claim

Store explicit permissions in a custom token claim such as `custom:permissions`.

Benefits:

- very explicit route-permission representation
- easier to inspect directly in the token

Limitations:

- custom claim packing can become awkward as permission lists grow
- less natural for representing human roles than group membership

## Recommendation for Next Implementation

For the next PoC implementation phase:

- use `cognito:groups` with backend group-to-permission mapping
- keep support for scope lists in `AccessContext` for future use

This gives the PoC a practical role model now without closing off a future move toward explicit `scope`-based authorization.

## Backend Enforcement Design

Proposed backend design:

- add permission resolution to `AccessContext` or to a new helper closely adjacent to it
- map groups and or scopes to effective permissions
- add `assert_permission_allowed(permission, access_context)`
- call the permission check from route handlers before business logic runs
- keep business validation and workflow-state validation unchanged
- keep the RAG project and customer policy gate unchanged

Important design rule:

Route permission checks must not replace:

- RAG project and customer scope checks
- metadata filtering
- approval state validation
- executor action-type validation

The target call flow should be layered, not substitutive:

1. API Gateway authenticates the caller
2. `AccessContext` resolves verified identity and claims
3. route permission check verifies the caller has the required route permission
4. existing business validation still runs
5. RAG policy and filtering still run for RAG paths

## Recommended Implementation Order

Recommended implementation order:

1. protect approval decision and execute with permission checks first
2. protect `documents:write`
3. protect `agent:run`
4. protect `incident-reports:read`
5. protect `chat:invoke` and `debug:echo`
6. optionally internalize health

Why this order is practical:

- approval decision and execute are the highest-risk authenticated actions
- document write is high-risk and easier to reason about than multi-task agent authorization
- agent access exposes operational data and should follow closely behind
- incident report access is sensitive but narrower than execution rights
- chat and echo are lower-risk special-purpose routes after the core workflow is covered

Alternative starting point:

Start with a read-only permission such as `rag:query` if a lower-risk first implementation slice is preferred.

## Evidence Plan

For each permission check, evidence should include:

- valid token with permission succeeds
- valid token without permission returns `403`
- no-token request is still rejected by API Gateway
- business validation still works
- token-mode evaluation is updated with expected allowed and denied cases

Critical evidence to collect in future phases:

- a user with `ai-user` cannot approve
- a user with `ai-approver` can approve but cannot execute
- a user with `ai-operator` can execute but still requires an already approved state
- wrong project or customer filters are still denied by RAG policy even when the route permission exists

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| overbroad `ai-admin` hides bugs | a superuser demo path can make missing permission checks invisible | use narrower test users for positive and negative evidence; avoid using `ai-admin` as the default demo identity |
| token claim changes require re-login | stale tokens can mislead testing after group or permission updates | force a fresh login or token re-issue after claim or group changes |
| group-to-permission mapping drift | backend mapping can diverge from intended role semantics | keep the mapping explicit, versioned, and covered by focused tests |
| confusing authentication and authorization denials | `401` and `403` can be misread during rollout | document clearly whether a denial happened at API Gateway or in backend permission logic |
| route permission check accidentally replaces business validation | permission success could incorrectly bypass approval-state or executor validation | keep business validation calls unchanged and test them independently after permission checks are added |
| tests becoming brittle | too many route-role combinations can make the suite noisy and fragile | add focused permission tests per route slice and keep broad end-to-end cases small and intentional |

## Non-goals

- no implementation in Phase 8Q
- no route-level OAuth scope enforcement yet
- no production IdP federation
- no removal of `trusted_headers` fallback
- no replacement of the RAG policy gate
- no production readiness claim

## Proposed Next Phase

Phase 8S - Expand permission checks beyond approval decision and execute
