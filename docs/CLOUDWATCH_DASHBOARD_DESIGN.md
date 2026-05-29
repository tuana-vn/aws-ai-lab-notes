# CloudWatch Dashboard Design

## Purpose

This document defines a practical CloudWatch dashboard design for the current AWS AI Platform PoC.

It does not claim that a dashboard has already been deployed. It describes the sections, widgets, and Logs Insights queries that would give operators a useful view of the current runtime without pretending that more telemetry exists than the repository actually emits today.

## Design Principles

- start from existing Lambda log groups and current structured logs
- use DynamoDB-backed traces and approval records as companion evidence, not as direct CloudWatch widget sources
- keep the dashboard focused on operator questions rather than generic infrastructure charts
- distinguish clearly between current signals and future metrics or services

## Proposed Dashboard Sections

### 1. Platform Runtime Health

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| Requests by status | CloudWatch Logs Insights on route log groups | count by `status` where present | Whether the platform is mostly `completed`, `blocked`, `denied`, `no_source`, or `failed` |
| Requests by route | CloudWatch Logs Insights on all current Lambda log groups | derive route from `path` when present or fallback to `@log` | Which routes are active and where traffic concentrates |
| Error events by route | CloudWatch Logs Insights | `@message like /ERROR|error|failed/` with route grouping fallback | Where operator attention is needed |
| Latency by route | CloudWatch Logs Insights | aggregate `latency_ms` where present | Whether `/rag/query` or `/agent/run` is degrading |

### 2. RAG Quality and Grounding

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| RAG outcomes | `/rag/query` log group | count by `status` for `completed`, `no_source`, `blocked`, `denied`, `failed` | Whether retrieval quality or policy denials are changing |
| No-source trend | `/rag/query` log group | filter `status="no_source"` | Whether grounded evidence is becoming harder to find |
| Source count distribution | `/rag/query` log group | stats on `source_count` where present | Whether successful answers are thinly sourced |
| Eligible chunk count | `/rag/query` log group | stats on `eligible_chunk_count` where present | Whether metadata filtering is narrowing the result set too aggressively |

### 3. Security Boundary and Policy Denial

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| Policy denied requests | `/rag/query` log group | filter `status="denied"` or `@message like /denied/` | Whether the backend scope boundary is actively denying out-of-scope requests |
| Unauthenticated access evidence | external manual tests plus auth evidence docs | not a direct CloudWatch widget today | Confirms API Gateway denies no-token requests before Lambda |
| Approval permission denials | approvals log group if future audit events are added; otherwise manual evidence | query by `approval_execute_denied` or fallback raw message | Shows whether approval permission boundaries are being exercised |

API Gateway and Cognito authorizer rejections may not appear in Lambda log groups because no-token requests can be rejected before Lambda invocation.

### 4. Guardrail and Abuse Detection

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| Input guardrail blocks | `/rag/query` log group | count by `guardrail_reason` and `guardrail_matched_rule` | Which unsafe request patterns are most common |
| Output guardrail warnings | `/rag/query` log group | filter `output_guardrail_action="warn"` | Whether answer quality warnings are increasing |
| Blocked request samples | `/rag/query` log group | recent blocked events with request IDs | Gives operators concrete examples for investigation |

### 5. Agent Tool Execution

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| Agent tasks by status | `/agent/run` log group | count by `task` and `status` | Which bounded agent paths are being used |
| Agent tool calls | `/agent/run` log group | extract `tool_calls` when present or fallback on task-specific messages | Which tools are being called and whether they succeed |
| Blocked investigations | `/agent/run` log group | filter `task="investigate_recent_blocks"` | Whether the investigation path is being used as expected |
| Approval-required proposals | `/agent/run` log group | filter `status="approval_required"` | Whether proposal flows are creating approvals instead of executing actions |

### 6. Approval and Internal Action Audit

| Widget name | Data source | Intended query or signal | What it tells the operator |
| --- | --- | --- | --- |
| Approval decisions | approvals handler log group after future normalization; currently DynamoDB is primary evidence | query `approval_decided` or fallback raw message search | How many proposals were approved or rejected |
| Execution attempts | approvals handler log group after future normalization; currently DynamoDB is primary evidence | query `approval_execute_requested` or fallback raw message search | Whether execution is attempted frequently |
| Executed internal actions | approvals handler log group plus incident report records | query `approval_executed` or search for `reportId` | Whether approved actions led to internal incident report creation |
| Incident reports created | incident report table and execution result | not a direct log widget today | Confirms the executor only created internal DynamoDB records |

## Suggested Logs Insights Query Patterns

The query details are collected in [docs/SECURITY_AUDIT_QUERIES.md](docs/SECURITY_AUDIT_QUERIES.md). The dashboard should reuse those patterns rather than inventing a second query vocabulary.

Preferred current log groups to query:

- `/aws/lambda/<RagQueryFunction>`
- `/aws/lambda/<AgentRunFunction>`
- `/aws/lambda/<DocumentsFunction>`
- `/aws/lambda/<ChatFunction>`
- `/aws/lambda/<EchoFunction>`
- `/aws/lambda/<ApprovalsFunction>`
- `/aws/lambda/<IncidentReportsFunction>`

## Current PoC Limitations

- there is no deployed CloudWatch dashboard resource yet
- CloudWatch Logs are the primary dashboard source, while DynamoDB traces, approval records, and incident report records remain companion evidence
- not every handler emits normalized structured JSON logs
- approval and incident report handlers currently rely more on DynamoDB records than on explicit audit log events
- DynamoDB traces are useful companion evidence but are not native CloudWatch dashboard data sources
- no CloudWatch metrics or alarms are emitted specifically for guardrail blocks, denies, approvals, or executions
- no per-user operational metric stream exists yet

## Future Improvements

These are future improvements only. They are not implemented by the current repository.

- add normalized audit events for approvals and internal execution
- add CloudWatch metric filters and alarms for denies, guardrail blocks, execution denials, and execution failures
- add CloudTrail-based change and access visibility where it helps operator workflows
- add WAF metrics if an internet-facing protection layer is introduced later
- add X-Ray or OpenTelemetry only if cross-service tracing becomes necessary
- add cost and token usage telemetry for Bedrock-backed flows
- evaluate Bedrock-managed observability features only if they match the future runtime shape

## Implementation Guidance

The safest implementation order after this design is:

1. normalize approval and execution audit events
2. stabilize Logs Insights queries across RAG and agent flows
3. add a dashboard definition only after the event fields are stable
4. add alarms after normal baseline behavior is known
