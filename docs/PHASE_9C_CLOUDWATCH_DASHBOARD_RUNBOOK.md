# Phase 9C CloudWatch Dashboard Runbook

## Purpose of Phase 9C

Phase 9C operationalizes the Phase 9A design and the Phase 9B audit-event normalization work.

This phase provides:

- a practical operator runbook for the current CloudWatch Logs and audit-query workflow
- a basic CloudWatch dashboard definition that is intentionally small and low-risk
- clear guidance on what can be observed today versus what remains future hardening work

This phase does not add new application behavior, authorization changes, external execution, or production hardening controls such as WAF, CloudTrail dashboards, X-Ray, OpenTelemetry, or cost dashboards.

## Current Observability Sources

Current operator-facing observability sources are:

- CloudWatch Logs from the deployed Lambda functions
- DynamoDB trace records for traced routes such as `/echo`, `/chat`, `/rag/query`, and `/agent/run`
- DynamoDB approval records for approval lifecycle state
- DynamoDB incident report records for internal execution output
- local helper scripts:
  - `scripts/get_lambda_log_groups.py`
  - `scripts/query_logs.py`
  - `scripts/view_trace.py`
  - `scripts/view_eval_trace.py`
- local evaluation artifacts from `scripts/run_rag_eval.py`

CloudWatch Logs are the primary source for the Phase 9C dashboard and query workflow.

DynamoDB traces, approval records, and incident report records remain companion evidence.

## Required Environment Variables

Common variables for the runbook:

- `STACK_NAME`
- `AWS_REGION`
- `API_BASE_URL`
- `AUTH_TOKEN`
- `RAG_QUERY_LOG_GROUP`
- `AGENT_RUN_LOG_GROUP`
- `APPROVALS_LOG_GROUP`
- `INCIDENT_REPORTS_LOG_GROUP`

Example:

```bash
export STACK_NAME="aws-ai-platform-poc-dev"
export AWS_REGION="ap-southeast-1"
export API_BASE_URL="https://<api-id>.execute-api.${AWS_REGION}.amazonaws.com/v1"
export AUTH_TOKEN="<id-token>"
```

Do not paste full JWTs, passwords, or secrets into committed files or screenshots.

## How to Discover Lambda Log Groups

Use the existing helper:

```bash
python3 scripts/get_lambda_log_groups.py --stack-name "$STACK_NAME" --region "$AWS_REGION"
```

Expected output includes the logical ID, physical Lambda function name, and the corresponding CloudWatch log group name.

Typical groups to export for later commands:

```bash
export RAG_QUERY_LOG_GROUP="/aws/lambda/<rag-query-function-name>"
export AGENT_RUN_LOG_GROUP="/aws/lambda/<agent-run-function-name>"
export APPROVALS_LOG_GROUP="/aws/lambda/<approvals-function-name>"
export INCIDENT_REPORTS_LOG_GROUP="/aws/lambda/<incident-reports-function-name>"
```

## How to Run Each Important Query Preset

### Summary

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset summary \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Policy Denied

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset policy-denied \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Guardrail Blocked

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset blocked \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### No-source

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset no-source \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Errors

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset errors \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Latency

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset latency \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Guardrails

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset guardrails \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Agent Tools

```bash
python3 scripts/query_logs.py \
  --log-group "$AGENT_RUN_LOG_GROUP" \
  --preset agent-tools \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Approval Lifecycle

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset approval \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Executions

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset executions \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

### Security Audit

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset security-audit \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

## How to Verify RAG Policy Denial Visibility

1. Use a valid token.
2. Send a `/rag/query` request with a `projectId` or `customerId` outside the allowed claims scope.
3. Confirm the API returns HTTP `403`.
4. Query the RAG log group with `policy-denied`.

Example query command:

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset policy-denied \
  --start-minutes-ago 60 \
  --region "$AWS_REGION"
```

What to look for:

- `status=denied` or `eventType=policy_denied`
- matching `request_id` or `requestId`
- the expected route path

## How to Verify Guardrail Block Visibility

1. Send a `/rag/query` request with an input that should match the input guardrail.
2. Confirm the response returns the blocked status behavior.
3. Query the RAG log group with `blocked` or `guardrails`.

Commands:

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset blocked \
  --start-minutes-ago 60 \
  --region "$AWS_REGION"
```

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset guardrails \
  --start-minutes-ago 60 \
  --region "$AWS_REGION"
```

What to look for:

- `guardrail_action=block` or `guardrailAction=block`
- `guardrail_reason` or `guardrailReason`
- the matched rule field when present

## How to Verify No-source Visibility

1. Send a `/rag/query` request that stays in scope but produces no eligible grounded evidence.
2. Confirm the response returns `status=no_source`.
3. Query the RAG log group with `no-source`.

```bash
python3 scripts/query_logs.py \
  --log-group "$RAG_QUERY_LOG_GROUP" \
  --preset no-source \
  --start-minutes-ago 60 \
  --region "$AWS_REGION"
```

What to look for:

- `status=no_source` or `eventType=rag_no_source`
- `source_count` or `sourceCount` near zero
- `eligible_chunk_count` or `eligibleChunkCount` for context

## How to Verify Approval Lifecycle Visibility

Approval creation is emitted from the agent proposal path, while decision and execution lifecycle events are emitted from the approvals handler.

Check approval creation in the agent log group:

Expected event: `eventType=approval_created`

```bash
python3 scripts/query_logs.py \
  --log-group "$AGENT_RUN_LOG_GROUP" \
  --preset security-audit \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

Check approval decisions in the approvals log group:

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset approval \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

What to look for:

- `eventType=approval_created` in the agent log group
- `eventType=approval_decided` in the approvals log group
- `approvalId` correlation across both stages

## How to Verify Execution Visibility

Query the approvals log group for execution lifecycle events:

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset executions \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

What to look for:

- `eventType=approval_execute_requested`
- `eventType=approval_execute_denied` for denied paths
- `eventType=approval_executed` for successful execution
- `reportId` or `report_id` when a report is created

## How to Investigate an Incident Report Creation Audit Trail

1. Start with the approvals log group and query `executions` or `security-audit`.
2. Identify the relevant `approvalId`, `reportId`, and `requestId`.
3. Confirm the approval state in DynamoDB or through the approval API if needed.
4. Confirm the incident report record through the incident report API or DynamoDB.

Suggested sequence:

```bash
python3 scripts/query_logs.py \
  --log-group "$APPROVALS_LOG_GROUP" \
  --preset executions \
  --start-minutes-ago 120 \
  --region "$AWS_REGION"
```

Then inspect the workflow record through the API:

```bash
curl -i -sS \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  "$API_BASE_URL/approvals/<approvalId>"
```

And inspect the created incident report:

```bash
curl -i -sS \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  "$API_BASE_URL/incident-reports/<reportId>"
```

## Dashboard Sections

### Platform Runtime Health

| Widget name | Source log group | Query preset or Logs Insights query | What the operator should look for |
| --- | --- | --- | --- |
| RAG Policy Denied Events | `$RAG_QUERY_LOG_GROUP` | direct Logs Insights query matching the dashboard widget | unexpected spikes in denied retrieval attempts |
| RAG Guardrail Blocks | `$RAG_QUERY_LOG_GROUP` | direct Logs Insights query matching the dashboard widget | repeated unsafe request patterns |

### RAG Quality and Grounding

| Widget name | Source log group | Query preset or Logs Insights query | What the operator should look for |
| --- | --- | --- | --- |
| RAG No-Source Events | `$RAG_QUERY_LOG_GROUP` | direct Logs Insights query matching the dashboard widget | increases in no-source outcomes that may indicate weak coverage or narrow filtering |

### Security and Guardrail Events

| Widget name | Source log group | Query preset or Logs Insights query | What the operator should look for |
| --- | --- | --- | --- |
| Approval Security Audit Events | `$APPROVALS_LOG_GROUP` | `security-audit` equivalent query | denied executions, approval lifecycle anomalies, and execution-related audit trails |

### Agent Tool Execution

| Widget name | Source log group | Query preset or Logs Insights query | What the operator should look for |
| --- | --- | --- | --- |
| Agent Tool Execution | `$AGENT_RUN_LOG_GROUP` | `agent-tools` equivalent query | tool usage shape, failures, and unexpected task behavior |

### Approval and Internal Execution Audit

| Widget name | Source log group | Query preset or Logs Insights query | What the operator should look for |
| --- | --- | --- | --- |
| Approval Decisions | `$APPROVALS_LOG_GROUP` | `approval` equivalent query | approved versus rejected workflow decisions |
| Approval Executions | `$APPROVALS_LOG_GROUP` | `executions` equivalent query | requested, denied, and successful execution outcomes |

## Known Limitations

- CloudWatch Logs remain the primary dashboard source, not DynamoDB tables
- DynamoDB traces, approval records, and incident report records remain companion evidence
- API Gateway and Cognito authorizer no-token rejections may not appear in Lambda log groups because Lambda may not be invoked
- the dashboard focuses on key log groups and does not replace targeted manual investigation
- this PoC is not production-ready

## Future Alarm Candidates

These are documented candidates only. They are not implemented in this phase.

- repeated `policy_denied` spikes on `/rag/query`
- sudden increases in guardrail block rates
- sustained `no_source` increases after a document or embedding change
- unexpected growth in `approval_execute_denied`
- repeated execution failures or unexpected report-creation failures

## Future Production Hardening Candidates

These are future hardening ideas only. They are not implemented in this phase.

- CloudWatch alarms after baseline noise is better understood
- stronger metric filters for audit event types
- CloudTrail-based operational visibility where it materially helps operators
- WAF metrics if an internet-facing protection layer is later added
- X-Ray or OpenTelemetry only if cross-service tracing becomes necessary
- stronger retention and export strategy for logs and workflow evidence
- token and cost observability for Bedrock-backed flows if later justified

## Deployment Note

This phase can include a CloudWatch dashboard resource in the SAM template if the template is updated and deployed. Until that deployment happens, operators should treat the runbook queries as the active operational path.
