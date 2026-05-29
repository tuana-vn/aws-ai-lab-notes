# Phase 9B Approval Execution Audit Events

## Purpose

Phase 9B adds low-risk structured audit logging for approval creation, approval decision, approval execution requests, denied execution attempts, successful execution, and internal incident report creation.

This phase is instrumentation only. It adds CloudWatch audit visibility alongside the existing DynamoDB workflow state. It does not change approval business behavior, route permissions, or the executor scope.

## Current Gap From Phase 9A

Phase 9A defined the target audit schema and Logs Insights queries, but the approval and execution flows were still less normalized than the RAG and agent paths.

Before this phase:

- approval workflow state existed in DynamoDB
- execution results existed in DynamoDB
- CloudWatch audit queries for approval lifecycle events were partly design-forward
- approval and incident report events were not emitted in the same normalized style as the newer audit schema

Phase 9B closes that gap by emitting structured audit events without changing the underlying state model.

## Events Added

| Event type | Purpose |
| --- | --- |
| `approval_created` | Approval record created from an approval-required agent proposal |
| `approval_decided` | Approval decision persisted without executing the action |
| `approval_execute_requested` | Execution endpoint invoked after request parsing and identity resolution |
| `approval_execute_denied` | Execution request denied before internal action execution |
| `approval_executed` | Approved internal action executed successfully |
| `incident_report_created` | Internal incident report record created from an approved action |

## Where Each Event Is Emitted

| Event type | Emitted from | Notes |
| --- | --- | --- |
| `approval_created` | `backend/lambda/agent_run/handler.py` | Emitted after the approval record is created for `propose_incident_report`. |
| `approval_decided` | `backend/lambda/approvals/handler.py` | Emitted after the decision is successfully persisted. |
| `approval_execute_requested` | `backend/lambda/approvals/handler.py` | Emitted after request parsing and identity resolution, before execution-state checks. |
| `approval_execute_denied` | `backend/lambda/approvals/handler.py` | Emitted for approval-not-found, permission denial, invalid request body, non-approved state, non-executable state, and unsupported action type. |
| `approval_executed` | `backend/lambda/approvals/handler.py` | Emitted after successful internal execution and approval-state update. |
| `incident_report_created` | `backend/lambda/approvals/handler.py` | Emitted when the internal incident report record is written during approved execution. |

## Fields Included

New audit events prefer the normalized field names described in [docs/AUDIT_EVENT_SCHEMA.md](docs/AUDIT_EVENT_SCHEMA.md), including:

- `eventType`
- `requestId`
- `approvalId`
- `reportId`
- `userId`
- `routeCategory`
- `actionType`
- `executionStatus`
- `policyReason`

Current runtime compatibility is preserved because the shared logger still emits `request_id` at the top level when a request ID is available. This means Phase 9A compatibility queries can read both styles during migration.

Only fields already available at the emit point are included. No secrets, passwords, raw JWTs, or token contents are logged.

## What Is Intentionally Not Changed

This phase does not change:

- approval decision permission requirements
- approval execute permission requirements
- approval workflow state transitions
- the allowlisted executable action type `create_incident_report`
- the fact that successful execution only creates an internal DynamoDB incident report record
- the fact that no external email, Jira, shell, or external API execution exists
- the fact that DynamoDB remains the source of workflow state

## Manual Verification Commands

Approval lifecycle audit events can be reviewed through the approvals Lambda log group.

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset approval \
  --start-minutes-ago 120 \
  --region ap-southeast-1
```

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset executions \
  --start-minutes-ago 120 \
  --region ap-southeast-1
```

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset security-audit \
  --start-minutes-ago 120 \
  --region ap-southeast-1
```

If you want a broader review window, also query the agent log group for `approval_created` events because approval creation is emitted from the `POST /agent/run` proposal path:

```bash
python3 scripts/query_logs.py \
  --log-group "$AGENT_RUN_LOG_GROUP" \
  --preset security-audit \
  --start-minutes-ago 120 \
  --region ap-southeast-1
```

The `incident_report_created` event is emitted from the approvals execution path in this phase, so it should appear in the approvals Lambda log group rather than requiring a separate incident-reports log query.

## Acceptance Criteria

Phase 9B is acceptable when:

- approval creation emits a structured `approval_created` audit event
- approval decision emits a structured `approval_decided` audit event after persistence
- execution requests emit `approval_execute_requested`
- denied execution paths emit `approval_execute_denied` with sanitized reasons
- successful execution emits both `approval_executed` and `incident_report_created`
- DynamoDB approval and incident report records remain unchanged as workflow state sources
- route permissions and executor scope remain unchanged
- no secrets, raw JWTs, or passwords are logged

## Current Limitations

- the dashboard is still not deployed in this phase
- CloudWatch audit visibility is improved, but DynamoDB remains the authoritative workflow state store
- `approval_created` is emitted from the agent proposal flow, so approval audit review may involve both the agent and approvals log groups
- this phase does not add CloudTrail, WAF, X-Ray, OpenTelemetry, or cost dashboards
- this phase does not add external execution behavior
