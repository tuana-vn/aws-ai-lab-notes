# Audit Event Schema

## Purpose

This document defines a practical audit event shape for Phase 9A.

It does not claim that every event in this schema is already emitted by the current runtime. The current repository already emits structured JSON logs for several flows and persists trace records for selected routes. This schema is the normalization target for future audit-oriented logging and dashboard work.

## Design Principles

- keep the schema small enough to emit from Lambda handlers without new infrastructure
- keep route, request, user, and decision fields explicit
- separate required core fields from route-specific optional fields
- support current PoC flows: RAG, agent tasks, approval lifecycle, and internal incident report creation
- avoid secrets, passwords, full JWTs, or raw token capture

## Common Audit Event Fields

| Field | Required | Type | Purpose |
| --- | --- | --- | --- |
| `eventType` | yes | string | Normalized audit event name |
| `timestamp` | yes | string | ISO 8601 UTC event time |
| `requestId` | yes for request-scoped events | string | Primary correlation ID across response, logs, and trace |
| `path` | yes for route-scoped events | string | API path or logical route |
| `method` | optional | string | HTTP method when relevant |
| `status` | optional | string | Outcome such as `completed`, `blocked`, `denied`, `failed`, `approval_required` |
| `httpStatusCode` | optional | number | Response code when available |
| `userId` | optional | string | Human-readable application user identifier |
| `principalId` | optional | string | Stable identity principal if available |
| `authSource` | optional | string | Example: `cognito_authorizer_claims` or `trusted_headers` |
| `groups` | optional | array of strings | Effective group membership used for route permission logic |
| `permissions` | optional | array of strings | Effective permissions if resolved |
| `routeCategory` | optional | string | Example: `rag`, `agent`, `approval`, `incident_report`, `debug` |
| `message` | optional | string | Short operator-facing summary |
| `errorType` | optional | string | Error classification for failures |
| `errorMessage` | optional | string | Sanitized failure reason |
| `latencyMs` | optional | number | End-to-end Lambda latency for the handled request |
| `filters` | optional | object | Requested `projectId`, `customerId`, `documentType` filters |
| `policyDecision` | optional | string | `allowed` or `denied` |
| `policyReason` | optional | string | Reason for policy result |
| `guardrailAction` | optional | string | `allow`, `block`, or warning-oriented value |
| `guardrailReason` | optional | string | Guardrail reason such as `prompt_injection` |
| `guardrailMatchedRule` | optional | string | Specific input rule ID when matched |
| `outputGuardrailAction` | optional | string | `allow`, `warn`, or other normalized outcome |
| `outputGuardrailReason` | optional | string | Why output guardrail fired or allowed |
| `outputGuardrailWarnings` | optional | array of strings | Warning list when output guardrail is not clean |
| `eligibleChunkCount` | optional | number | RAG candidate count after metadata filtering |
| `sourceCount` | optional | number | Grounded source count |
| `toolName` | optional | string | Agent tool name |
| `toolStatus` | optional | string | Agent tool call outcome |
| `task` | optional | string | Agent task name |
| `approvalId` | optional | string | Approval workflow record ID |
| `decision` | optional | string | Approval decision value |
| `executionStatus` | optional | string | Approval execution state |
| `actionType` | optional | string | Proposed or executed action type |
| `reportId` | optional | string | Incident report identifier |

## Recommended `eventType` Values

| Event type | When to emit |
| --- | --- |
| `request_received` | Request accepted by the Lambda handler before business work begins |
| `request_completed` | Request completed successfully or with a known functional outcome |
| `auth_context_resolved` | `AccessContext` resolved and identity context is known |
| `policy_allowed` | Requested scope or action passed policy validation |
| `policy_denied` | Requested scope or action was denied by backend policy or permission logic |
| `input_guardrail_blocked` | Input guardrail blocked the request before retrieval or model use |
| `output_guardrail_warning` | Output guardrail raised a warning after model generation |
| `rag_no_source` | Retrieval completed without grounded evidence above threshold |
| `rag_answered_with_sources` | Grounded RAG response completed with one or more sources |
| `agent_task_started` | Agent task execution began |
| `agent_tool_called` | An allowlisted tool was called by the agent |
| `agent_tool_failed` | A tool call failed or returned an operator-significant failure |
| `approval_created` | Approval record created from an approval-required proposal |
| `approval_decided` | Approval record received an `approved` or `rejected` decision |
| `approval_execute_requested` | Execution endpoint invoked for an approval |
| `approval_execute_denied` | Execution attempt denied by permission or state validation |
| `approval_executed` | Approved internal action executed successfully |
| `incident_report_created` | Internal incident report record created |
| `error` | Unexpected runtime failure not captured by the more specific event types |

## Required vs Optional Guidance

Required for every emitted audit event:

- `eventType`
- `timestamp`
- at least one correlation field: `requestId`, `approvalId`, or `reportId`
- enough route or workflow context to make the event operator-usable without reading source code

Required for route-scoped request events:

- `requestId`
- `path`
- `status`

Required for policy and guardrail events:

- `requestId`
- `path`
- `eventType`
- the reason field relevant to that outcome

Required for approval workflow events:

- `approvalId`
- `eventType`
- `status` or `executionStatus` depending on the stage

Optional fields should only be emitted when they are already known by the handler or service. Do not invent values only to fill the schema.

## Field Naming Compatibility

Current runtime logs may still use snake_case fields, while the normalized audit schema may use camelCase fields.

During migration, query documents and helper scripts should support both naming styles.

- do not rename existing runtime fields unless the code is intentionally migrated
- do not invent values only to fill the normalized schema
- new audit events should prefer one consistent naming convention
- compatibility queries may read both naming styles during migration

Examples:

```text
request_id -> requestId
user_id -> userId
latency_ms -> latencyMs
source_count -> sourceCount
eligible_chunk_count -> eligibleChunkCount
guardrail_action -> guardrailAction
approval_id -> approvalId
report_id -> reportId
execution_status -> executionStatus
```

## Example Events

### Policy denied RAG request

```json
{
  "eventType": "policy_denied",
  "timestamp": "2026-05-29T10:15:22Z",
  "requestId": "req-12345",
  "path": "/rag/query",
  "method": "POST",
  "routeCategory": "rag",
  "status": "denied",
  "httpStatusCode": 403,
  "userId": "approver-demo",
  "authSource": "cognito_authorizer_claims",
  "filters": {
    "projectId": "other-project",
    "customerId": "internal"
  },
  "policyDecision": "denied",
  "policyReason": "requested projectId is outside allowed scope",
  "message": "Authenticated caller was denied by backend RAG policy."
}
```

### Input guardrail blocked request

```json
{
  "eventType": "input_guardrail_blocked",
  "timestamp": "2026-05-29T10:18:04Z",
  "requestId": "req-23456",
  "path": "/rag/query",
  "method": "POST",
  "routeCategory": "rag",
  "status": "blocked",
  "httpStatusCode": 200,
  "userId": "user-learning",
  "guardrailAction": "block",
  "guardrailReason": "prompt_injection",
  "guardrailMatchedRule": "ignore_previous_instructions",
  "message": "Request was blocked before retrieval and model invocation."
}
```

### RAG no-source response

```json
{
  "eventType": "rag_no_source",
  "timestamp": "2026-05-29T10:22:11Z",
  "requestId": "req-34567",
  "path": "/rag/query",
  "method": "POST",
  "routeCategory": "rag",
  "status": "no_source",
  "httpStatusCode": 200,
  "userId": "user-learning",
  "filters": {
    "projectId": "learning",
    "customerId": "internal",
    "documentType": "technical-note"
  },
  "eligibleChunkCount": 1,
  "sourceCount": 0,
  "message": "No chunk passed the configured similarity threshold."
}
```

### Approval decision

```json
{
  "eventType": "approval_decided",
  "timestamp": "2026-05-29T10:30:45Z",
  "approvalId": "approval-123",
  "path": "/approvals/approval-123/decision",
  "method": "POST",
  "routeCategory": "approval",
  "status": "approved",
  "httpStatusCode": 200,
  "userId": "approver-user",
  "decision": "approved",
  "executionStatus": "approved_not_executed",
  "message": "Approval decision recorded without executing the action."
}
```

### Approved action execution

```json
{
  "eventType": "approval_executed",
  "timestamp": "2026-05-29T10:36:02Z",
  "approvalId": "approval-123",
  "path": "/approvals/approval-123/execute",
  "method": "POST",
  "routeCategory": "approval",
  "status": "executed",
  "httpStatusCode": 200,
  "userId": "operator-user",
  "actionType": "create_incident_report",
  "executionStatus": "executed",
  "reportId": "report-456",
  "message": "Approved internal action executed by creating an incident report record."
}
```

## Current PoC Notes

Current repository alignment with this schema:

- RAG and agent flows already emit structured JSON logs and trace records that map well to many of these fields
- approval and incident report flows currently have weaker log normalization and rely more on DynamoDB state than on explicit audit events
- this schema should therefore be treated as a target contract for Phase 9A follow-on work, not as a claim that every event already exists in CloudWatch Logs today
