# Authorizer Implementation Decision

## Purpose

This document chooses the safest implementation path after the Phase 8B `AccessContext` refactor.

The decision is focused on the next authentication boundary that can be added with minimal disruption to the current PoC. It is design-only and does not claim that Cognito, JWT validation, or an API Gateway authorizer are implemented in the current repository.

## Current State

The current repository state is:

- `AccessContext` exists as the backend-facing auth and authorization contract.
- `auth_source` is currently `trusted_headers`.
- The backend policy gate still validates requested `projectId` and `customerId` filters.
- Missing or empty allowed scope now fails closed when requested filters are present.
- No real authentication boundary is implemented yet.
- No Cognito, JWT validation, or API Gateway authorizer is present in the runtime.

What this means in practice:

- the PoC demonstrates where policy enforcement belongs
- the PoC does not prove caller identity
- the backend policy gate is already separated enough to support a safer next step without rewriting retrieval logic

## Decision Criteria

The next implementation step should satisfy the following criteria:

- minimal disruption to the current PoC
- keeps the backend policy gate unchanged
- supports a later move to Cognito and verified JWT claims
- easy to test with unit tests and curl-based requests
- clear evidence path for allowed and denied cases
- no fake production-readiness claim

## Option A: Cognito User Pool Authorizer

Architecture:

- API Gateway validates a Cognito-issued JWT before the request reaches Lambda
- verified claims are passed through the API Gateway authorizer context
- Lambda maps verified claims into `AccessContext`
- backend policy continues to validate requested `projectId` and `customerId` filters against that context

Benefits:

- uses a standard AWS-native authentication boundary
- moves identity verification to the API boundary instead of the application layer
- aligns well with the long-term target design in the Phase 8A docs
- creates a clear path to issuer, audience, expiry, and signature validation

Risks:

- introduces infrastructure change while the project is still learning the auth contract
- couples claim-shape decisions to Cognito configuration sooner than necessary
- increases the number of moving parts for the next phase
- makes debugging harder if claim mapping and infrastructure change are introduced at the same time

Implementation impact:

- add Cognito user pool configuration
- add API Gateway authorizer wiring
- update route protection rules
- add claim-to-`AccessContext` mapping logic in the backend
- preserve the backend policy gate behavior after identity verification

Evidence required:

- authenticated allowed request succeeds
- missing or invalid token fails at the API boundary
- verified claim scope maps into `AccessContext`
- mismatched `projectId` or `customerId` is still denied by the backend policy gate
- end-to-end evaluation still passes after route protection changes

## Option B: Lambda Authorizer

Architecture:

- API Gateway invokes a Lambda authorizer before the main handler
- the authorizer validates identity or trusted auth inputs and emits a normalized context payload
- Lambda maps that authorizer context into `AccessContext`
- backend policy continues to enforce requested scope against allowed scope

Benefits:

- more flexible than a managed Cognito authorizer
- can normalize claims, roles, and derived scope before the request reaches the main handler
- can support enterprise IdP or external policy lookup patterns later
- preserves the existing separation between authentication and backend policy enforcement

Risks:

- authorizer logic becomes part of the security boundary and must be maintained carefully
- more moving parts than the current PoC needs for the immediate next step
- easier to overbuild before the claim mapping contract is proven
- larger testing surface than a small `AccessContext` source extension

Implementation impact:

- add a new Lambda authorizer function or authorizer integration
- define authorizer output shape and route bindings
- add backend mapping from authorizer context to `AccessContext`
- add tests for authorizer output and policy compatibility

Evidence required:

- authorizer allows valid requests and denies invalid requests
- authorizer context is mapped correctly into `AccessContext`
- backend policy still fails closed on missing scope
- route behavior remains stable for RAG and agent paths
- evaluation still passes after authorizer integration

## Option C: Mock Authorizer Claims Resolver
This mode must never be presented as real authentication because the claims are not cryptographically verified in Phase 8E. It is only a way to test the claim mapping and policy gate behavior before adding real authentication infrastructure.
Architecture:

- add support for `requestContext.authorizer.claims` as a second `AccessContext` source
- continue to support trusted headers for learning and demo compatibility
- do not add token verification yet
- map already-verified-looking authorizer claims into `AccessContext`
- set `auth_source` to `authorizer_claims` or `mock_authorizer_claims` when this path is used
- keep the backend policy gate unchanged

Benefits:

- smallest refactor after Phase 8B
- exercises claim mapping without requiring Cognito or JWT infrastructure immediately
- preserves the current PoC working path while adding a second input mode
- provides a direct bridge from header-based learning mode to real authorizer-backed claims later
- easy to unit test with synthetic Lambda events and curl-compatible local request bodies

Risks:

- the word authorizer can be misunderstood as real authentication if the docs are not explicit
- claims can still be synthetic in this phase, so the trust boundary is not yet real
- the project must be disciplined about keeping trusted headers clearly marked as learning-only

Implementation impact:

- extend `resolve_access_context(event)` to inspect `requestContext.authorizer.claims`
- add deterministic claim parsing and fail-closed behavior for missing scope claims
- preserve the current trusted-header mode for compatibility
- add tests covering both access-context sources without changing the backend policy gate

Evidence required:

- existing trusted-header tests still pass
- authorizer-claims mapping tests pass
- `auth_source` reflects the claim-based source when used
- missing project or customer claims fail closed when requested filters are present
- existing RAG evaluation still passes after the resolver extension

## Decision

Option C is the recommended next implementation step, followed later by a Cognito User Pool authorizer.

Decision rationale:

- Next implementation phase should add an authorizer-claims resolver mode.
- It should not add Cognito yet.
- It should not verify JWT yet.
- It should only map already-verified-looking authorizer claims into `AccessContext`.
- This keeps the refactor small and testable.

Why this is the safest path:

- it changes one narrow abstraction boundary instead of changing infrastructure and backend logic together
- it keeps the existing backend policy gate intact
- it allows evidence collection around claim mapping before a real trust boundary is introduced
- it reduces the chance of disrupting the currently working PoC

## Proposed Phase Plan

- 8D: decision doc
- 8E: implement authorizer-claims resolver mode
- 8F: evidence run for claims resolver
- 8G: add Cognito and User Pool authorizer infrastructure
- 8H: real JWT evidence run

## Target AccessContext Sources

| Source | auth_source | Input location | Trust level | Phase | Notes |
| --- | --- | --- | --- | --- | --- |
| trusted headers | `trusted_headers` | request headers | low | current through 8E | Learning-only source. Keep for compatibility until real auth is in place. |
| mock authorizer claims | `mock_authorizer_claims` | `requestContext.authorizer.claims` | low to medium for internal testing only | 8E | Useful for testing claim mapping before token verification exists. |
| Cognito authorizer claims | `cognito_authorizer_claims` | `requestContext.authorizer.claims` from API Gateway Cognito authorizer | high relative to current PoC | 8G | Target AWS-native verified-claims path. |
| Lambda authorizer context | `lambda_authorizer_context` | `requestContext.authorizer` | depends on authorizer correctness | future alternative | Useful when custom principal or policy lookup logic is required. |

## Claims Mapping for 8E

The 8E mock authorizer-claims resolver should expect the following claims when present:

- `sub`
- `username` or `preferred_username`
- `custom:project_ids`
- `custom:customer_ids`
- `scope`
- `cognito:groups`

Recommended 8E mapping intent:

- `sub` becomes the stable principal identifier
- `username` or `preferred_username` can provide a human-readable user identifier
- `custom:project_ids` maps to `allowed_project_ids`
- `custom:customer_ids` maps to `allowed_customer_ids`
- `scope` maps to coarse-grained `scopes`
- `cognito:groups` maps to `groups`

Important 8E rule:

- missing required project or customer scope claims must fail closed when the request asks for those filters

## Non-goals

- no Cognito in 8D
- no JWT validation in 8D
- no CloudFormation authorizer change in 8D
- no route protection change in 8D
- no removal of trusted headers in 8D
- no production-ready auth claim

## Acceptance Criteria for 8E

- existing trusted-header tests still pass
- new authorizer-claims tests pass
- authorizer claims source maps to `AccessContext`
- missing claims fail closed
- backend policy gate remains unchanged
- no Cognito or JWT code is added
- `run_rag_eval` still passes