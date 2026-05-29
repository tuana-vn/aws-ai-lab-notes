# Idempotency And Retry Review

## Purpose

This document reviews idempotency and retry behavior for the current `aws-ai-platform-poc` routes.

The intent is practical: identify where repeated requests are mostly harmless, where they create duplicate evidence only, and where they risk duplicate or inconsistent business records.

## Current Idempotency Posture

The current repository does not implement a platform-wide idempotency strategy.

Current behavior is mixed:

- some routes are effectively read-only
- some routes are safe to repeat from a business-state perspective but will create duplicate traces, logs, or Bedrock cost
- some write paths can create duplicate or ambiguous outcomes if a client retries after timeout or partial failure

## Why Idempotency Matters For This Platform

Idempotency matters here because the platform combines:

- synchronous API calls
- downstream model calls
- inline persistence of traces and business records
- approval-controlled execution that creates internal records

In this shape, client retries after timeouts or network ambiguity are realistic. Without clear idempotency rules, the same request can produce duplicate evidence, duplicate work, or duplicate records.

## Route-by-route Review

### GET /health

- Current behavior: returns a simple health response.
- Side effects: none.
- Retry risk: low.
- Idempotency expectation: naturally idempotent.
- Recommended hardening: keep the route side-effect free and non-sensitive.
- Priority: P2.

### POST /echo

- Current behavior: validates the message, generates a new `request_id`, saves a trace record, and returns the message.
- Side effects: one trace write and one structured log per call.
- Retry risk: repeating the same request creates duplicate trace records with different request IDs.
- Idempotency expectation: business-state impact is low, but evidence is not idempotent.
- Recommended hardening: if the route remains useful, treat trace persistence as optional evidence or add an explicit request-idempotency model if duplicate traces become a problem.
- Priority: P2.

### POST /chat

- Current behavior: validates the message, calls Bedrock Converse, writes a trace record, logs completion, and returns the answer.
- Side effects: one Bedrock generation call, one trace write, and one success log per call.
- Retry risk: repeating the same request can duplicate Bedrock cost and duplicate trace records.
- Idempotency expectation: not idempotent from a cost and evidence perspective, even though no business record is created.
- Recommended hardening: define whether clients may retry on timeouts, and if so, under what timeout and request-correlation rules.
- Priority: P1.

### POST /documents

- Current behavior: chunks the document, generates embeddings, deletes prior chunks for `documentId`, then saves the new chunk set.
- Side effects: embedding calls, delete operations, and replacement writes to `DocumentChunksTable`.
- Retry risk: a repeated call with the same payload may converge to the same final chunk set, but partial failure can still leave data missing or partially replaced. A retry after delete-and-before-save is the main risk.
- Idempotency expectation: not fully idempotent today because replacement is not guarded by versioning, staging, or an idempotency key.
- Recommended hardening: define document-ingestion idempotency around `documentId`, optional version, and a safer replacement model that avoids destructive partial replacement.
- Priority: P0.

### POST /rag/query

- Current behavior: runs the shared RAG path, may call embeddings and Bedrock, writes traces for blocked, `no_source`, and completed flows, and logs outcomes.
- Side effects: trace writes, logs, embedding calls, and sometimes Bedrock generation calls.
- Retry risk: repeated requests can duplicate cost and traces, but they do not create business records.
- Idempotency expectation: functionally retryable from a business-state perspective, but not cost-idempotent or evidence-idempotent.
- Recommended hardening: define whether trace-write failure should break the request and define client retry guidance for Bedrock-related timeouts.
- Priority: P1.

### POST /agent/run

- Current behavior: behavior varies by task. Read-like tasks inspect traces or logs; `answer_question` uses the shared RAG path; `propose_incident_report` creates a new approval record.
- Side effects: trace writes on every task; some tasks also invoke RAG or create approval records.
- Retry risk: read-like tasks mainly duplicate traces and downstream lookups, but `propose_incident_report` can create duplicate approval records if retried.
- Idempotency expectation: mixed. Read-like tasks are lower risk; proposal creation is not idempotent today.
- Recommended hardening: separate read-only task retry guidance from proposal-creation guidance, and define deduplication expectations for repeated proposal requests.
- Priority: P0 for proposal creation, P1 for the rest.

### GET /approvals/{approvalId}

- Current behavior: reads and returns the approval record when it exists.
- Side effects: none in application state.
- Retry risk: low.
- Idempotency expectation: naturally idempotent.
- Recommended hardening: keep it read-only and add permission scoping later if the approval-read surface expands.
- Priority: P2.

### POST /approvals/{approvalId}/decision

- Current behavior: validates permission, parses the decision body, and updates the approval record with decision state, decision timestamp, comment, and execution status.
- Side effects: updates the approval record and writes an audit event.
- Retry risk: repeated identical decisions will still rewrite timestamps and decision metadata; conflicting repeated decisions can mutate approval state again because the current code does not enforce terminal-decision immutability.
- Idempotency expectation: repeated same-decision calls should become safe; conflicting repeated decisions should be rejected once the record is already decided.
- Recommended hardening: define same-decision idempotency explicitly and prevent conflicting re-decision after terminal decision unless an explicit override flow is introduced later.
- Priority: P0.

### POST /approvals/{approvalId}/execute

- Current behavior: validates permission, returns the existing `reportId` when the approval is already marked `executed` with a stored report reference, and otherwise creates an incident report with a new generated `report_id` before marking the approval executed.
- Side effects: creates an incident report record, updates the approval record, and writes audit events.
- Retry risk: Phase 10F removes the already-executed replay case when `execution_status=executed` and a stored report reference exists. The remaining risk is the narrower partial-failure case where incident report creation succeeds but approval state is not updated with the report reference.
- Idempotency expectation: execution should return the existing incident report when the approval is already marked executed with a stored report reference.
- Recommended hardening: keep the Phase 10F replay behavior and address the remaining partial-failure gap later with a transaction, deterministic report ID, or conditional write strategy.
- Priority: P0.

### GET /incident-reports/{reportId}

- Current behavior: reads and returns the incident report record when it exists.
- Side effects: none.
- Retry risk: low.
- Idempotency expectation: naturally idempotent.
- Recommended hardening: keep it read-only and add broader read-permission hardening separately.
- Priority: P2.

## Special Focus

### Approval Execute Must Not Create Duplicate Incident Reports If Retried

This is the most important current idempotency gap.

Current execution order is:

1. create incident report
2. mark approval executed
3. return success

Phase 10F closes the broader replay case where the approval is already marked `executed` with a stored report reference. The remaining replay window is narrower: step 1 can still succeed before step 2 stores the report reference on the approval.

### Approval Decision Should Be Safe If Repeated With The Same Decision

The safest future rule is:

- same approval ID plus same decision should be treated as safe repeat behavior
- same approval ID plus conflicting decision should be rejected after terminal decision unless the platform later defines an explicit override model

### Document Ingestion May Need documentId / version / idempotency key

`POST /documents` already uses `documentId`, but the current flow still performs destructive replacement without a versioned or staged write model.

That means the route likely needs at least one of these later:

- explicit document versioning
- request idempotency key
- safer replacement flow that does not delete the old chunk set until the new set is ready

### Trace / Log Write Failures Should Not Break Core User Path Unless Explicitly Required

Today, several handlers perform trace persistence inline. In practice that means trace-write failures can still fail an otherwise successful request.

Future hardening should decide route by route:

- which routes require durable audit evidence before success is returned
- which routes can degrade observability without breaking the user path

## Current Implementation Boundary

Current implementation means idempotency is still partial and route-specific, but approval execute now has replay-safe behavior for already-executed approvals with a stored report reference.

## Future Roadmap Boundary

Future roadmap means explicit replay protection for critical write paths, especially approval execution and document replacement.