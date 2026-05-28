# Chat and Echo Route Decision

## Purpose

This document decides how to handle the remaining non-core routes after the main RAG, agent, approval, and incident-report routes have been protected.

It is a decision document only. It does not implement route protection, route removal, or any runtime changes.

## Current Route Status

| Route | Current status | Current purpose | Risk if public | Recommended decision |
| --- | --- | --- | --- | --- |
| `GET /health` | public | basic service-health check | low if the response remains non-sensitive; higher if operational or environment details are added later | keep public only while it remains non-sensitive; otherwise convert to an internal-only authenticated route |
| `POST /chat` | unprotected and still deployed | Bedrock smoke-test endpoint | moderate because it invokes the model without the controlled RAG metadata and policy boundary | if retained, protect with Cognito in the next implementation phase and label it as smoke-test only |
| `POST /echo` | unprotected and still deployed | debug endpoint for API Gateway and Lambda request handling | moderate because it may reflect request payloads, headers, or other debugging context | protect it if still needed, or disable or remove it in later cleanup |

## /chat Assessment

`POST /chat` remains useful as a Bedrock smoke-test endpoint.

It is not the controlled enterprise RAG path. Unlike `POST /rag/query`, it does not apply the same document retrieval flow, metadata boundary, or policy-driven filter checks. For that reason, it should not be presented as the main platform path in demos, walkthroughs, or future platform messaging.

If the route remains deployed, it should be protected by Cognito in a later implementation phase. For customer-facing demos or workflow explanations, prefer `POST /rag/query` for grounded answer behavior and `POST /agent/run` for controlled agent behavior.

## /echo Assessment

`POST /echo` is useful for debugging API Gateway integration, Lambda request shape, and basic request plumbing.

Its business value is low, and it carries more exposure risk than user value if it remains publicly reachable. Depending on the implementation and request content, an echo endpoint can accidentally expose request payloads or headers in a way that is appropriate for debugging but not for an exposed platform surface.

If it is still needed after the main auth rollout, it should be protected. If it is no longer needed outside development or internal debugging, it should be disabled or removed in a later cleanup phase.

## Recommended Decision

- Keep `GET /health` public only if it continues to return no sensitive information.
- Protect `POST /chat` in the next implementation phase if it remains deployed.
- Protect `POST /echo` if it remains deployed.
- Consider disabling or removing `POST /echo` in later cleanup.
- Clearly label `POST /chat` as smoke-test only and not as the main enterprise RAG path.

## Proposed Next Phase

Recommended next phase:

Phase 8O - Protect `/chat` and `/echo` or disable `/echo`.

## Evidence Requirements for Future Implementation

For `POST /chat`:

- no-token `/chat` should return `401` or `403` if the route is protected
- valid-token `/chat` should still return a Bedrock response
- documentation should explicitly state that `/chat` is smoke-test only

For `POST /echo`:

- no-token `/echo` should return `401` or `403` if the route is protected
- valid-token `/echo` should still return the expected echo response
- if the route is removed instead of protected, it should return `404` or no longer be deployed

## Non-goals

- no code changes in this phase
- no route protection in this phase
- no removal of `/chat` or `/echo` in this phase
- no production readiness claim
