# Evidence Pack After Phase 6G

## Purpose

This file is used to collect evidence after running the current demo flow.

It is designed as a practical capture sheet for terminal output, screenshots, IDs, trace lookups, log lookups, and short observations that prove the PoC behavior end to end.

## Evidence Checklist

### Deployment evidence

- [ ] `API_BASE_URL` is set for the deployed `/v1` stage.
- [ ] The stack name used for helper scripts is recorded.
- [ ] Lambda log groups were listed from the deployed stack.
- [ ] The demo commit hash was recorded with `git rev-parse --short HEAD`.

### Endpoint evidence

- [ ] `GET /health` returned `status=ok`.
- [ ] `POST /chat` returned `status=completed` and a `requestId`.
- [ ] `POST /documents` returned `status=indexed`.

### RAG evidence

- [ ] At least one `POST /rag/query` response returned `status=completed`.
- [ ] The successful RAG response included at least one source.
- [ ] A successful RAG `requestId` was captured for trace inspection.

### Guardrail evidence

- [ ] At least one blocked request returned `status=blocked`.
- [ ] The blocked response included guardrail metadata.
- [ ] A blocked `requestId` was captured.

### Policy boundary evidence

- [ ] At least one policy-denied request returned HTTP `403`.
- [ ] The denial response included `Access denied for requested retrieval scope.`

### Agent tool evidence

- [ ] `answer_question` showed `rag_query` in `toolCalls`.
- [ ] `inspect_trace` showed `trace_lookup` in `toolCalls`.
- [ ] `search_logs` showed `log_search` in `toolCalls`.
- [ ] `investigate_recent_blocks` showed both `log_search` and `trace_lookup`.

### Approval workflow evidence

- [ ] `propose_incident_report` returned `status=approval_required`.
- [ ] A real `APPROVAL_ID` was captured.
- [ ] Approval decision changed the record to `approved` and `approved_not_executed`.

### Internal executor evidence

- [ ] Approved execution returned `status=executed`.
- [ ] A real `REPORT_ID` was captured.
- [ ] Incident report lookup returned the created report.

### Trace evidence

- [ ] `scripts/view_trace.py` successfully displayed a trace summary.
- [ ] At least one trace view was captured for a successful RAG request.
- [ ] At least one trace view was captured for a blocked or no-source request.

### CloudWatch log evidence

- [ ] `scripts/get_lambda_log_groups.py` listed stack log groups.
- [ ] `scripts/query_logs.py --preset blocked` returned blocked evidence or a justified empty result after runtime review.
- [ ] `scripts/query_logs.py --preset no-source` returned no-source evidence or a justified empty result after runtime review.

### Evaluation evidence

- [ ] `scripts/run_rag_eval.py` completed successfully.
- [ ] `reports/rag-eval-results.json` was produced or refreshed.
- [ ] `reports/rag-eval-report.md` was produced or refreshed.

## Evidence Capture Template

Use the following template for each evidence item you capture.

### Evidence Item Template

- Date/time:
- Command:
- Output summary:
- Request ID:
- Approval ID if applicable:
- Report ID if applicable:
- Trace lookup command:
- Log query command:
- Notes:

### Example Use

- Date/time: `2026-05-26T14:30:00Z`
- Command: `curl -sS -X POST "$API_BASE_URL/rag/query" ...`
- Output summary: `completed response with one grounded source for api-gateway-note`
- Request ID: `REQUEST_ID`
- Approval ID if applicable: `-`
- Report ID if applicable: `-`
- Trace lookup command: `python3 scripts/view_trace.py --request-id "REQUEST_ID" --table-name "$TRACE_TABLE_NAME"`
- Log query command: `python3 scripts/query_logs.py --log-group "$RAG_LOG_GROUP" --preset raw --start-minutes-ago 120`
- Notes: `Use the same requestId for screenshot correlation.`

## Recommended Demo Recording Order

1. Record deployment context first: environment variables, stack name, and discovered log groups.
2. Record the main runtime path next: health, chat, document ingestion, successful RAG, blocked RAG, no-source RAG, and policy denial.
3. Record agent behavior after the core runtime path: `answer_question`, `inspect_trace`, `search_logs`, and `investigate_recent_blocks`.
4. Record the approval boundary and internal executor last: proposal, decision, execute, report lookup, trace viewer, log helper, and evaluation script output.

## Known Runtime Placeholders

- `API_BASE_URL`: deployed API stage base URL.
- `REQUEST_ID`: response `requestId` captured from `/chat`, `/rag/query`, or `/agent/run`.
- `APPROVAL_ID`: response `approvalId` captured from `propose_incident_report`.
- `REPORT_ID`: response `reportId` captured from `/approvals/{approvalId}/execute`.
- `RAG_LOG_GROUP`: actual CloudWatch log group derived from `scripts/get_lambda_log_groups.py` output.
- `STACK_NAME`: deployed CloudFormation stack name.
- `TRACE_TABLE_NAME`: deployed request trace DynamoDB table name.

## Acceptance Criteria

The demo evidence is complete when:

- at least one successful RAG answer has sources
- at least one blocked guardrail request exists
- at least one `no_source` response exists
- at least one agent investigation trace exists
- at least one pending approval is created
- one approval is approved
- one approved action is executed
- one incident report can be retrieved
- evaluation script passes
- trace viewer can inspect at least one request
- CloudWatch log helper can find blocked or `no_source` events