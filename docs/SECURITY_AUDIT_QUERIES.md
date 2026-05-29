# Security Audit Queries

## Purpose

This document provides CloudWatch Logs Insights query examples for the current AWS AI Platform PoC.

The queries are intentionally defensive because the current logs are only partly normalized. Some routes emit structured JSON logs with fields such as `request_id`, `path`, `status`, `guardrail_action`, and `latency_ms`. Other routes, especially approval and incident report flows, are not yet normalized to the same degree.

Some current logs may only have snake_case fields. Future normalized audit logs may use camelCase fields. The queries below intentionally support both naming styles during migration.

Where exact fields may not exist consistently, each section includes:

- a preferred query for structured logs
- a fallback query using `@message like /.../`
- notes about current limitations when the best evidence today is DynamoDB rather than CloudWatch Logs

## Assumptions

Assumptions grounded in the current repository:

- `common.logging.log_json()` emits JSON log lines
- RAG and agent paths already use structured logging more consistently than approval or incident report paths
- `request_id` is the main log correlation key when present
- `path`, `status`, `guardrail_action`, `guardrail_reason`, `latency_ms`, and `tool_calls` may be present in structured log events depending on the handler
- future normalized audit events may use camelCase fields such as `requestId`, `userId`, `latencyMs`, `sourceCount`, `eligibleChunkCount`, `guardrailAction`, `approvalId`, and `reportId`

## Requests by Route

Preferred query:

```sql
fields @timestamp, path, status, eventType
| filter ispresent(path)
| stats count(*) as request_count by path
| sort request_count desc
```

Fallback query:

```sql
fields @timestamp, @log, @message
| stats count(*) as request_count by @log
| sort request_count desc
```

## Requests by User

Preferred query:

```sql
fields @timestamp, user_id, userId, path, status, eventType
| filter ispresent(user_id) or ispresent(userId)
| stats count(*) as request_count by user_id, userId, path
| sort request_count desc
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /user_id|userId/
| sort @timestamp desc
| limit 50
```

## Errors by Route

Preferred query:

```sql
fields @timestamp, path, status, eventType, error, errorType, message
| filter status = "failed" or eventType = "error" or ispresent(error) or ispresent(errorType)
| stats count(*) as error_count by path, status
| sort error_count desc
```

Fallback query:

```sql
fields @timestamp, @log, @message
| filter @message like /ERROR|error|failed|Exception/
| stats count(*) as error_count by @log
| sort error_count desc
```

## Latency by Route

Preferred query:

```sql
fields @timestamp, path, status, latency_ms, latencyMs
| filter ispresent(latency_ms) or ispresent(latencyMs)
| stats avg(latency_ms) as avg_latency_ms, avg(latencyMs) as avg_latencyMs, max(latency_ms) as max_latency_ms, max(latencyMs) as max_latencyMs, count(*) as sample_count by path, status
| sort sample_count desc
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /latency_ms|latencyMs/
| sort @timestamp desc
| limit 50
```

## Policy Denied Events

Preferred query:

```sql
fields @timestamp, request_id, requestId, path, user_id, userId, filters, status, eventType, @message
| filter status = "denied"
	or eventType = "policy_denied"
	or @message like /denied|policy/
| sort @timestamp desc
| limit 50
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /denied|policy/
| sort @timestamp desc
| limit 50
```

Notes:
The strongest current CloudWatch evidence for policy denial comes from the RAG path.

## Input Guardrail Blocked Events

Preferred query:

```sql
fields @timestamp, request_id, requestId, path, guardrail_action, guardrailAction, guardrail_reason, guardrailReason, guardrail_matched_rule, guardrailMatchedRule, user_id, userId, status, eventType
| filter guardrail_action = "block"
	or guardrailAction = "block"
	or status = "blocked"
	or eventType = "input_guardrail_blocked"
| sort @timestamp desc
| limit 50
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /blocked|guardrail|prompt_injection|unsafe_data_access/
| sort @timestamp desc
| limit 50
```

## RAG No-source Events

Preferred query:

```sql
fields @timestamp, request_id, requestId, path, question, source_count, sourceCount, eligible_chunk_count, eligibleChunkCount, status, eventType
| filter status = "no_source" or eventType = "rag_no_source"
| sort @timestamp desc
| limit 50
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /no_source/
| sort @timestamp desc
| limit 50
```

## Agent Tool Calls

Preferred query:

```sql
fields @timestamp, request_id, requestId, task, tool_calls, toolCalls, status, eventType
| filter ispresent(tool_calls) or ispresent(toolCalls) or eventType = "agent_tool_called"
| sort @timestamp desc
| limit 50
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /tool_calls|trace_lookup|log_search|rag_query/
| sort @timestamp desc
| limit 50
```

Notes:
Structured agent traces are often a better source than raw logs for tool-call detail.

## Agent Tool Failures

Preferred query:

```sql
fields @timestamp, request_id, requestId, task, tool_calls, toolCalls, status, eventType, message, @message
| filter (ispresent(tool_calls) or ispresent(toolCalls) or eventType = "agent_tool_failed")
	and (status = "failed" or eventType = "agent_tool_failed" or @message like /failed/)
| sort @timestamp desc
| limit 50
```

Fallback query:

```sql
fields @timestamp, @message
| filter @message like /tool|failed|trace_lookup|log_search|rag_query/
| sort @timestamp desc
| limit 50
```

## Approval Decisions

Preferred compatibility query:

```sql
fields @timestamp, approval_id, approvalId, decision, execution_status, executionStatus, user_id, userId, status, eventType, @message
| filter eventType = "approval_decided"
	or ispresent(approval_id)
	or ispresent(approvalId)
	or @message like /approval|decision|approved|rejected/
| sort @timestamp desc
| limit 50
```

Current fallback query:

```sql
fields @timestamp, @message
| filter @message like /approval|decision|approved|rejected/
| sort @timestamp desc
| limit 50
```

Current limitation:
The approvals handler does not currently use the shared structured logging helper, so DynamoDB approval records are the primary source of truth today.

## Approval Execution Attempts

Preferred compatibility query:

```sql
fields @timestamp, approval_id, approvalId, report_id, reportId, execution_status, executionStatus, action_type, actionType, user_id, userId, status, eventType, @message
| filter eventType = "approval_execute_requested"
	or eventType = "approval_execute_denied"
	or eventType = "approval_executed"
	or ispresent(report_id)
	or ispresent(reportId)
	or @message like /execute|executed|reportId|report_id|incident report/
| sort @timestamp desc
| limit 50
```

Current fallback query:

```sql
fields @timestamp, @message
| filter @message like /execute|approvalId|reportId|incident report/
| sort @timestamp desc
| limit 50
```

Current limitation:
Execution attempts and results are more reliably visible in approval and incident report DynamoDB records than in normalized CloudWatch logs today.

## Incident Report Creation Events

Preferred compatibility query:

```sql
fields @timestamp, report_id, reportId, approval_id, approvalId, status, user_id, userId, eventType, @message
| filter eventType = "incident_report_created"
	or ispresent(report_id)
	or ispresent(reportId)
	or @message like /reportId|report_id|incident report|create_incident_report/
| sort @timestamp desc
| limit 50
```

Current fallback query:

```sql
fields @timestamp, @message
| filter @message like /reportId|incident report|create_incident_report/
| sort @timestamp desc
| limit 50
```

Current limitation:
The incident report repository writes to DynamoDB but does not emit a dedicated structured CloudWatch audit event today.

## Query Usage Notes

Use these queries against the most relevant log groups rather than assuming one global application log group.

Typical starting points are:

- the RAG query Lambda log group for policy, guardrail, `no_source`, and latency visibility
- the agent run Lambda log group for tool usage and investigations
- the approvals Lambda log group for future approval audit normalization
- the documents, chat, echo, and incident reports Lambda log groups for route-specific troubleshooting

When the fallback queries return little or no data, that usually indicates a logging normalization gap, not necessarily that the workflow did not happen.
