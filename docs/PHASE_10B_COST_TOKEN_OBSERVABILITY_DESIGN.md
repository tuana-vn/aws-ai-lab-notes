# Phase 10B Cost and Token Usage Observability Design

## Purpose

This document defines the first practical cost and token usage observability slice for the current `aws-ai-platform-poc` repository.

The goal of Phase 10B is not to produce a production-grade cost dashboard or to estimate USD cost from guessed prices. The goal is to identify which Bedrock-backed flows exist, what Bedrock usage data is actually available from the current runtime, what can be logged safely, and what is still missing before cost estimation becomes credible.

## Current Baseline

The current PoC baseline includes:

- API Gateway, Lambda, DynamoDB, CloudWatch Logs, Bedrock Runtime, Cognito, and SAM / CloudFormation
- a basic CloudWatch dashboard and runbook from Phase 9C
- `/chat` as a Bedrock-backed smoke-test endpoint
- `/rag/query` as the controlled grounded-answer path
- `/agent/run` as a bounded agent path that may call the shared RAG flow for `answer_question`
- structured logging and trace records for the main chat, RAG, and agent flows

The repository is still a PoC and is not production-ready.

## Bedrock-backed Flows In The Current PoC

### Generation flows

The following flows call Bedrock generation through `BedrockClient.converse()`:

- `POST /chat`
- `POST /rag/query` when valid grounded sources exist
- `POST /agent/run` only when the task is `answer_question`, because that task reuses the shared RAG generation path

### Embedding flows

The following flows call the embedding model through `EmbeddingClient`:

- `POST /documents` for chunk embeddings during ingestion
- `POST /rag/query` for question embeddings during retrieval
- `POST /agent/run` only when the task is `answer_question`, because that task reuses the shared RAG retrieval path

## What Should Be Measured

For Bedrock generation, the minimum useful observability set is:

- which route invoked generation
- which model ID was used
- actual input token count when returned by Bedrock
- actual output token count when returned by Bedrock
- actual total token count when returned by Bedrock
- Bedrock latency when returned by Bedrock
- whether a request path reached generation at all

For embedding activity, the first useful observability set is smaller:

- which embedding model is used
- whether the repository can safely capture request volume or latency without logging content
- whether the embedding response exposes usage-like fields that the current code can trust

## What Can Be Measured Today

Based on current code inspection and the Bedrock Converse response shape:

- `BedrockClient.converse()` can now safely preserve the Bedrock `usage` object when present
- the Converse response shape includes:
  - `usage.inputTokens`
  - `usage.outputTokens`
  - `usage.totalTokens`
  - `metrics.latencyMs`
- Phase 10B now propagates those generation fields into `/chat` and `/rag/query` trace/log records when generation actually occurs
- `scripts/query_logs.py` now includes a `cost-tokens` preset for runtime logs that carry those fields

Additional current facts that can already be observed from code:

- blocked input does not call Bedrock generation because the input guardrail returns before retrieval and generation
- `no_source` does not call Bedrock generation because the RAG path returns before `BedrockClient.converse()` when no eligible grounded chunks qualify
- `/agent/run` does not call Bedrock for non-generation tasks such as `inspect_trace`, `search_logs`, `investigate_recent_blocks`, or `propose_incident_report`

## What Cannot Be Measured Today

The current repository still cannot credibly answer all cost questions.

It does not currently provide:

- verified embedding token usage fields from the embedding model response path
- any pricing configuration source inside the application
- any USD cost calculation model
- any production-grade cost dashboard
- any billing reconciliation workflow

For embeddings specifically:

- the current code reads the response body for vectors only
- the current repository does not verify any token-like embedding usage field from that response path
- this means embedding token counts should be treated as unavailable in the current implementation unless a later phase validates a trusted source for them

## Actual Token Usage Versus Estimated Cost

These are different categories and should stay separate.

Actual token usage means counts returned by the Bedrock generation response itself.

Estimated cost means a pricing calculation derived from:

- pricing rules for the exact model or inference profile
- pricing version and source
- input versus output pricing distinctions when applicable
- any regional or service-tier differences that materially affect price

Phase 10B only introduces actual generation usage observability where the runtime already exposes it. It does not estimate price.

## Why USD Cost Should Not Be Estimated Without Pricing Config

USD cost should not be guessed from token counts alone.

The repository currently lacks:

- a versioned pricing source
- model-specific pricing configuration
- region-aware pricing treatment
- an explicit policy for how cost estimates should be reviewed and trusted

Without that, a cost number would look precise while being operationally unreliable. That is worse than leaving the cost field empty.

## Bedrock Usage Availability Finding

### Generation usage

Confirmed available from the Bedrock Converse response shape:

- `usage.inputTokens`
- `usage.outputTokens`
- `usage.totalTokens`
- `metrics.latencyMs`

Current Phase 10B runtime behavior:

- extracts those fields when present
- does not fail the request if they are missing
- does not change answer behavior
- does not log prompts, retrieved chunk text, raw document text, full answers, secrets, or JWTs for token tracking

### Embedding usage

Not confirmed from the current repository implementation.

Current Phase 10B position:

- embedding token usage remains undocumented as an actual measured field
- embedding cost estimation remains deferred

## Minimal Implementation Approach

The minimal low-risk implementation for this phase is:

1. preserve the Bedrock Converse response usage and latency fields at the `BedrockClient` boundary
2. add those fields to `/chat` success trace/log records
3. add those fields to `/rag/query` success trace/log records only when generation happens
4. leave blocked and `no_source` flows without generation token fields
5. add a `cost-tokens` Logs Insights preset only because runtime token fields now exist

This keeps the change small and avoids introducing pricing logic or behavior changes.

## Logging And Trace Fields

Current Phase 10B runtime fields emitted when generation usage is available:

- `modelId`
- `inputTokens`
- `outputTokens`
- `totalTokens`
- `bedrockLatencyMs`

Existing compatibility fields remain relevant as well:

- `request_id`
- `path`
- `status`
- `latency_ms`
- `model_id`

This means the current repository will temporarily contain a mix of older snake_case runtime fields and newer camelCase Bedrock usage fields. That is acceptable for this first pass as long as queries and docs describe the distinction clearly.

## Dashboard And Runbook Ideas

Useful first-step operator views for cost and token usage are:

- recent `/chat` generation requests with token counts
- recent `/rag/query` generation requests with token counts
- top high-token requests by total token count
- grouped comparison of `/chat` versus `/rag/query`
- evidence showing that blocked requests do not emit generation usage fields
- evidence showing that `no_source` requests do not emit generation usage fields

These views are for operational inspection only in this phase. They are not a production-grade cost dashboard.

## Known Limitations

- no USD cost estimation is implemented
- no pricing config exists in the repository
- embedding usage is not confirmed from the current code path
- agent flows only surface generation usage indirectly through the shared RAG path
- blocked and `no_source` paths can prove Bedrock generation was skipped only by the absence of generation usage fields and by code-path inspection, not by a dedicated billing event
- the repository is still a PoC and is not production-ready

## Acceptance Criteria

Phase 10B is acceptable when:

- the design clearly identifies which flows call Bedrock generation and embeddings
- the design clearly separates actual usage from estimated cost
- generation usage fields are documented only where verified
- no invented token counts or cost numbers appear in docs or code
- blocked and `no_source` generation behavior is explained accurately
- the runtime implementation, if present, remains low-risk and does not change request behavior

## Future Roadmap

Future work beyond this phase can include:

- validated embedding usage observability if the model response or another trusted source supports it
- pricing configuration and versioning only after a trustworthy source is chosen
- explicit cost estimation fields only after pricing config exists
- dashboard improvements after enough real runtime data exists
- alarming only after stable baseline behavior is understood

These are roadmap items only. They are not implemented by this document.