# Cost and Token Trace Schema

## Purpose

This document defines the recommended schema for Phase 10B cost and token observability fields.

It separates actual Bedrock usage from optional future cost-estimate fields. Actual usage fields may be populated only when the runtime receives them from a trusted Bedrock response. Estimated cost fields must remain empty unless an explicit pricing configuration source exists.

## Common Fields

| Field | Meaning | Notes |
| --- | --- | --- |
| `requestId` | Normalized request identifier | Preferred normalized form when new structured events are created. |
| `request_id` | Compatibility request identifier | Current repository compatibility field used in traces and logs today. |
| `path` | API route path | For example `/chat` or `/rag/query`. |
| `routeCategory` | High-level route group | Suggested values include `chat`, `rag`, `documents`, or `agent`. |
| `operationType` | Logical operation | Suggested values include `generation`, `embedding`, or `token_observability`. |
| `status` | Request or operation status | For example `completed`, `blocked`, `no_source`, `failed`, or `indexed`. |
| `modelId` | Bedrock generation model identifier | Populate only for generation events or traces. |
| `timestamp` | UTC timestamp for the event or trace | ISO 8601 string recommended. |

## Request ID Compatibility Note

The repository currently uses `request_id` widely in trace and log records. Newer normalized schemas prefer `requestId`.

Recommended rule:

- keep `request_id` compatibility where existing flows depend on it
- use `requestId` in design-forward schemas and future normalized events
- query layers should support both during migration

## Generation Usage Fields

These fields represent actual Bedrock generation usage and should only be populated from the Bedrock generation response itself.

| Field | Meaning | Population rule |
| --- | --- | --- |
| `inputTokens` | Input token count returned by Bedrock | Populate only when returned by Bedrock `Converse`. |
| `outputTokens` | Output token count returned by Bedrock | Populate only when returned by Bedrock `Converse`. |
| `totalTokens` | Total token count returned by Bedrock | Populate only when returned by Bedrock `Converse`. |
| `bedrockLatencyMs` | Model latency returned by Bedrock | Populate only when returned by Bedrock `metrics.latencyMs`. |

Rules:

- do not infer token values from prompt length or character count
- do not invent missing Bedrock usage fields
- absence of these fields is acceptable when Bedrock does not return them or when generation did not happen

## Embedding Usage And Volume Fields

Embedding usage is less mature in the current repository. These fields are recommended, but they should be populated only when a trusted implementation path exists.

| Field | Meaning | Population rule |
| --- | --- | --- |
| `embeddingModelId` | Embedding model identifier | Populate when the embedding model is known for the operation. |
| `embeddingInputTextCount` | Number of texts sent to the embedding call | Safe volume metric when available from the application path. |
| `embeddingInputCharCount` | Character count of embedding input text | Safe volume metric when available from the application path. |
| `embeddingVectorCount` | Number of vectors returned or produced | Safe output volume metric when available from the application path. |
| `embeddingLatencyMs` | Embedding call latency | Populate only when the runtime measures it safely. |

Rules:

- do not treat character count as token count
- do not treat vector count as billing usage
- only populate embedding token-like fields when a trusted response shape is verified

## Cost-estimate Fields

These fields are reserved for a future phase. They must remain unpopulated unless pricing configuration exists.

| Field | Meaning | Population rule |
| --- | --- | --- |
| `costEstimated` | Whether any estimate was computed | Only `true` when all required pricing inputs are configured and trusted. |
| `estimatedInputCostUsd` | Estimated USD cost for input usage | Only populate from trusted pricing config. |
| `estimatedOutputCostUsd` | Estimated USD cost for output usage | Only populate from trusted pricing config. |
| `estimatedTotalCostUsd` | Estimated total USD cost | Only populate from trusted pricing config. |
| `pricingSource` | Pricing source identifier | For example a config file, pricing table version, or approved pricing document reference. |
| `pricingVersion` | Version of the applied pricing data | Required if any estimate is emitted. |
| `currency` | Currency code | Required if any estimate is emitted. |

Rules:

- estimated cost fields must only be populated when pricing config exists
- do not hardcode model pricing in runtime code for this phase
- do not present estimated cost as actual billed cost

## Sensitive Data Exclusion Rules

The following must not be logged for token or cost tracking:

- prompt text
- retrieved chunk text
- raw document text
- full answer text
- secrets
- passwords
- raw JWTs
- any other sensitive token or credential material

Safe observability should focus on metadata, usage counts, latency, and status rather than content.

## Current Implementation Boundary

Current Phase 10B implementation supports generation usage fields from Bedrock `Converse` when available.

Embedding token usage and cost estimation remain future work.