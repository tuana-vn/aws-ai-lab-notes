# Phase 10E Reliability Hardening Plan

## Purpose

This document defines a practical reliability-hardening plan for the current `aws-ai-platform-poc` baseline.

The goal is to make retry behavior, idempotency expectations, failure recovery, rollback, and environment separation explicit before broader rollout. This phase is documentation only. It does not add DLQs, retry infrastructure, idempotency keys, deployment automation, or new AWS resources.

## Current Baseline

The current repository baseline includes:

- API Gateway, Lambda, DynamoDB, CloudWatch Logs, Cognito, Bedrock Runtime, and SAM
- `GET /health` as a public route
- Cognito protection on all non-health routes
- `/rag/query` with `AccessContext`, input guardrail, backend policy gate, metadata filter, retrieval, `no_source` behavior, grounded Bedrock generation, output guardrail, traces, logs, and Bedrock token-usage visibility where available
- `/agent/run` constrained to controlled tasks and allowlisted tools
- approval decision requiring `approvals:decide`
- approval execute requiring `approvals:execute`
- execution limited to `create_incident_report`
- successful execution creating an internal DynamoDB incident report record
- Phase 9 approval and execution audit events and a basic CloudWatch dashboard
- Phase 10D security-planning documents for WAF, CloudTrail, alarms, and retention

The current PoC does not yet define an explicit retry policy, DLQ strategy, idempotency model, rollback checklist, or production environment-promotion workflow.

## What This Phase Does Not Implement

This phase does not implement:

- application retry logic
- DLQs
- Step Functions, queues, or event-driven recovery flows
- idempotency keys or deduplication records
- DynamoDB schema changes
- approval workflow behavior changes
- deployment automation or CI/CD
- environment-specific infrastructure expansion
- new alarms or AWS resources

## Reliability Hardening Goals

The Phase 10E goals are:

- define where synchronous retries are safe and where they are dangerous
- identify which routes are naturally read-like and which routes have write or replay risk
- define the first idempotency expectations for approval decision, approval execution, and document ingestion
- define how write failures should be handled when they affect traces, audit events, or business records differently
- define practical rollback and environment-separation expectations before production-style deployment discussion

## Reliability Areas

### Synchronous API Gateway To Lambda Behavior

The current platform is dominated by synchronous API Gateway to Lambda calls. That has two direct consequences:

- the caller experiences the Lambda result directly, including timeouts and downstream failures
- some failures happen after partial work has already occurred, which creates replay risk if the client retries

This means reliability hardening must focus on request-level side effects, not just background recovery patterns.

### Lambda Timeout And Retry Expectations

The SAM template sets a global function timeout of 10 seconds. The current repository does not define an explicit automatic retry policy for synchronous routes.

That means the main practical questions are:

- what happens if the client retries after a timeout or ambiguous network failure
- which handlers can safely absorb that retry
- which handlers risk duplicate writes or duplicate downstream work

### DynamoDB Write Failure Behavior

Current write paths include:

- trace writes
- document chunk writes
- approval writes
- incident report writes

These writes do not currently use a broader transactional or deduplication strategy. Some write failures are business-critical. Others are observability-critical. Those two categories should not be treated the same.

### Trace / Audit Write Failure Behavior

Current code generally performs trace persistence inline in the request path. In several handlers, a trace-write failure can still fail the user-facing request even when the main response payload was otherwise available.

That is acceptable for a PoC, but it is not the final reliability posture. The platform should decide explicitly whether trace and audit persistence are hard requirements for a given route or whether they should degrade without breaking the core user path.

### Approval Decision Idempotency

The current approval decision path updates the approval record directly. It does not document repeated-decision handling as a formal idempotency rule.

Two future expectations should be made explicit:

- repeating the same decision for the same approval should be safe
- conflicting repeated decisions after the approval is already in a terminal state should be rejected clearly

### Approval Execution Idempotency

Approval execution currently creates an incident report first and marks the approval executed second.

That execution order matters. If incident report creation succeeds but the approval update or response path fails, a retry can create a second incident report for the same approval because the approval may still look executable.

This was the highest-value replay-safety gap in the current repository. Phase 10F is the first implementation slice for this area: it makes execute replay-safe when the approval is already marked `executed` with a stored report reference. The narrower partial-failure case still remains.

### Incident Report Creation Replay Safety

Incident report creation is currently tied to approval execution and uses a new generated `report_id` per execution attempt.

Without a deduplication rule or idempotent execution key, repeated execution attempts after partial failure can create duplicate business records.

### Bedrock Call Failure And Timeout Behavior

Current Bedrock-backed routes return failure responses when Bedrock invocation fails. They do not define:

- automatic retry rules
- timeout budgets per Bedrock call type
- operator guidance for repeated downstream model failures

This is especially relevant for `/chat`, `/rag/query`, and `/agent/run` when `answer_question` uses the shared RAG path.

### Partial Failure Handling

The platform already has several partial-failure shapes that matter more than simple success or failure:

- a trace write can fail after the answer is already available
- `/documents` deletes prior chunks before saving replacement chunks
- approval execution can create an incident report before marking the approval executed
- a client timeout can leave the caller uncertain whether the write happened

Reliability hardening must address these ambiguous states explicitly.

Phase 10G is the document-ingestion follow-up design for this area. It focuses on safer replacement so old chunks remain available until a new chunk set is fully ready.

### Deployment Rollback

The repository uses SAM and CloudFormation, but does not yet document a production rollback workflow.

That gap matters because deployment reliability is not just about infrastructure rollback. It also includes:

- release evidence before deployment
- smoke tests immediately after deployment
- operator criteria for rollback versus forward-fix

### Environment Separation

The template supports an `EnvironmentName` parameter and the repo includes a default deploy configuration for `dev`, but the repository does not yet document a full multi-environment promotion model.

That means environment separation is currently a target strategy, not an implemented operating model.

## Prioritized Recommendations

### P0

- define idempotency and replay-safety rules for `POST /approvals/{approvalId}/execute`
- define repeated-decision behavior for `POST /approvals/{approvalId}/decision`
- define write-failure handling for `/documents`, especially delete-then-save replacement behavior
- define a deployment rollback checklist and post-deploy smoke-test set

### P1

- define which trace and audit writes are hard requirements versus best-effort evidence writes
- define timeout and retry expectations for Bedrock-backed synchronous routes
- define a target environment-promotion model beyond the current default `dev` deployment shape

### P2

- evaluate where event-driven recovery or DLQ-backed patterns would matter if the platform later adds asynchronous workflows
- refine route-specific retry guidance once production-like traffic and timeout data exist

## Suggested Future Implementation Order

1. document and implement replay protection for approval execution
2. document and implement safe repeated-decision handling for approval decision
3. document and implement safer document-ingestion replacement behavior
4. separate critical business writes from best-effort trace writes
5. define rollback checklist, smoke tests, and release evidence requirements
6. define environment-promotion and configuration-separation strategy
7. evaluate future asynchronous recovery patterns only where synchronous request paths are no longer enough

## Acceptance Criteria

Phase 10E is acceptable when:

- the plan describes the current baseline honestly
- it distinguishes read-like retries from write-path replay risks
- it identifies approval execution replay safety as a top-priority issue
- it explains why DLQ is not the default answer for synchronous API routes
- it separates current deployment reality from future environment and rollback strategy
- it does not claim retry, DLQ, idempotency, rollback, or environment-promotion controls are already implemented

## Current Implementation Boundary

Current implementation means:

- synchronous API Gateway to Lambda request paths dominate the platform
- trace, document, approval, and incident-report writes happen inline in request handlers
- no platform-wide idempotency-key model is implemented
- replay protection is currently partial and route-specific
- Phase 10F added replay-safe behavior for already-executed approvals with a stored report reference
- Phase 10G documents the target safer replacement design for document ingestion, but it is not implemented yet
- no deployment rollback checklist or multi-environment promotion model is documented

## Future Roadmap Boundary

Future roadmap means:

- replay protection for critical writes
- explicit retry and timeout guidance
- rollback and promotion checklists
- possible event-driven recovery patterns only where justified

These are planning targets only. They are not implemented by this document.