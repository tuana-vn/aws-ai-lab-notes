# AWS AI Platform PoC

This repository contains a minimal AWS backend foundation for an AI platform, now extended through Phase 3A with a mini RAG flow built on DynamoDB document chunks and Amazon Bedrock inference.

## Why this foundation exists

This first step establishes the API, Lambda execution model, request tracing, and infrastructure boundaries before Amazon Bedrock is introduced. That keeps the Bedrock integration focused later on business capabilities such as `/chat`, `/rag/query`, and `/agent/run`, instead of mixing those concerns with initial platform plumbing.

Phase 2 adds only the smallest useful Bedrock capability: a `/chat` endpoint that sends one user message to the Bedrock Converse API, returns the model answer, records a short trace in DynamoDB, and logs the request lifecycle to CloudWatch.

Phase 3A adds a learning-focused mini RAG foundation. Documents are split into simple chunks and stored in DynamoDB. A `/rag/query` request scans those chunks, ranks them by keyword overlap, builds a grounded prompt, and asks Bedrock to answer only from the retrieved context.

## Target architecture

Client -> API Gateway -> Lambda -> DynamoDB -> CloudWatch Logs

Mini RAG flow:

Client -> API Gateway -> Documents Lambda -> DynamoDB DocumentChunks

Client -> API Gateway -> RagQuery Lambda -> DynamoDB DocumentChunks -> Bedrock Converse API -> DynamoDB Trace -> CloudWatch Logs

## Project structure

```text
aws-ai-platform-poc/
  README.md
  backend/
    lambda/
      common/
        bedrock_client.py
        chunking.py
        document_repository.py
        response.py
        logging.py
        retrieval.py
        trace_repository.py
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
  test-data/
    requests/
      chat-request.json
      document-request.json
      echo-request.json
      rag-query-request.json
```

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

### POST /rag/query

Request body:

```json
{
  "question": "What does API Gateway do?"
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
      "chunkIndex": 0
    }
  ],
  "modelId": "apac.amazon.nova-lite-v1:0",
  "status": "completed"
}
```

When no relevant chunks are found, `/rag/query` returns `I do not know based on the available documents.` with an empty `sources` array. This keeps the first RAG iteration explicit and grounded instead of guessing.

## Design notes

- `requestId` is generated inside the Lambda so each request can be correlated across API responses, DynamoDB trace records, and CloudWatch logs.
- DynamoDB trace storage gives a simple, durable request audit trail that is useful for debugging and operational visibility while the platform is still small.
- The Echo Lambda is granted only `dynamodb:PutItem` on the single trace table because IAM policies should stay least-privilege from the beginning.
- The Chat Lambda uses the Bedrock Runtime Converse API with a model ID from `BEDROCK_MODEL_ID`, defaulting to `amazon.nova-lite-v1:0` for a simple first integration.
- The chat trace stores only `answer_preview` instead of the full answer so the trace table stays lightweight and avoids persisting long model outputs by default.
- Phase 3A is a mini RAG because retrieval is still backend-managed and keyword-based. It grounds answers with retrieved chunks, but it does not yet use embeddings, vector search, hybrid retrieval, reranking, or Bedrock Knowledge Bases.
- Keyword retrieval is the right first step for learning because the logic is visible and easy to debug before moving to more capable retrieval approaches.
- DynamoDB Scan is acceptable here only because this is a learning PoC. Production retrieval should use better indexing, metadata filters, vector search, or managed knowledge services.
- The code intentionally avoids extra frameworks so the Lambda and SAM patterns remain easy to learn and easy to extend.

## Required AWS permissions

To deploy and run Phase 2, the environment needs permission for:

- CloudFormation and SAM deployment operations
- Lambda create, update, and invoke permissions
- API Gateway deployment permissions
- DynamoDB table creation and `dynamodb:PutItem`
- DynamoDB `dynamodb:Scan` on the document chunk table for the learning retrieval flow
- Bedrock runtime access, including `bedrock:InvokeModel` and `bedrock:Converse`

The SAM template keeps DynamoDB write access least-privilege. Bedrock access uses `Resource: "*"` in this PoC because model ARN scoping varies by setup; production should narrow that policy to approved model resources.

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

## How to test /rag/query

Use `test-data/requests/rag-query-request.json` after indexing at least one document.

```bash
curl -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -d @test-data/requests/rag-query-request.json
```

## Future Phase 3B

The next RAG step should add embeddings and vector search or move retrieval to Bedrock Knowledge Bases. That is the point where retrieval quality, metadata filtering, and scale should improve beyond this learning-oriented keyword baseline.

## Local test payload

Use `test-data/requests/echo-request.json` as a sample request body for `POST /echo`.
Use `test-data/requests/chat-request.json` as a sample request body for `POST /chat`.
Use `test-data/requests/document-request.json` as a sample request body for `POST /documents`.
Use `test-data/requests/rag-query-request.json` as a sample request body for `POST /rag/query`.

## Phase 2 Note

In ap-southeast-1, direct on-demand invocation of amazon.nova-lite-v1:0 was not supported.
The PoC uses the inference profile ID:
    apac.amazon.nova-lite-v1:0