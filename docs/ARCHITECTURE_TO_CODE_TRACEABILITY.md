# Architecture to Code Traceability

## Purpose

This document maps the Phase 7A architecture blueprint to the current implementation files in this repository.

## Phase 7B Verification Result

- Verified against the current repository for the Phase 7B documentation-only pass.
- `POST /chat` is a basic Bedrock inference and smoke-test endpoint. It is not the controlled enterprise RAG path.
- `/chat` has no input guardrail, output guardrail, metadata filtering, or approval flow.
- `scripts/run_rag_eval.py` does exercise approval and execution flows through `GET /approvals/{approvalId}`, `POST /approvals/{approvalId}/decision`, `POST /approvals/{approvalId}/execute`, and `GET /incident-reports/{reportId}`.

It is intentionally evidence-based:

- only deployed resources defined in `infra/cloudformation/template.yaml` are treated as runtime components
- only modules, handlers, repositories, scripts, environment variables, and routes that exist in the repository are listed
- architecture labels that do not exist as standalone modules are called out explicitly in notes or in the verification section

## Current Implementation Scope

The current repository implements the following backend capabilities:

- backend foundation through AWS SAM, API Gateway, Lambda, DynamoDB, and CloudWatch Logs
- Bedrock chat through `POST /chat` as a basic Bedrock inference / smoke-test endpoint
- document ingestion through `POST /documents`
- RAG query through `POST /rag/query`
- metadata boundary through chunk metadata and pre-retrieval filtering in `common.rag_service`
- policy gate through header-derived access context and filter authorization checks in `common.policy`
- input/output guardrails through `common.guardrails` and `common.output_guardrails`
- evaluation through `scripts/run_rag_eval.py` and `reports/rag-eval-*`
- trace viewer utilities through `scripts/view_trace.py` and `scripts/view_eval_trace.py`
- CloudWatch log query helpers through `scripts/get_lambda_log_groups.py` and `scripts/query_logs.py`
- read-only agent tools through `rag_query`, `trace_lookup`, and `log_search`
- multi-tool investigation through the `investigate_recent_blocks` task in `POST /agent/run`
- approval workflow through `/approvals/{approvalId}` and `/approvals/{approvalId}/decision`
- approved internal executor through `/approvals/{approvalId}/execute`, limited to creating an internal incident report record

## Component-to-Code Map

| Architecture Component | Responsibility | Source Files | Runtime Dependency | Notes |
| --- | --- | --- | --- | --- |
| API Gateway / SAM template | Defines the deployed API, Lambda functions, DynamoDB tables, outputs, and function environment variables | `infra/cloudformation/template.yaml` | AWS SAM, API Gateway, Lambda, DynamoDB, Bedrock Runtime, CloudWatch Logs | `ApiGateway` exposes stage `v1`; all current backend routes come from this template. |
| Lambda handlers | Validate API requests and dispatch to the shared modules for each route | `backend/lambda/health/handler.py`, `backend/lambda/echo/handler.py`, `backend/lambda/chat/handler.py`, `backend/lambda/documents/handler.py`, `backend/lambda/rag_query/handler.py`, `backend/lambda/agent_run/handler.py`, `backend/lambda/approvals/handler.py`, `backend/lambda/incident_reports/handler.py` | API Gateway proxy event shape, `common.response` | Each deployed route maps to `lambda_handler` in one of these files. |
| Bedrock chat client | Wraps Bedrock Converse calls for chat and grounded answer generation | `backend/lambda/common/bedrock_client.py`, `backend/lambda/chat/handler.py`, `backend/lambda/common/rag_service.py` | Amazon Bedrock Runtime `converse` | Used directly by `/chat` and indirectly by `/rag/query` and `/agent/run` when task is `answer_question`. |
| Embedding client | Wraps Bedrock embedding model invocation for document and query embeddings | `backend/lambda/common/embedding_client.py`, `backend/lambda/documents/handler.py`, `backend/lambda/common/rag_service.py` | Amazon Bedrock Runtime `invoke_model` | Used on ingestion and retrieval paths. |
| Retrieval module | Scores eligible chunks and returns the top matches | `backend/lambda/common/retrieval.py`, `backend/lambda/common/rag_service.py` | In-memory Python ranking over DynamoDB-loaded chunks | `retrieve_top_chunks()` applies `min_similarity_score` and returns at most three chunks. |
| Vector math module | Computes cosine similarity between query and chunk embeddings | `backend/lambda/common/vector_math.py` | Python `math.sqrt` | Pure utility module; no AWS dependency. |
| Metadata filter | Filters chunk candidates by `projectId`, `customerId`, and `documentType` before similarity ranking | `backend/lambda/common/rag_service.py` | Loaded chunk records from `DocumentChunksTable` | Implemented as `_filter_chunks_by_metadata()` inside `common.rag_service`, not as a separate module. |
| Policy gate | Resolves user access context from headers and blocks disallowed filter scopes | `backend/lambda/common/policy.py`, `backend/lambda/common/rag_service.py`, `backend/lambda/agent_run/handler.py` | Request headers `X-User-Id`, `X-Allowed-Project-Ids`, `X-Allowed-Customer-Ids` | Header-based authorization only; no IAM authorizer or identity provider integration exists in code. |
| Input guardrail | Blocks prompt injection and unsafe data access patterns before retrieval/model use | `backend/lambda/common/guardrails.py`, `backend/lambda/common/rag_service.py` | In-Lambda string matching | Returns `blocked` behavior with no model call when triggered. |
| Output guardrail | Warns when grounded answers are empty or do not reference sources | `backend/lambda/common/output_guardrails.py`, `backend/lambda/common/rag_service.py` | In-Lambda validation of answer text and source list | Warning-oriented only; it does not suppress or rewrite answers. |
| Request trace writer | Persists request or agent traces to the trace table | `backend/lambda/common/trace_repository.py`, `backend/lambda/echo/handler.py`, `backend/lambda/chat/handler.py`, `backend/lambda/common/rag_service.py`, `backend/lambda/agent_run/handler.py` | DynamoDB table `AiPlatformRequestTrace` | There is no separate trace service module; handlers and shared services call `TraceRepository.save_trace()` directly. |
| Document chunk storage | Stores, deletes, scans, and deserializes indexed document chunks | `backend/lambda/common/document_repository.py`, `backend/lambda/documents/handler.py`, `backend/lambda/common/rag_service.py` | DynamoDB table `DocumentChunksTable` | Retrieval currently uses table scan plus in-Lambda filtering/ranking. |
| Agent orchestrator | Defines fixed task plans and executes bounded task branches | `backend/lambda/common/agent.py`, `backend/lambda/agent_run/handler.py` | API Gateway, DynamoDB trace, DynamoDB approvals, CloudWatch Logs, optional Bedrock via `common.rag_service` | The agent is deterministic. There is no free-form planner module or managed agent runtime. |
| Tool allowlist | Restricts agent tool usage to known read-only tool names | `backend/lambda/common/agent.py`, `backend/lambda/agent_run/handler.py` | In-Lambda branch checks | `ALLOWED_TOOLS = ["rag_query", "trace_lookup", "log_search"]`. |
| `rag_query` tool | Lets the agent answer grounded questions through the shared RAG pipeline | `backend/lambda/agent_run/handler.py`, `backend/lambda/common/rag_service.py` | DynamoDB `DocumentChunksTable`, Bedrock Runtime, DynamoDB `AiPlatformRequestTrace` | No separate `rag_query` tool module exists; the agent branch calls `run_rag_query(..., save_trace=False)` directly. |
| `trace_lookup` tool | Looks up one trace record by request ID | `backend/lambda/common/trace_lookup.py`, `backend/lambda/agent_run/handler.py` | DynamoDB table `AiPlatformRequestTrace` | Used by `inspect_trace` and `investigate_recent_blocks`. |
| `log_search` tool | Searches recent Lambda log events using a preset | `backend/lambda/common/log_search.py`, `backend/lambda/agent_run/handler.py` | CloudWatch Logs `FilterLogEvents`, env var `RAG_QUERY_LOG_GROUP_NAME` | Supported presets are `raw`, `blocked`, `no_source`, and `errors`. |
| Approval repository/service | Stores approval records and updates approval lifecycle fields | `backend/lambda/common/approval_repository.py`, `backend/lambda/agent_run/handler.py`, `backend/lambda/approvals/handler.py` | DynamoDB table `ActionApprovalsTable` | Repository exists; approval workflow logic stays in handlers, not in a separate service module. |
| Internal incident report executor | Writes an internal incident report after explicit approval and execution checks | `backend/lambda/approvals/handler.py`, `backend/lambda/common/incident_report_repository.py` | DynamoDB tables `ActionApprovalsTable` and `IncidentReportsTable` | Only action type `create_incident_report` is executable. No external system write exists. |
| Evaluation scripts | Exercise document, RAG, agent, approval, and execution flows and write reports | `scripts/run_rag_eval.py`, `reports/rag-eval-results.json`, `reports/rag-eval-report.md`, `test-data/rag-evaluation/questions.json`, `test-data/rag-evaluation/documents/api-gateway-note.json` | Deployed API endpoints, local filesystem | The script drives approval and execution flows as part of evaluation cases. |
| Trace viewer scripts | Fetch and format individual trace records for manual inspection | `scripts/view_trace.py`, `scripts/view_eval_trace.py` | AWS CLI `dynamodb get-item`, local reports file | `view_eval_trace.py` resolves a `caseId` to a `requestId` via `reports/rag-eval-results.json`. |
| CloudWatch log query scripts | Discover Lambda log groups and run Logs Insights presets from the command line | `scripts/get_lambda_log_groups.py`, `scripts/query_logs.py` | AWS CLI `cloudformation describe-stack-resources`, `logs start-query`, `logs get-query-results` | These scripts are operational helpers; the Lambda runtime uses `FilterLogEvents`, not Logs Insights. |

## Endpoint-to-Code Map

| Endpoint | HTTP Method | Lambda/Handler | Main Modules Called | DynamoDB Tables Used | Bedrock Used? | Trace/Log Behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `/health` | GET | `health.handler.lambda_handler` | `common.response.json_response` | None | No | No custom trace record; only default Lambda logs if the platform emits them. |
| `/echo` | POST | `echo.handler.lambda_handler` | `common.trace_repository.TraceRepository`, `common.logging.log_json`, `common.response.json_response` | `AiPlatformRequestTrace` | No | Writes one trace record with `request_id`, `message`, `path`, `timestamp`, `status`; emits structured JSON logs. |
| `/chat` | POST | `chat.handler.lambda_handler` | `common.bedrock_client.BedrockClient`, `common.trace_repository.TraceRepository`, `common.logging.log_json`, `common.response.json_response` | `AiPlatformRequestTrace` | Yes, Bedrock Converse | Basic Bedrock inference / smoke-test path only; writes a success trace on completion and structured logs for success/failure. |
| `/documents` | POST | `documents.handler.lambda_handler` | `common.chunking.chunk_document`, `common.document_repository.DocumentRepository`, `common.embedding_client.EmbeddingClient`, `common.logging.log_json`, `common.response.json_response` | `DocumentChunksTable` | Yes, Bedrock embeddings | No trace-table write; logs indexing success and failures to CloudWatch Logs. |
| `/rag/query` | POST | `rag_query.handler.lambda_handler` | `common.rag_service.run_rag_query`, `common.rag_service.normalize_filters`, `common.logging.log_json`, `common.response.json_response` | `DocumentChunksTable`, `AiPlatformRequestTrace` | Yes, Bedrock embeddings and Bedrock Converse when a grounded answer is generated | Saves trace records for `blocked`, `no_source`, and `completed`; logs `denied`, `failed`, and other statuses to CloudWatch Logs. |
| `/agent/run` | POST | `agent_run.handler.lambda_handler` | `common.agent`, `common.rag_service`, `common.trace_lookup`, `common.log_search`, `common.investigation`, `common.action_proposal`, `common.approval_repository`, `common.trace_repository`, `common.logging` | Always `AiPlatformRequestTrace`; `DocumentChunksTable` when task is `answer_question`; `ActionApprovalsTable` when task is `propose_incident_report` | Only when task is `answer_question`, via the shared RAG pipeline | Writes one agent trace per request; can also read CloudWatch Logs or create an approval record depending on task. |
| `/approvals/{approvalId}` | GET | `approvals.handler.lambda_handler` | `common.approval_repository.ApprovalRepository`, `common.response.json_response` | `ActionApprovalsTable` | No | No custom trace write or structured logging path in code. |
| `/approvals/{approvalId}/decision` | POST | `approvals.handler.lambda_handler` | `common.approval_repository.ApprovalRepository`, `common.response.json_response` | `ActionApprovalsTable` | No | No custom trace write or structured logging path in code. |
| `/approvals/{approvalId}/execute` | POST | `approvals.handler.lambda_handler` | `common.approval_repository.ApprovalRepository`, `common.incident_report_repository.IncidentReportRepository`, `common.response.json_response` | `ActionApprovalsTable`, `IncidentReportsTable` | No | No custom trace write or structured logging path in code. |
| `/incident-reports/{reportId}` | GET | `incident_reports.handler.lambda_handler` | `common.incident_report_repository.IncidentReportRepository`, `common.response.json_response` | `IncidentReportsTable` | No | No custom trace write or structured logging path in code. |

## Flow Traceability

### Chat flow

1. Entry point: `POST /chat` in `backend/lambda/chat/handler.py`.
2. Validation/control steps: `_parse_body()` requires JSON with non-empty `message`; request ID and path are generated before runtime work.
3. Internal modules: `BedrockClient.converse()`, `TraceRepository.save_trace()`, `log_json()`, `json_response()`.
4. External AWS services used: Amazon Bedrock Runtime and DynamoDB `AiPlatformRequestTrace`.
5. Trace/log output: success writes a trace with `answer_preview`, `model_id`, `latency_ms`, and `status=completed`; failures log structured error data.
6. Current boundary / limitation: `/chat` is a basic Bedrock inference / smoke-test endpoint, not the controlled enterprise RAG path; no input guardrail, output guardrail, metadata filtering, or approval flow exists on `/chat`.

### Document ingestion flow

1. Entry point: `POST /documents` in `backend/lambda/documents/handler.py`.
2. Validation/control steps: `_parse_body()` validates `documentId`, `title`, `content`, and optional `projectId`, `customerId`, `documentType`; defaults are `default`, `default`, and `general`.
3. Internal modules: `chunk_document()`, `EmbeddingClient.embed_document()`, `DocumentRepository.delete_chunks_by_document_id()`, `DocumentRepository.save_chunks()`, `log_json()`.
4. External AWS services used: Amazon Bedrock Runtime embeddings and DynamoDB `DocumentChunksTable`.
5. Trace/log output: no trace-table write; CloudWatch logs record `document indexed` or embedding/unexpected failure events.
6. Current boundary / limitation: ingestion stores metadata on chunks, but no separate metadata registry or batch pipeline exists.

### Controlled RAG query flow

1. Entry point: `POST /rag/query` in `backend/lambda/rag_query/handler.py`, then `common.rag_service.run_rag_query()`.
2. Validation/control steps: request JSON must contain non-empty `question`; `normalize_filters()` validates filters; `resolve_access_context()` reads request headers; `evaluate_input_guardrail()` can block; `assert_filters_allowed()` can return `403`; `_filter_chunks_by_metadata()` constrains eligible chunks before similarity ranking.
3. Internal modules: `DocumentRepository.list_chunks()`, `EmbeddingClient.embed_query()`, `retrieve_top_chunks()`, `cosine_similarity()`, `_build_grounded_prompt()`, `BedrockClient.converse()`, `evaluate_output_guardrail()`, `TraceRepository.save_trace()`.
4. External AWS services used: DynamoDB `DocumentChunksTable`, DynamoDB `AiPlatformRequestTrace`, Amazon Bedrock Runtime embeddings, Amazon Bedrock Runtime Converse, CloudWatch Logs.
5. Trace/log output: blocked, no-source, and completed responses are trace-persisted; denied and failed branches log structured status/error details.
6. Current boundary / limitation: retrieval is DynamoDB scan plus in-Lambda filtering/ranking, and policy enforcement is header-based rather than identity-backed.

### Agent `answer_question` flow

1. Entry point: `POST /agent/run` with `task: answer_question` in `backend/lambda/agent_run/handler.py`.
2. Validation/control steps: `_parse_body()` requires non-empty `question`; filters are normalized; `build_plan()` returns the fixed read-only plan; shared RAG policy and guardrail checks run inside `run_rag_query()`.
3. Internal modules: `common.agent.build_plan()`, `common.rag_service.run_rag_query(..., save_trace=False)`, `common.agent.build_tool_call()`, `_save_agent_trace()`.
4. External AWS services used: DynamoDB `DocumentChunksTable`, Amazon Bedrock Runtime embeddings and Converse, DynamoDB `AiPlatformRequestTrace`, CloudWatch Logs.
5. Trace/log output: the shared RAG path does not save its own trace here; instead the agent writes one agent trace containing plan, tool calls, answer preview, and task status.
6. Current boundary / limitation: the agent can only call the shared RAG path through the allowlisted `rag_query` tool and does not invent new tool sequences.

### Agent `inspect_trace` flow

1. Entry point: `POST /agent/run` with `task: inspect_trace`.
2. Validation/control steps: `_parse_body()` requires non-empty `requestId`; `_tool_is_allowlisted("trace_lookup")` must pass.
3. Internal modules: `lookup_trace()`, `_build_trace_summary()`, `_summarize_trace_result()`, `_save_inspect_trace_agent_trace()`.
4. External AWS services used: DynamoDB `AiPlatformRequestTrace` and CloudWatch Logs for structured agent completion logging.
5. Trace/log output: writes an agent trace for `completed` or `not_found`; response includes compact trace summary fields.
6. Current boundary / limitation: it reads one trace record only; there is no query-by-status or history search inside the Lambda path.

### Agent `search_logs` flow

1. Entry point: `POST /agent/run` with `task: search_logs`.
2. Validation/control steps: `_parse_body()` validates `preset` and `minutes`; `_tool_is_allowlisted("log_search")` must pass; `RAG_QUERY_LOG_GROUP_NAME` must be configured.
3. Internal modules: `search_logs()`, `build_tool_call()`, `_save_search_logs_agent_trace()`.
4. External AWS services used: CloudWatch Logs `FilterLogEvents` and DynamoDB `AiPlatformRequestTrace`.
5. Trace/log output: response returns `logSummary` and capped events; an agent trace is saved with preset, minutes, matched event count, status, and answer preview.
6. Current boundary / limitation: only four presets exist and the Lambda returns a bounded recent event list, not Logs Insights output.

### Agent `investigate_recent_blocks` flow

1. Entry point: `POST /agent/run` with `task: investigate_recent_blocks`.
2. Validation/control steps: `minutes` is validated; both `log_search` and `trace_lookup` must be allowlisted; `RAG_QUERY_LOG_GROUP_NAME` must be configured.
3. Internal modules: `_run_bounded_blocked_investigation()`, `search_logs(..., preset="blocked")`, `extract_request_ids_from_log_events()`, `lookup_trace()`, `_build_investigation_trace_summary()`, `summarize_investigation()`, `_save_investigation_agent_trace()`.
4. External AWS services used: CloudWatch Logs `FilterLogEvents`, DynamoDB `AiPlatformRequestTrace`, CloudWatch Logs for the agent completion log.
5. Trace/log output: saves one agent trace with `matched_events`, `inspected_trace_count`, `inspected_trace_statuses`, and answer preview.
6. Current boundary / limitation: investigation is bounded to recent logs, capped event results, and up to three extracted request IDs.

### `propose_incident_report` flow

1. Entry point: `POST /agent/run` with `task: propose_incident_report`.
2. Validation/control steps: validates `minutes`; requires `log_search` and `trace_lookup` allowlist entries, `RAG_QUERY_LOG_GROUP_NAME`, and `ACTION_APPROVALS_TABLE_NAME`.
3. Internal modules: `_run_bounded_blocked_investigation()`, `build_incident_report_proposal()`, `_create_pending_approval()`, `ApprovalRepository.create_approval()`, `_save_proposed_action_agent_trace()`.
4. External AWS services used: CloudWatch Logs `FilterLogEvents`, DynamoDB `AiPlatformRequestTrace`, DynamoDB `ActionApprovalsTable`, CloudWatch Logs.
5. Trace/log output: writes an agent trace with `agent_mode=approval_required`; creates an approval record with `status=pending_approval` and `execution_status=pending_approval`.
6. Current boundary / limitation: proposal creation stops before execution; only the internal action type `create_incident_report` is produced.

### Approval decision flow

1. Entry point: `POST /approvals/{approvalId}/decision` in `backend/lambda/approvals/handler.py`.
2. Validation/control steps: `approvalId` path parameter is required; the approval record must exist; `_parse_decision_body()` only accepts `approved` or `rejected` plus `decidedBy`.
3. Internal modules: `ApprovalRepository.get_approval()`, `ApprovalRepository.update_decision()`, `json_response()`.
4. External AWS services used: DynamoDB `ActionApprovalsTable`.
5. Trace/log output: no custom trace write or structured `log_json()` path exists in the handler.
6. Current boundary / limitation: the decision endpoint records approval state only; it never executes the action.

### Approved internal execution flow

1. Entry point: `POST /approvals/{approvalId}/execute` in `backend/lambda/approvals/handler.py`.
2. Validation/control steps: `approvalId` and `executedBy` are required; approval must exist; status must be `approved`; execution status must be `approved_not_executed`; `proposed_action.actionType` must equal `create_incident_report`.
3. Internal modules: `ApprovalRepository.get_approval()`, `IncidentReportRepository.create_report()`, `ApprovalRepository.mark_executed()`, `json_response()`.
4. External AWS services used: DynamoDB `ActionApprovalsTable` and DynamoDB `IncidentReportsTable`.
5. Trace/log output: no custom trace record or structured logging helper is used; execution state is visible through the updated approval record and stored incident report.
6. Current boundary / limitation: execution is restricted to one internal DynamoDB write path; no external API, ticketing, email, or shell action exists in code.

## Environment Variables and Configuration

| Variable | Defined In | Used In | Purpose |
| --- | --- | --- | --- |
| `TRACE_TABLE_NAME` | `EchoFunction`, `ChatFunction`, `RagQueryFunction`, `AgentRunFunction` in `infra/cloudformation/template.yaml` | `backend/lambda/echo/handler.py`, `backend/lambda/chat/handler.py`, `backend/lambda/common/rag_service.py`, `backend/lambda/agent_run/handler.py` | Points runtime trace writes to `AiPlatformRequestTrace`. |
| `BEDROCK_MODEL_ID` | `ChatFunction`, `RagQueryFunction`, `AgentRunFunction` in the SAM template | `backend/lambda/chat/handler.py`, `backend/lambda/common/rag_service.py` | Selects the Bedrock Converse model for chat and grounded answer generation. |
| `DOCUMENT_CHUNKS_TABLE_NAME` | `DocumentsFunction`, `RagQueryFunction`, `AgentRunFunction` in the SAM template | `backend/lambda/documents/handler.py`, `backend/lambda/common/rag_service.py` | Points ingestion and retrieval code to `DocumentChunksTable`. |
| `EMBEDDING_MODEL_ID` | `DocumentsFunction`, `RagQueryFunction`, `AgentRunFunction` in the SAM template | `backend/lambda/documents/handler.py`, `backend/lambda/common/embedding_client.py`, `backend/lambda/common/rag_service.py` | Selects the embedding model for chunk and query embeddings. |
| `MIN_SIMILARITY_SCORE` | `RagQueryFunction`, `AgentRunFunction` in the SAM template | `backend/lambda/common/rag_service.py` | Sets the minimum cosine similarity threshold before a chunk is treated as grounded evidence. |
| `ACTION_APPROVALS_TABLE_NAME` | `AgentRunFunction`, `ApprovalsFunction` in the SAM template | `backend/lambda/agent_run/handler.py`, `backend/lambda/approvals/handler.py` | Points proposal and approval workflow code to `ActionApprovalsTable`. |
| `RAG_QUERY_LOG_GROUP_NAME` | `AgentRunFunction` in the SAM template | `backend/lambda/agent_run/handler.py`, `backend/lambda/common/log_search.py` | Tells the agent which Lambda log group to search for `search_logs` and bounded investigations. |
| `INCIDENT_REPORTS_TABLE_NAME` | `ApprovalsFunction`, `IncidentReportsFunction` in the SAM template | `backend/lambda/approvals/handler.py`, `backend/lambda/incident_reports/handler.py` | Points execution and report lookup code to `IncidentReportsTable`. |
| `API_BASE_URL` | Local shell environment for `scripts/run_rag_eval.py` | `scripts/run_rag_eval.py` | Required by the local evaluation script to call the deployed API. |

Related request-level configuration found in code, but not as environment variables:

- `X-User-Id`
- `X-Allowed-Project-Ids`
- `X-Allowed-Customer-Ids`

These headers are parsed in `backend/lambda/common/policy.py` and shape user identity plus allowed retrieval scope.

## Evidence Commands

Use the following repository-backed commands to verify the mappings above.

### Grep / find commands

```powershell
rg "Handler: .*lambda_handler|Path: /" infra/cloudformation/template.yaml
rg "TRACE_TABLE_NAME|DOCUMENT_CHUNKS_TABLE_NAME|ACTION_APPROVALS_TABLE_NAME|INCIDENT_REPORTS_TABLE_NAME|BEDROCK_MODEL_ID|EMBEDDING_MODEL_ID|MIN_SIMILARITY_SCORE|RAG_QUERY_LOG_GROUP_NAME" infra/cloudformation/template.yaml backend/lambda scripts
rg "answer_question|inspect_trace|search_logs|investigate_recent_blocks|propose_incident_report" backend/lambda/common backend/lambda/agent_run
rg "create_incident_report|pending_approval|approved_not_executed|executed" backend/lambda
```

### SAM template inspection commands

```powershell
sam build --template-file infra/cloudformation/template.yaml
sam validate --template-file infra/cloudformation/template.yaml
```

### Script execution commands

```powershell
$env:API_BASE_URL = "https://<api-id>.execute-api.<region>.amazonaws.com/v1"
python scripts/run_rag_eval.py
python scripts/view_trace.py --request-id <request-id> --table-name ai-platform-request-trace-dev
python scripts/view_eval_trace.py --case-id <case-id>
python scripts/get_lambda_log_groups.py --stack-name <stack-name>
python scripts/query_logs.py --log-group /aws/lambda/<function-name> --preset blocked --start-minutes-ago 60
```

### API smoke-test commands

```powershell
curl -X POST "$env:API_BASE_URL/chat" -H "Content-Type: application/json" -d @test-data/requests/chat-request.json
curl -X POST "$env:API_BASE_URL/rag/query" -H "Content-Type: application/json" -d @test-data/requests/rag-query-request.json
```

```bash
curl -X POST "$API_BASE_URL/chat" -H "Content-Type: application/json" --data @test-data/requests/chat-request.json
curl -X POST "$API_BASE_URL/rag/query" -H "Content-Type: application/json" --data @test-data/requests/rag-query-request.json
```

## Not Found / Needs Verification

The following architecture labels can be mapped to code behavior, but not to standalone dedicated modules:

- `Metadata filter` exists as `_filter_chunks_by_metadata()` inside `backend/lambda/common/rag_service.py`, not as a separate module.
- `Request trace writer` exists as direct `TraceRepository.save_trace()` calls from handlers and shared services, not as a separate service layer.
- `rag_query tool` exists as the `answer_question` branch in `backend/lambda/agent_run/handler.py` calling `common.rag_service.run_rag_query()`, not as its own tool module file.
- `Approval repository/service` is split between `backend/lambda/common/approval_repository.py` and handler-owned workflow logic in `backend/lambda/agent_run/handler.py` and `backend/lambda/approvals/handler.py`; there is no separate approval service module.