# AWS AI Platform PoC

This repository contains a minimal AWS backend foundation for an AI platform, now extended through Phase 3D with a mini RAG flow that stores document embeddings in DynamoDB, filters weak matches with a similarity threshold, and performs grounded Amazon Bedrock inference only when retrieval is strong enough.

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
        bedrock_client.py
        chunking.py
        document_repository.py
        embedding_client.py
        response.py
        logging.py
        retrieval.py
        trace_repository.py
        vector_math.py
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

`/documents` now generates an embedding for each chunk with the Bedrock model in `EMBEDDING_MODEL_ID`, defaulting to `cohere.embed-english-v3`, then stores both the chunk text and embedding in DynamoDB.

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
      "chunkIndex": 0,
      "similarity": 0.82
    }
  ],
  "modelId": "apac.amazon.nova-lite-v1:0",
  "embeddingModelId": "cohere.embed-english-v3",
  "status": "completed"
}
```

When no similar chunks are found, `/rag/query` returns `I do not know based on the available documents.` with an empty `sources` array and a `no_source` status. This keeps the RAG flow explicit and grounded instead of guessing.

`/rag/query` now generates a query embedding, scans document chunks from DynamoDB, calculates cosine similarity against each stored embedding, keeps only chunks with similarity greater than or equal to `MIN_SIMILARITY_SCORE`, selects the top 3 remaining chunks, and only then calls Bedrock Converse for answer generation.

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

## Local test payload

Use `test-data/requests/echo-request.json` as a sample request body for `POST /echo`.
Use `test-data/requests/chat-request.json` as a sample request body for `POST /chat`.
Use `test-data/requests/document-request.json` as a sample request body for `POST /documents`.
Use `test-data/requests/rag-query-request.json` as a sample request body for `POST /rag/query`.
Use `test-data/rag-evaluation/questions.json` with `scripts/run_rag_eval.py` for the Phase 3C local RAG evaluation flow.

## Phase 2 Note

In ap-southeast-1, direct on-demand invocation of amazon.nova-lite-v1:0 was not supported.
The PoC uses the inference profile ID:
    apac.amazon.nova-lite-v1:0