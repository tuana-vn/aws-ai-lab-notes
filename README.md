# AWS AI Platform PoC

This repository contains a minimal AWS backend foundation for an AI platform, now extended through Phase 6E with a mini RAG flow that stores document embeddings in DynamoDB, filters eligible chunks by metadata boundaries, validates requested retrieval scope against a simple caller policy, applies AWS-side throttling protections, blocks unsafe input patterns before retrieval, filters weak matches with a similarity threshold, validates output grounding signals, and exposes a controlled agent wrapper around the same retrieval path with an explicit approval boundary for proposed write actions.

## Why this foundation exists

This first step establishes the API, Lambda execution model, request tracing, and infrastructure boundaries before Amazon Bedrock is introduced. That keeps the Bedrock integration focused later on business capabilities such as `/chat`, `/rag/query`, and `/agent/run`, instead of mixing those concerns with initial platform plumbing.

Phase 2 adds only the smallest useful Bedrock capability: a `/chat` endpoint that sends one user message to the Bedrock Converse API, returns the model answer, records a short trace in DynamoDB, and logs the request lifecycle to CloudWatch.

Phase 3A added a learning-focused mini RAG foundation. Documents were split into simple chunks and stored in DynamoDB. A `/rag/query` request scanned those chunks, ranked them by keyword overlap, built a grounded prompt, and asked Bedrock to answer only from the retrieved context.

Phase 3B upgrades that retrieval step from keyword overlap to embedding-based semantic similarity. Each chunk is embedded during `/documents` ingestion, stored with its vector, and later compared with the question embedding using cosine similarity inside the Lambda.

## Target architecture

Client -> API Gateway -> Lambda -> DynamoDB -> CloudWatch Logs

Mini RAG flow:

Client -> API Gateway -> Documents Lambda -> Bedrock Embed -> DynamoDB DocumentChunks

Client -> API Gateway -> RagQuery Lambda -> Bedrock Embed -> DynamoDB DocumentChunks Scan -> Cosine Similarity -> Bedrock Converse API -> DynamoDB Trace -> CloudWatch Logs

## Project structure

```text
aws-ai-platform-poc/
  README.md
  backend/
    lambda/
      common/
        action_proposal.py
        bedrock_client.py
        chunking.py
        document_repository.py
        embedding_client.py
        investigation.py
        log_search.py
        response.py
        logging.py
        retrieval.py
        trace_lookup.py
        trace_repository.py
        vector_math.py
      agent_run/
        handler.py
      chat/
        handler.py
      documents/
        handler.py
      health/
        handler.py
      echo/
        handler.py
      rag_query/
        handler.py
  infra/
    cloudformation/
      template.yaml
  scripts/
    run_rag_eval.py
    get_lambda_log_groups.py
    query_logs.py
    view_trace.py
    view_eval_trace.py
  test-data/
    requests/
      chat-request.json
      document-request.json
      echo-request.json
      rag-query-request.json
    rag-evaluation/
      questions.json
      documents/
        api-gateway-note.json
```

Phase 3C adds a local evaluation workflow that re-indexes a known document, runs a small set of grounded RAG questions against the deployed API, and writes both raw JSON results and a readable Markdown report under a local `reports/` folder.

Phase 3D hardens the retrieval step with `MIN_SIMILARITY_SCORE`, defaulting to `0.25`. Chunks below that threshold are treated as not grounded enough, so `/rag/query` returns a `no_source` result with an empty `sources` array instead of sending weak context to the LLM.

Phase 4A adds metadata boundaries. Documents can now carry `projectId`, `customerId`, and `documentType`, and `/rag/query` can apply those filters before similarity scoring so retrieval stays inside the intended document scope.

Phase 4B adds a retrieval policy gate. `/rag/query` now resolves a caller access context from request headers and rejects disallowed `projectId` or `customerId` scopes before metadata filtering or embedding retrieval starts.

Phase 4C adds backend protection controls in infrastructure. API Gateway stage throttling now caps request rate before Lambda is invoked. Reserved concurrency remains a recommended control for expensive Lambdas, but it is not enabled by default in this learning template because small AWS accounts may have low concurrency quota.

Phase 5A adds an application-level input guardrail for `/rag/query`. The request question is checked before policy gate, metadata filtering, embedding generation, retrieval, or Bedrock invocation so obvious prompt injection and unsafe data access attempts are blocked early.

## Endpoints

### GET /health

Returns a fixed service health payload:

```json
{
  "status": "ok",
  "service": "aws-ai-platform-api",
  "version": "0.1.0"
}
```

### POST /echo

Request body:

```json
{
  "message": "hello AWS AI Platform"
}
```

Successful response:

```json
{
  "requestId": "<generated uuid>",
  "message": "hello AWS AI Platform",
  "status": "recorded"
}
```

### POST /chat

Request body:

```json
{
  "message": "Explain what an API Gateway does in simple terms."
}
```

Successful response:

```json
{
  "requestId": "<generated uuid>",
  "answer": "<model answer>",
  "modelId": "apac.amazon.nova-lite-v1:0",
  "status": "completed"
}
```

The `/chat` Lambda validates the request, calls the Bedrock Runtime Converse API through boto3, returns the model output, and stores a compact trace record in DynamoDB with request metadata, answer preview, model ID, and latency.

### POST /documents

Request body:

```json
{
  "documentId": "api-gateway-note",
  "title": "API Gateway Note",
  "projectId": "learning",
  "customerId": "internal",
  "documentType": "technical-note",
  "content": "Amazon API Gateway is a managed service that helps developers create, publish, maintain, monitor, and secure APIs. It can act as the front door for applications to access backend services such as Lambda functions or container-based services. API Gateway can handle routing, throttling, authorization, request validation, and integration with AWS services."
}
```

Successful response:

```json
{
  "documentId": "api-gateway-note",
  "title": "API Gateway Note",
  "chunkCount": 1,
  "status": "indexed"
}
```

`/documents` now generates an embedding for each chunk with the Bedrock model in `EMBEDDING_MODEL_ID`, defaulting to `cohere.embed-english-v3`, then stores both the chunk text and embedding in DynamoDB.

### POST /rag/query

Request body:

```json
{
  "question": "What does API Gateway do?",
  "filters": {
    "projectId": "learning",
    "customerId": "internal",
    "documentType": "technical-note"
  }
}
```

Successful response:

```json
{
  "requestId": "<uuid>",
  "answer": "<grounded answer>",
  "sources": [
    {
      "documentId": "api-gateway-note",
      "chunkId": "chunk-0001",
      "title": "API Gateway Note",
      "chunkIndex": 0,
      "similarity": 0.82,
      "projectId": "learning",
      "customerId": "internal",
      "documentType": "technical-note"
    }
  ],
  "modelId": "apac.amazon.nova-lite-v1:0",
  "embeddingModelId": "cohere.embed-english-v3",
  "retrievalMode": "embedding",
  "minSimilarityScore": 0.25,
  "filters": {
    "projectId": "learning",
    "customerId": "internal",
    "documentType": "technical-note"
  },
  "status": "completed"
}
```

When no similar chunks are found, `/rag/query` returns `I do not know based on the available documents.` with an empty `sources` array and a `no_source` status. This keeps the RAG flow explicit and grounded instead of guessing.

`/rag/query` now loads chunks from DynamoDB, applies optional metadata filters first, calculates cosine similarity only for the eligible chunks, keeps only chunks with similarity greater than or equal to `MIN_SIMILARITY_SCORE`, selects the top 3 remaining chunks, and only then calls Bedrock Converse for answer generation.

## Design notes

- `requestId` is generated inside the Lambda so each request can be correlated across API responses, DynamoDB trace records, and CloudWatch logs.
- DynamoDB trace storage gives a simple, durable request audit trail that is useful for debugging and operational visibility while the platform is still small.
- The Echo Lambda is granted only `dynamodb:PutItem` on the single trace table because IAM policies should stay least-privilege from the beginning.
- The Chat Lambda uses the Bedrock Runtime Converse API with a model ID from `BEDROCK_MODEL_ID`, defaulting to `amazon.nova-lite-v1:0` for a simple first integration.
- The chat trace stores only `answer_preview` instead of the full answer so the trace table stays lightweight and avoids persisting long model outputs by default.
- Phase 3B keeps the mini RAG intentionally simple. Retrieval is embedding-based, but storage still uses DynamoDB and retrieval still scans all chunks inside Lambda.
- Keyword retrieval is a good first step for learning because the logic is visible. Embedding retrieval improves recall for semantically related wording, even when the question and document chunks do not share many exact tokens.
- DynamoDB Scan plus cosine similarity inside Lambda is acceptable here only because this is a learning PoC. Production retrieval should use a proper vector store, Bedrock Knowledge Bases, or another indexed retrieval system.
- The repository stores embeddings alongside chunk content for clarity. In production, embeddings usually belong in a dedicated vector-capable system rather than a full-table DynamoDB scan path.
- The code intentionally avoids extra frameworks so the Lambda and SAM patterns remain easy to learn and easy to extend.

## Phase 3B purpose

Phase 3B exists to make the retrieval step more realistic without introducing a full managed retrieval stack yet. It shows the mechanics of:

- generating document embeddings during ingestion
- generating query embeddings at request time
- comparing vectors with cosine similarity
- selecting top chunks before grounded answer generation

This keeps the retrieval logic visible and debuggable while still demonstrating a meaningful improvement over keyword overlap.

## Keyword vs embedding retrieval

- Keyword retrieval matches exact or overlapping terms. It is simple and transparent, but it misses semantically similar phrasing.
- Embedding retrieval converts text into vectors so semantically related content can rank well even when the exact words differ.
- This Phase 3B implementation still stays intentionally small: one embedding model, DynamoDB storage, a scan, and cosine similarity in Lambda.

## Learning-only scaling note

Scanning DynamoDB and computing cosine similarity in Lambda is acceptable here only because the goal is to learn the RAG control flow end to end. It should not be treated as a production retrieval design because full scans increase latency and cost as the document set grows.

For production, prefer one of these options:

- Bedrock Knowledge Bases
- OpenSearch Serverless vector index
- Aurora PostgreSQL with pgvector
- another vector database or managed vector retrieval service

## Required AWS permissions

To deploy and run Phase 2, the environment needs permission for:

- CloudFormation and SAM deployment operations
- Lambda create, update, and invoke permissions
- API Gateway deployment permissions
- DynamoDB table creation and `dynamodb:PutItem`
- DynamoDB `dynamodb:Scan` on the document chunk table for the learning retrieval flow
- DynamoDB `dynamodb:DeleteItem` and `dynamodb:Query` on the document chunk table for re-indexing
- Bedrock runtime access, including `bedrock:InvokeModel` and `bedrock:Converse`

The SAM template keeps DynamoDB access scoped to the specific tables. Bedrock access uses `Resource: "*"` in this PoC because model and inference profile ARN scoping varies by setup; production should narrow that policy to approved model or profile resources.

## Deployment

From the `aws-ai-platform-poc` folder:

```bash
sam build --template-file infra/cloudformation/template.yaml
sam deploy --guided --template-file infra/cloudformation/template.yaml
```

## How to test /chat

Use `test-data/requests/chat-request.json` as the request body for `POST /chat` after deployment.

Example:

```bash
curl -X POST "$API_BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d @test-data/requests/chat-request.json
```

`/chat` calls Amazon Bedrock and may incur cost depending on the model, tokens processed, and AWS account pricing.

## How to test /documents

Use `test-data/requests/document-request.json` as the request body for `POST /documents`.

```bash
curl -X POST "$API_BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -d @test-data/requests/document-request.json
```

`/documents` now calls the Bedrock embedding model for each chunk and may incur additional Bedrock cost depending on chunk count, text size, and account pricing.

## How to test /rag/query

Use `test-data/requests/rag-query-request.json` after indexing at least one document.

```bash
curl -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -d @test-data/requests/rag-query-request.json
```

`/rag/query` now uses embedding retrieval. It also calls Bedrock for answer generation, so both embedding generation and final answer generation may incur cost.

## Phase 3C - RAG Evaluation

RAG evaluation is needed because a grounded answer pipeline can fail in more than one way: retrieval can miss the right chunk, the model can answer without grounding to the expected source, or the system can fail to refuse questions that are outside the indexed documents. A small local evaluation loop makes those failure modes visible with repeatable test cases.

The Phase 3C script uploads a known document to `/documents`, runs evaluation questions against `/rag/query`, and writes two local artifacts:

- `reports/rag-eval-results.json` for raw machine-readable results
- `reports/rag-eval-report.md` for a quick human review

Run it from the `aws-ai-platform-poc` folder:

```bash
export API_BASE_URL="https://xxxxx.execute-api.ap-southeast-1.amazonaws.com/v1"
python3 scripts/run_rag_eval.py
```

Read the Markdown report first to see total pass/fail counts, per-case notes, source document IDs, and short answer snippets. Use the JSON file when you want the full request expectations and raw API responses for each evaluation case.

## Phase 3D - Similarity Threshold and No-Source Hardening

Similarity thresholding is needed because similarity greater than zero is too weak for grounded retrieval. A chunk can be mathematically closer than zero while still being effectively unrelated to the user question. Sending those weak matches to the LLM increases the chance of noisy citations, irrelevant `sources`, and answers that look grounded when they are not.

Phase 3D adds `MIN_SIMILARITY_SCORE`, with a default value of `0.25` for this learning PoC. The `/rag/query` flow still computes cosine similarity for every scanned chunk, but it now drops chunks below the threshold before ranking the top results.

This matters for out-of-source questions. If no chunk meets the threshold, the Lambda does not call Bedrock Converse. Instead it returns the existing no-answer text, an empty `sources` array, `status: no_source`, and includes both `retrievalMode` and `minSimilarityScore` in the response for easier debugging.

The threshold is configured on `RagQueryFunction` through the environment variable `MIN_SIMILARITY_SCORE`. For this PoC, `0.25` is a readable starting point: high enough to block obviously weak matches, but still simple enough to tune while learning how retrieval quality changes.

## Phase 4A - Metadata Filter and Multi-Document Boundary

Metadata filtering is needed because similarity decides relevance, but metadata decides eligibility. A chunk can be semantically similar to a question and still belong to the wrong project, the wrong customer boundary, or the wrong document class.

Phase 4A adds `projectId`, `customerId`, and `documentType` to indexed document chunks. These values are stored on every chunk during `/documents` ingestion, with defaults of `default`, `default`, and `general` when the request does not provide them.

In `/rag/query`, metadata filtering happens before similarity search. That order matters: the system should first decide which chunks are allowed to participate, then rank only those eligible chunks by cosine similarity. Filtering after similarity would let out-of-bound documents influence the candidate set before the boundary is enforced.

This is still a learning PoC. Production systems should combine metadata filtering with IAM or application authorization checks and with a retrieval engine that can enforce metadata predicates during indexed vector search, rather than relying on a full DynamoDB scan inside Lambda.

## Phase 4B - Retrieval Policy Gate and Authorization Boundary

Metadata filters alone are not enough because the backend should not blindly trust caller-provided scope values. Without a policy check, a caller could request `projectId` or `customerId` values outside its intended boundary and the system would still search that content if matching chunks exist.

Phase 4B adds a simple authorization boundary before retrieval. The `/rag/query` flow now parses the question and filters, resolves caller access from HTTP headers, checks whether the requested `projectId` and `customerId` are allowed for that caller, and returns HTTP `403` if the requested scope is not permitted.

This learning PoC uses headers only:

- `X-User-Id`
- `X-Allowed-Project-Ids`
- `X-Allowed-Customer-Ids`

If the user header is missing, the handler defaults to `anonymous`. If the allowed-scope headers are missing, the PoC defaults to `default` scope lists. `documentType` is still used for metadata filtering, but it is not access-controlled in this phase.

This is intentionally not production-grade authorization. In production, replace these learning headers with a real authorization layer such as Cognito and JWT claims, IAM-backed identity propagation, OPA or Cedar-based policy evaluation, or another application authorization service.

## Phase 4C - API Throttling and Reserved Concurrency

Lambda already scales automatically, which is useful for normal traffic but dangerous for AI and RAG endpoints when requests become abusive or accidentally spike. In this PoC, `/chat`, `/documents`, and especially `/rag/query` can trigger Bedrock calls and DynamoDB activity, so unlimited scale would translate directly into higher cost and more pressure on downstream services.

Phase 4C adds API Gateway stage throttling directly in the template, and it documents reserved concurrency as a follow-on protection control to enable only after checking account quota.

- API Gateway stage throttling applies a default rate and burst limit across methods. When traffic exceeds that limit, API Gateway returns HTTP `429` before Lambda is invoked.
- Lambda reserved concurrency can cap the number of concurrent executions for the expensive AI paths so they cannot consume unbounded concurrency.

Reserved concurrency is especially important for `/rag/query` because that path can combine embedding generation, DynamoDB scan-based retrieval, and Bedrock Converse in a single request. When enabled, it helps protect Bedrock throughput, DynamoDB load, and the overall cost budget for this learning environment.

The template keeps these API Gateway throttling parameters exposed so the PoC stays easy to tune:

- `ApiStageThrottleRateLimit` default `10`
- `ApiStageThrottleBurstLimit` default `20`

Reserved concurrency is intentionally not enabled by default in this learning template. The observed learning case was an account with Lambda concurrency quota `10`, while the attempted reserved concurrency total was `13` across Chat, Documents, and RagQuery, which caused CloudFormation rollback during deployment.

Enable reserved concurrency later only after confirming your account quota or after requesting a quota increase.

This is still only a first protection layer. Production systems should also consider AWS WAF, usage plans and API keys where appropriate, real authentication, per-user or per-tenant rate limits, cost budgets, and CloudWatch alarms.

## Phase 5A - Application Guardrails for `/rag/query`

Application-level input guardrails are needed because some unsafe requests should be stopped before retrieval even begins. If a question is clearly attempting prompt injection or unsafe data access, the safest and cheapest behavior is to block it before policy checks, DynamoDB scan, embedding generation, or Bedrock calls.

Phase 5A adds a simple learning PoC guardrail that uses case-insensitive pattern matching against the incoming question. It currently blocks obvious prompt injection phrases such as attempts to ignore instructions or reveal prompts, and it also blocks obvious unsafe data access requests such as asking for customer secrets or dumping all documents.

This is intentionally simple and readable. It is useful for understanding where an application guardrail belongs in the request flow, but it is not strong enough for production by itself.

Production systems should combine stronger controls such as Bedrock Guardrails, policy engines, classification models, PII detection, monitoring, alerting, and human review for risky or high-impact actions.

## Phase 5B - Output Guardrail and Answer Validation

Input guardrails check the user request before retrieval starts. Output guardrails check the model answer after generation. These solve different problems: the input guardrail is about stopping unsafe requests early, while the output guardrail is about checking whether the returned answer still looks acceptable after the model has already generated it.

Phase 5B adds a simple output validation step for `/rag/query`. After Bedrock returns an answer, the handler evaluates whether the answer is empty or whether it appears to omit source references even though retrieved sources were provided. In this learning PoC, the output guardrail only warns. It does not block the response yet.

This keeps the behavior easy to observe during evaluation. The response and trace now include output guardrail metadata so you can see when an answer looks grounded versus when it should be reviewed more carefully.

Production systems can enforce stricter validation, stronger citation requirements, Bedrock Guardrails, model-based output review, or human approval workflows for sensitive actions.

## Phase 5C - Observability Cleanup and Trace Viewer

Evaluation shows pass or fail for each local test case, but it does not by itself explain the full execution path inside the backend. DynamoDB trace records show the request metadata, retrieval path, guardrail decisions, and answer preview. CloudWatch logs then provide the runtime log stream around the same request.

Phase 5C adds two small local helper scripts:

- `scripts/view_trace.py` fetches one trace record directly from DynamoDB by `requestId`
- `scripts/view_eval_trace.py` connects an evaluation `caseId` to its stored trace when a `requestId` exists in the evaluation result

Example commands:

```bash
python3 scripts/view_trace.py --request-id <requestId>
python3 scripts/view_eval_trace.py --case-id Q009
python3 scripts/view_eval_trace.py --case-id Q007
```

Use `view_trace.py` when you already know a `requestId` from an API response or evaluation output. Use `view_eval_trace.py` when you want to start from an evaluation case and inspect the corresponding trace record.

For learning scenarios:

- `Q007` and `Q008` should show input guardrail blocked behavior
- `Q009` should show output guardrail observation behavior
- `Q006` policy-denied may not have a `requestId`, depending on implementation, so the helper may report that no trace lookup is available

## Phase 5D - CloudWatch Logs Insights and Runtime Observability

DynamoDB trace is useful when you want to inspect one specific request. CloudWatch Logs Insights is useful when you want runtime aggregation across many requests, such as blocked requests, `no_source` traffic, latency trends, or errors over time.

Phase 5D adds two local helper scripts:

- `scripts/query_logs.py` runs CloudWatch Logs Insights preset queries through the AWS CLI
- `scripts/get_lambda_log_groups.py` lists Lambda function names and their log groups for a stack

Use `query_logs.py` to inspect runtime patterns such as blocked guardrail requests, `no_source` requests, errors, latency summaries, and guardrail counts. Use `get_lambda_log_groups.py` when you need the correct log group name for a Lambda before running a Logs Insights query.

Example commands:

```bash
python3 scripts/get_lambda_log_groups.py --stack-name aws-ai-platform-poc-dev
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset summary
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset blocked
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset no-source
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset errors
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset latency
python3 scripts/query_logs.py --log-group "/aws/lambda/<rag-query-function-name>" --preset guardrails
```

If Logs Insights does not automatically parse the structured JSON fields the way you expect, use the `raw` preset first to inspect `@message` directly and confirm what CloudWatch is extracting.

## Local test payload

Use `test-data/requests/echo-request.json` as a sample request body for `POST /echo`.
Use `test-data/requests/chat-request.json` as a sample request body for `POST /chat`.
Use `test-data/requests/document-request.json` as a sample request body for `POST /documents`.
Use `test-data/requests/rag-query-request.json` as a sample request body for `POST /rag/query`.
Use `test-data/rag-evaluation/questions.json` with `scripts/run_rag_eval.py` for the Phase 3C local RAG evaluation flow.

## Phase 6A - Controlled Read-only Agent Skeleton

Phase 6A adds `POST /agent/run` as the first controlled agent entrypoint. The key idea is that the agent is not magic. It is a thin orchestrator with an explicit allowlist and an explicit plan. In this phase, the allowlist contains exactly one read-only tool: `rag_query`.

The agent does not get arbitrary execution, arbitrary external tools, or permission to mutate state. It validates the request, follows a fixed read-only plan, invokes the shared RAG service, and returns both the answer and the tool execution summary.

This also avoids a behavior fork. The main retrieval, guardrail, policy, and output validation flow now lives in `backend/lambda/common/rag_service.py`, and both `/rag/query` and `/agent/run` call that same shared logic.

Current constraints in Phase 6A:

- `/agent/run` supports only `task: answer_question`
- `agentMode` is always `read_only`
- the only allowed tool call is `rag_query`
- write actions are intentionally out of scope

Successful `/agent/run` response shape:

```json
{
  "requestId": "<uuid>",
  "agentMode": "read_only",
  "task": "answer_question",
  "plan": [
    "Validate request",
    "Check input guardrail",
    "Check retrieval policy",
    "Run rag_query tool",
    "Validate output",
    "Return grounded answer"
  ],
  "toolCalls": [
    {
      "toolName": "rag_query",
      "status": "completed",
      "readOnly": true
    }
  ],
  "answer": "<grounded answer>",
  "sources": [
    {
      "documentId": "api-gateway-note",
      "chunkId": "chunk-0001",
      "title": "API Gateway Note",
      "chunkIndex": 0,
      "similarity": 0.82,
      "projectId": "learning",
      "customerId": "internal",
      "documentType": "technical-note"
    }
  ],
  "status": "completed"
}
```

Example request:

```bash
curl -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-learning" \
  -H "X-Allowed-Project-Ids: learning" \
  -H "X-Allowed-Customer-Ids: internal" \
  -d '{
    "task": "answer_question",
    "question": "What does API Gateway do?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }'
```

Future tools could include RCA draft generation or ticket draft creation, but any write-capable action should sit behind a stronger approval boundary than this learning-phase read-only skeleton.

## Phase 6B - Second Read-only Tool: trace_lookup

Phase 6B extends the read-only agent with a second explicit tool: `trace_lookup`. The agent now has two read-only tools:

- `rag_query`
- `trace_lookup`

`trace_lookup` lets the agent inspect platform behavior by `requestId` using the existing trace table. This is useful when you want the agent to explain why a previous request was blocked, why it returned `no_source`, or whether it completed successfully.

The tool stays intentionally small and read-only. It uses DynamoDB `GetItem` against the existing trace table and returns a compact inspection result plus a deterministic natural-language summary. It does not mutate state, call Bedrock, or introduce a new AWS service.

The `/agent/run` endpoint now supports:

- `task: answer_question`
- `task: inspect_trace`

Example trace inspection request:

```json
{
  "task": "inspect_trace",
  "requestId": "paste-request-id-here"
}
```

This keeps the agent useful for platform introspection without turning it into a write-capable automation system. Future tools can include RCA draft generation and ticket draft creation, but any write action should still require explicit human approval.

## Phase 6C - Third Read-only Tool: log_search

Phase 6C adds a third read-only tool: `log_search`. The agent now has three read-only tools:

- `rag_query`
- `trace_lookup`
- `log_search`

`log_search` lets the agent inspect recent runtime logs for the RAG path. This is useful for operational questions such as whether blocked requests have appeared recently, whether `no_source` traffic is increasing, or whether recent errors are visible in the backend log stream.

This learning PoC keeps the implementation intentionally simple. Inside Lambda, the tool uses the CloudWatch Logs `FilterLogEvents` API through boto3 and returns only a small summary plus a capped set of recent matching events. It does not use Logs Insights in the Lambda path and it does not return large raw log payloads.

Supported presets are:

- `raw`
- `blocked`
- `no_source`
- `errors`

Production systems should go further than this learning tool. In a more complete platform, prefer stronger IAM scoping for log access, plus Logs Insights, metrics, dashboards, alarms, and richer operational workflows.

## Phase 6D - Multi-tool Investigation Agent

Phase 6D builds on Phase 6C by chaining existing read-only tools instead of adding a new one. The new `investigate_recent_blocks` task runs a bounded multi-tool workflow:

- `log_search` with the `blocked` preset
- request-id extraction from recent log previews
- `trace_lookup` for up to three candidate request IDs

This makes the agent more useful for explaining recent blocked requests while keeping the workflow deterministic, bounded, and read-only. The agent does not call Bedrock for this task, does not write to external systems, and only uses its existing allowlisted inspection tools.

The workflow is intentionally small for a learning PoC. It searches a limited recent window, inspects at most three trace records, and returns a compact summary of blocked reasons when they can be determined.

In production, this kind of investigation flow should be paired with stronger incident workflows, dashboards, alarms, richer observability tooling, and explicit human approval before any write-capable follow-up action is introduced.

## Phase 6E - Human Approval Boundary for Write Actions

Phase 6E adds the first approval-gated action proposal flow. The earlier agent phases intentionally limited the toolset to read-only inspection and retrieval. That is the safe first step. Once an agent starts proposing actions that could lead to ticketing, email, or other operational workflows, it needs an explicit human approval boundary.

The new `propose_incident_report` task reuses the same bounded blocked-request investigation from Phase 6D, then builds a deterministic incident report proposal. It does not execute any external write action. Instead, it returns a `proposedAction` object with `requiresApproval: true` and `executionStatus: not_executed`.

This keeps the learning PoC clear about the boundary: the agent may prepare a draft, but a human must approve any write-capable next step before it happens.

Production systems could connect this approval boundary to ticketing systems, email workflows, or incident management tooling later, but the approval decision should stay explicit and auditable before those write actions are enabled.