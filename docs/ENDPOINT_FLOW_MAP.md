# Endpoint Flow Map

## Purpose

This document describes each deployed API endpoint as an execution flow, based only on the current repository.

## Phase 7B Verification Result

- Verified against the current repository for the Phase 7B documentation-only pass.
- `POST /chat` is a basic Bedrock inference and smoke-test endpoint. It is not the controlled enterprise RAG path.
- `/chat` has no input guardrail, output guardrail, metadata filtering, or approval flow.
- `scripts/run_rag_eval.py` does exercise approval and execution flows through dedicated approval workflow cases.

## GET /health

- Purpose: Return a simple backend health response with static service metadata.
- Request shape summary: No request body is parsed; no required headers are enforced in code.
- Response shape summary: `200` with `status`, `service`, and `version`.
- Flow steps:
  1. API Gateway routes `GET /health` to `health.handler.lambda_handler`.
  2. The handler returns `common.response.json_response(200, {...})` with static values.
- Main files/modules: `backend/lambda/health/handler.py`, `backend/lambda/common/response.py`.
- Data stores used: None.
- Guardrails/policy checks: None.
- Trace/log behavior: No custom trace persistence or structured log path exists in the handler.
- Failure cases: No explicit application-level failure path is implemented in this handler.
- Demo command if available: No dedicated demo command was found in repository docs.

## POST /echo

- Purpose: Record a simple request payload in the trace table and echo it back with a generated request ID.
- Request shape summary: JSON body with required non-empty string field `message`.
- Response shape summary: `200` with `requestId`, `message`, and `status=recorded`.
- Flow steps:
  1. API Gateway routes `POST /echo` to `echo.handler.lambda_handler`.
  2. `_parse_body()` validates JSON and the `message` field.
  3. The handler creates a `request_id` and builds a trace record.
  4. `TraceRepository.save_trace()` writes the record to DynamoDB.
  5. `log_json()` emits a structured `echo request recorded` event.
  6. The handler returns the request ID and message.
- Main files/modules: `backend/lambda/echo/handler.py`, `backend/lambda/common/trace_repository.py`, `backend/lambda/common/logging.py`, `backend/lambda/common/response.py`.
- Data stores used: `AiPlatformRequestTrace`.
- Guardrails/policy checks: None.
- Trace/log behavior: Writes one trace record and one structured success log; invalid input logs a warning; unexpected failures log an exception.
- Failure cases: `400` for missing/invalid JSON or empty `message`; `500` for unexpected failures.
- Demo command if available:

```powershell
curl -X POST "$env:API_BASE_URL/echo" -H "Content-Type: application/json" -d @test-data/requests/echo-request.json
```

```bash
curl -X POST "$API_BASE_URL/echo" -H "Content-Type: application/json" --data @test-data/requests/echo-request.json
```

## POST /chat

- Purpose: Send a user message to Bedrock Converse as a basic Bedrock inference / smoke-test endpoint and persist a compact success trace.
- Request shape summary: JSON body with required non-empty string field `message`.
- Response shape summary: `200` with `requestId`, `answer`, `modelId`, and `status=completed`.
- Flow steps:
  1. API Gateway routes `POST /chat` to `chat.handler.lambda_handler`.
  2. `_parse_body()` validates the request body.
  3. `BedrockClient.converse()` sends the message to the model in `BEDROCK_MODEL_ID`.
  4. On success, the handler writes a trace record with `answer_preview`, `model_id`, and latency.
  5. A structured success log is emitted.
  6. The full answer is returned to the caller.
- Main files/modules: `backend/lambda/chat/handler.py`, `backend/lambda/common/bedrock_client.py`, `backend/lambda/common/trace_repository.py`, `backend/lambda/common/logging.py`, `backend/lambda/common/response.py`.
- Data stores used: `AiPlatformRequestTrace`.
- Guardrails/policy checks: None in the `/chat` path. This is not the controlled enterprise RAG path.
- Trace/log behavior: Success writes a trace and logs completion; Bedrock failures and unexpected exceptions are logged with status context.
- Failure cases: `400` for invalid request body; `502` when Bedrock invocation fails; `500` for unexpected failures.
- Demo command if available:

```powershell
curl -X POST "$env:API_BASE_URL/chat" -H "Content-Type: application/json" -d @test-data/requests/chat-request.json
```

```bash
curl -X POST "$API_BASE_URL/chat" -H "Content-Type: application/json" --data @test-data/requests/chat-request.json
```

- Current boundary / limitation: no input guardrail, output guardrail, metadata filtering, or approval flow exists on `/chat`.

## POST /documents

- Purpose: Chunk a document, generate embeddings for each chunk, and replace the stored chunk set for that document ID.
- Request shape summary: JSON body with required `documentId`, `title`, and `content`; optional `projectId`, `customerId`, and `documentType`.
- Response shape summary: `200` with `documentId`, `title`, `chunkCount`, and `status=indexed`.
- Flow steps:
  1. API Gateway routes `POST /documents` to `documents.handler.lambda_handler`.
  2. `_parse_body()` validates required fields and applies default metadata when optional fields are missing.
  3. `chunk_document()` splits the content into chunk-sized blocks.
  4. `EmbeddingClient.embed_document()` generates one embedding per chunk.
  5. `DocumentRepository.delete_chunks_by_document_id()` removes prior chunks for the document ID.
  6. `DocumentRepository.save_chunks()` stores the new chunk records, including metadata and embeddings.
  7. The handler logs indexing status and returns the chunk count.
- Main files/modules: `backend/lambda/documents/handler.py`, `backend/lambda/common/chunking.py`, `backend/lambda/common/document_repository.py`, `backend/lambda/common/embedding_client.py`, `backend/lambda/common/logging.py`, `backend/lambda/common/response.py`.
- Data stores used: `DocumentChunksTable`.
- Guardrails/policy checks: None.
- Trace/log behavior: No trace-table write; CloudWatch logs contain indexing success or failure information.
- Failure cases: `400` for invalid request body; `502` when embedding generation fails; `500` for unexpected failures.
- Demo command if available:

```powershell
curl -X POST "$env:API_BASE_URL/documents" -H "Content-Type: application/json" -d @test-data/requests/document-request.json
```

```bash
curl -X POST "$API_BASE_URL/documents" -H "Content-Type: application/json" --data @test-data/requests/document-request.json
```

## POST /rag/query

- Purpose: Run the controlled RAG path over indexed chunks and return a grounded answer, a blocked response, or a no-source response.
- Request shape summary: JSON body with required non-empty `question`; optional `filters.projectId`, `filters.customerId`, and `filters.documentType`.
- Response shape summary: On success-style flows, `200` with `requestId`, `userId`, `answer`, `sources`, `modelId`, `embeddingModelId`, `retrievalMode`, `minSimilarityScore`, `filters`, `guardrail`, `outputGuardrail`, and `status`. On policy denial, `403` with `message`.
- Flow steps:
  1. API Gateway routes `POST /rag/query` to `rag_query.handler.lambda_handler`.
  2. `_parse_body()` validates the question and normalizes filters.
  3. `run_rag_query()` resolves access context from request headers.
  4. `evaluate_input_guardrail()` can return a `blocked` response before retrieval.
  5. `assert_filters_allowed()` can reject disallowed retrieval scopes with `403`.
  6. `DocumentRepository.list_chunks()` loads chunk records and `_filter_chunks_by_metadata()` applies metadata boundaries.
  7. `EmbeddingClient.embed_query()` generates the query embedding.
  8. `retrieve_top_chunks()` ranks eligible chunks by cosine similarity and enforces `MIN_SIMILARITY_SCORE`.
  9. If no chunk qualifies, the handler returns `status=no_source` without a Bedrock Converse call.
  10. If chunks qualify, `_build_grounded_prompt()` builds the model prompt, `BedrockClient.converse()` generates the answer, and `evaluate_output_guardrail()` assesses the result.
  11. A trace record is persisted and the response is returned.
- Main files/modules: `backend/lambda/rag_query/handler.py`, `backend/lambda/common/rag_service.py`, `backend/lambda/common/policy.py`, `backend/lambda/common/guardrails.py`, `backend/lambda/common/output_guardrails.py`, `backend/lambda/common/document_repository.py`, `backend/lambda/common/embedding_client.py`, `backend/lambda/common/retrieval.py`, `backend/lambda/common/vector_math.py`, `backend/lambda/common/bedrock_client.py`, `backend/lambda/common/trace_repository.py`, `backend/lambda/common/logging.py`.
- Data stores used: `DocumentChunksTable`, `AiPlatformRequestTrace`.
- Guardrails/policy checks: Input guardrail, header-derived access context, allowed filter enforcement, metadata pre-filtering, and output guardrail.
- Trace/log behavior: Saves trace records for `blocked`, `no_source`, and `completed`; logs unscoped requests, access-denied cases, invocation failures, and unexpected failures.
- Failure cases: `400` for invalid request body or invalid filters; `403` when filter scope is denied; `502` when embedding or Bedrock invocation fails; `500` for unexpected failures.
- Demo command if available:

```powershell
curl -X POST "$env:API_BASE_URL/rag/query" -H "Content-Type: application/json" -d @test-data/requests/rag-query-request.json
```

```bash
curl -X POST "$API_BASE_URL/rag/query" -H "Content-Type: application/json" --data @test-data/requests/rag-query-request.json
```

## POST /agent/run

- Purpose: Execute one bounded agent task using fixed plans and allowlisted tools.
- Request shape summary: JSON body with required `task`. Additional fields depend on the task:
  - `answer_question`: `question`, optional `filters`
  - `inspect_trace`: `requestId`
  - `search_logs`: optional `preset`, optional `minutes`
  - `investigate_recent_blocks`: optional `minutes`
  - `propose_incident_report`: optional `minutes`
- Response shape summary: Structured task result containing `requestId`, `agentMode`, `task`, `plan`, `toolCalls`, task-specific payload, `answer`, and `status`. `propose_incident_report` also returns `approvalId` and `proposedAction`.
- Flow steps:
  1. API Gateway routes `POST /agent/run` to `agent_run.handler.lambda_handler`.
  2. `_parse_body()` validates the task-specific request shape.
  3. `build_plan()` generates a fixed plan for the selected task.
  4. `resolve_access_context()` resolves the caller identity context.
  5. One task branch is executed:
     - `answer_question` calls the shared RAG path through the allowlisted `rag_query` branch.
     - `inspect_trace` calls `lookup_trace()`.
     - `search_logs` calls `search_logs()`.
     - `investigate_recent_blocks` chains `search_logs()`, request ID extraction, and `lookup_trace()`.
     - `propose_incident_report` runs the bounded investigation, builds a proposal, and writes an approval record.
  6. The handler writes an agent trace and returns a structured result.
- Main files/modules: `backend/lambda/agent_run/handler.py`, `backend/lambda/common/agent.py`, `backend/lambda/common/rag_service.py`, `backend/lambda/common/trace_lookup.py`, `backend/lambda/common/log_search.py`, `backend/lambda/common/investigation.py`, `backend/lambda/common/action_proposal.py`, `backend/lambda/common/approval_repository.py`, `backend/lambda/common/trace_repository.py`, `backend/lambda/common/logging.py`, `backend/lambda/common/response.py`.
- Data stores used: Always `AiPlatformRequestTrace`; `DocumentChunksTable` for `answer_question`; `ActionApprovalsTable` for `propose_incident_report`.
- Guardrails/policy checks: Task validation, tool allowlist checks, shared RAG guardrail/policy path for `answer_question`, log group configuration checks for log-search tasks, and approval table configuration for proposal creation.
- Trace/log behavior: Every successful or terminal task branch writes an agent trace; structured CloudWatch logs include task, user, status, tool calls, and investigation/proposal metadata.
- Failure cases: `400` for invalid task payloads or unsupported tasks; `500` when required tools or configuration are missing; `404` for `inspect_trace` when the trace does not exist; `403` only through the shared RAG path used by `answer_question`.
- Demo command if available:

```powershell
curl -X POST "$env:API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "X-User-Id: user-learning" -H "X-Allowed-Project-Ids: learning" -H "X-Allowed-Customer-Ids: internal" -d '{"task":"answer_question","question":"What does API Gateway do?","filters":{"projectId":"learning","customerId":"internal"}}'
```

```bash
curl -X POST "$API_BASE_URL/agent/run" -H "Content-Type: application/json" -H "X-User-Id: user-learning" -H "X-Allowed-Project-Ids: learning" -H "X-Allowed-Customer-Ids: internal" -d '{"task":"answer_question","question":"What does API Gateway do?","filters":{"projectId":"learning","customerId":"internal"}}'
```

## GET /approvals/{approvalId}

- Purpose: Fetch one approval record created by the agent proposal flow.
- Request shape summary: Path parameter `approvalId` is required; no request body is used.
- Response shape summary: `200` with the stored approval record, or error payload with `message`.
- Flow steps:
  1. API Gateway routes `GET /approvals/{approvalId}` to `approvals.handler.lambda_handler`.
  2. The handler verifies `ACTION_APPROVALS_TABLE_NAME` and extracts `approvalId`.
  3. `ApprovalRepository.get_approval()` loads the record.
  4. The record is returned or a `404` is emitted.
- Main files/modules: `backend/lambda/approvals/handler.py`, `backend/lambda/common/approval_repository.py`, `backend/lambda/common/response.py`.
- Data stores used: `ActionApprovalsTable`.
- Guardrails/policy checks: None beyond path parameter and configuration validation.
- Trace/log behavior: No custom trace or structured logging path exists.
- Failure cases: `500` when the approval table env var is missing; `400` when `approvalId` is missing; `404` when the record is not found.
- Demo command if available: No standalone curl example was found; this endpoint is exercised indirectly by `python scripts/run_rag_eval.py` during approval workflow cases.

## POST /approvals/{approvalId}/decision

- Purpose: Record a human approval or rejection decision against a pending approval record.
- Request shape summary: Path parameter `approvalId`; JSON body with required `decision` (`approved` or `rejected`) and required `decidedBy`; optional `comment`.
- Response shape summary: `200` with `approvalId`, updated `status`, `decision`, and `executionStatus`.
- Flow steps:
  1. API Gateway routes `POST /approvals/{approvalId}/decision` to `approvals.handler.lambda_handler`.
  2. The handler verifies table configuration and loads the approval record.
  3. `_parse_decision_body()` validates the request body.
  4. `ApprovalRepository.update_decision()` updates status, decision metadata, and execution status.
  5. The compact decision result is returned.
- Main files/modules: `backend/lambda/approvals/handler.py`, `backend/lambda/common/approval_repository.py`, `backend/lambda/common/response.py`.
- Data stores used: `ActionApprovalsTable`.
- Guardrails/policy checks: Only request shape and approval existence checks.
- Trace/log behavior: No custom trace or structured logging path exists.
- Failure cases: `500` when the approval table env var is missing; `400` for missing `approvalId`, invalid JSON, invalid `decision`, or invalid `decidedBy`; `404` when the approval record is not found.
- Demo command if available: No standalone curl example was found; this endpoint is exercised indirectly by `python scripts/run_rag_eval.py` during approval workflow and execution cases.

## POST /approvals/{approvalId}/execute

- Purpose: Execute an approved internal action after explicit state validation.
- Request shape summary: Path parameter `approvalId`; JSON body with required `executedBy`.
- Response shape summary: `200` with `approvalId`, `reportId`, `status=executed`, and `executionStatus=executed` on success.
- Flow steps:
  1. API Gateway routes `POST /approvals/{approvalId}/execute` to `approvals.handler.lambda_handler`.
  2. The handler verifies approval and incident report table configuration.
  3. `_parse_execute_body()` validates `executedBy`.
  4. The approval record is loaded and checked for `status=approved` and `execution_status=approved_not_executed`.
  5. The handler verifies that `proposed_action.actionType` is `create_incident_report`.
  6. A report record is built and persisted through `IncidentReportRepository.create_report()`.
  7. `ApprovalRepository.mark_executed()` updates the approval record with execution metadata.
  8. The report ID and execution status are returned.
- Main files/modules: `backend/lambda/approvals/handler.py`, `backend/lambda/common/approval_repository.py`, `backend/lambda/common/incident_report_repository.py`, `backend/lambda/common/response.py`.
- Data stores used: `ActionApprovalsTable`, `IncidentReportsTable`.
- Guardrails/policy checks: Explicit approval state and action-type checks gate execution.
- Trace/log behavior: No custom trace or structured logging path exists.
- Failure cases: `500` when required table env vars are missing; `400` for missing `approvalId`, invalid JSON, invalid `executedBy`, or unsupported action type; `404` when the approval record is not found; `409` when the approval record is not in an executable state.
- Demo command if available: No standalone curl example was found; this endpoint is exercised indirectly by `python scripts/run_rag_eval.py` during `approval_execute_internal_report` cases.

## GET /incident-reports/{reportId}

- Purpose: Fetch one internally created incident report record.
- Request shape summary: Path parameter `reportId` is required; no request body is used.
- Response shape summary: `200` with the stored incident report record, or error payload with `message`.
- Flow steps:
  1. API Gateway routes `GET /incident-reports/{reportId}` to `incident_reports.handler.lambda_handler`.
  2. The handler verifies `INCIDENT_REPORTS_TABLE_NAME` and extracts `reportId`.
  3. `IncidentReportRepository.get_report()` loads the record from DynamoDB.
  4. The stored report is returned or a `404` is emitted.
- Main files/modules: `backend/lambda/incident_reports/handler.py`, `backend/lambda/common/incident_report_repository.py`, `backend/lambda/common/response.py`.
- Data stores used: `IncidentReportsTable`.
- Guardrails/policy checks: None beyond path parameter and configuration validation.
- Trace/log behavior: No custom trace or structured logging path exists.
- Failure cases: `500` when the incident reports table env var is missing; `400` when `reportId` is missing; `404` when the report is not found.
- Demo command if available: No standalone curl example was found; this endpoint is exercised indirectly by `python scripts/run_rag_eval.py` when approval execution creates and reads a report.