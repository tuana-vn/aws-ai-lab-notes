# ADR: RAG Production Architecture Decision

## Title

Proposed retrieval upgrade direction for moving beyond the current mini RAG baseline

## Status

Proposed

## Context

The current repository implements a learning-focused mini RAG architecture with the following characteristics:

- documents are chunked and stored in DynamoDB with embeddings
- `/rag/query` applies input guardrails, the backend policy gate, metadata filtering, query embedding, DynamoDB scan, in-Lambda similarity ranking, a similarity threshold, grounded Bedrock generation, output guardrails, traces, and structured logs
- `/agent/run` reuses the same RAG path only for `task: answer_question`
- observability and token-usage evidence have improved through Phase 9 and Phase 10B

This architecture is useful for learning and evidence-driven design discussion, but it is not the long-term production-scale retrieval path.

## Decision Drivers

- preserve the backend policy gate before retrieval
- preserve metadata compatibility for `projectId`, `customerId`, and `documentType`
- preserve grounded-answer behavior and `no_source` behavior
- improve scalability beyond DynamoDB scan plus in-Lambda ranking
- preserve or improve evidence quality, evaluation comparability, and observability
- keep migration risk controlled rather than replacing the current path abruptly

## Options Considered

### Option 1: Current mini RAG

The current mini RAG remains the existing implemented path.

Benefits:

- easiest to understand and inspect in code
- strongest current baseline for regression and evidence comparison
- no migration effort if left unchanged

Limitations:

- not the production-scale retrieval path
- poor long-term scalability fit compared with more production-oriented retrieval architectures

### Option 2: Bedrock Knowledge Bases

This option would move toward a more managed AWS-native retrieval architecture.

Benefits:

- strong AWS-native fit
- practical candidate for a PoC-to-enterprise progression discussion
- may reduce some custom retrieval burden compared with the current path

Limitations:

- retrieval behavior is more managed, so fine-grained control must be validated carefully
- policy gate compatibility, evidence behavior, and observability need explicit validation before implementation

### Option 3: OpenSearch vector index / custom retrieval

This option would move toward a more explicitly controlled retrieval architecture built around a vector index and custom retrieval behavior.

Benefits:

- deeper retrieval control
- stronger flexibility for ranking, filtering, and retrieval behavior
- potentially better fit for teams that want lower lock-in and more retrieval tuning freedom

Limitations:

- more operational complexity
- larger migration surface
- stronger need for explicit observability, ranking, and evidence design

## Proposed Recommendation

For AWS-native PoC-to-enterprise discussion, Bedrock Knowledge Bases is the strongest first production-oriented candidate.

For deeper retrieval control, custom ranking, and more control over retrieval behavior, OpenSearch or another custom retrieval path remains a valid option.

The current mini RAG should remain as a learning baseline and regression reference, not as the production-scale retrieval path.

## Why

This recommendation is cautious because the evidence in the repository supports a direction, not a final production decision.

Why this recommendation is reasonable:

- the current mini RAG already proves the policy, guardrail, grounding, and observability boundaries that should survive migration
- Bedrock Knowledge Bases is a practical first candidate when staying close to the current AWS-native platform matters most
- OpenSearch or custom retrieval stays valid where retrieval control matters more than a more managed AWS path
- preserving the current mini RAG as a baseline lowers migration risk and keeps evaluation comparison possible

## Consequences

If this recommendation is followed:

- the current mini RAG stays in the repository during migration planning
- the first experimental retrieval path should be introduced beside the existing path, not as an immediate replacement
- backend authorization and policy enforcement must remain explicit before retrieval
- the team will need comparison evidence before any cutover decision

## What Remains Unchanged

These principles should remain unchanged regardless of which retrieval option is later implemented:

- the backend policy gate remains before retrieval
- metadata filtering does not become the only security boundary
- invalid scope should still be denied before retrieval work continues
- `no_source` should remain a real outcome when evidence is insufficient
- traces, logs, and evaluation should remain part of the retrieval story

## What Must Be Validated Before Implementation

Before implementing either upgrade option, validate:

- metadata contract compatibility
- backend policy gate placement and denial behavior
- evidence and citation quality versus the current baseline
- latency and token-usage impact versus the current baseline
- observability compatibility
- rollback approach and side-by-side comparison plan

## What Is Explicitly Out Of Scope

This ADR does not:

- implement Bedrock Knowledge Bases
- implement OpenSearch
- declare a final production decision
- remove the current mini RAG
- claim production readiness

## Current Implementation Boundary

Current implementation remains the DynamoDB-based mini RAG in the repository today.

## Future Roadmap Boundary

Future roadmap includes experimental retrieval migration work and a later cutover decision only after validation evidence exists.