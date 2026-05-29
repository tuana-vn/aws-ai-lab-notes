# RAG Migration Plan From Mini RAG

## Purpose

This document describes a phased migration plan for moving from the current mini RAG baseline toward a more production-oriented retrieval architecture.

The plan is intentionally conservative. It preserves the current repository behavior as the baseline, keeps evaluation and observability intact for comparison, and treats any new retrieval path as experimental until evidence supports a cutover decision.

## Phase M1 - Preserve Current Mini RAG Baseline

### Objective

Keep the current `/documents` and `/rag/query` behavior as the baseline reference.

### Actions

- keep current ingestion behavior intact
- keep current retrieval, policy, guardrail, and grounding behavior intact
- keep current evaluation cases available for comparison
- keep current trace, log, and token-observability fields available for side-by-side evidence

### Why This Matters

Without a stable baseline, later retrieval comparisons become ambiguous.

## Phase M2 - Define Document Source And Metadata Contract

### Objective

Define the metadata and source-document contract that any future retrieval path must preserve.

### Required fields

- `projectId`
- `customerId`
- `documentType`
- `documentId`
- `version`
- `sourceUri`
- `ingestionTimestamp`
- `classification` or `sensitivity` if needed later

### Why This Matters

Migration is safer when metadata expectations are explicit rather than implicit in the current chunk format.

## Phase M3 - Prototype Bedrock Knowledge Bases Path Or OpenSearch Path

### Objective

Introduce an experimental retrieval path without replacing the current `/rag/query` immediately.

### Actions

- create a separate experimental route or feature flag
- do not replace the current `/rag/query` path on the first pass
- do not weaken the existing policy gate, input guardrail, output guardrail, or traceability expectations

### Why This Matters

Side-by-side comparison is safer than immediate cutover.

## Phase M4 - Preserve Policy Gate Before Retrieval

### Objective

Keep authorization logic explicit and independent from retrieval metadata.

### Rules

- `AccessContext` remains the authority for allowed project and customer scope
- metadata filters must not become the only security boundary
- invalid `projectId` or `customerId` scope must still return access denied before retrieval proceeds

### Why This Matters

Metadata filtering improves retrieval relevance. It is not a replacement for backend authorization.

## Phase M5 - Preserve No-source Behavior And Grounding

### Objective

Preserve the current evidence-driven answer discipline.

### Rules

- no source means no generated answer
- weak retrieval should not be sent to Bedrock generation
- citations and evidence behavior must be preserved or improved

### Why This Matters

The current PoC already uses `no_source` as a meaningful control point. Migration should not weaken that boundary.

## Phase M6 - Evaluation And Comparison

### Objective

Compare the current mini RAG against the experimental retrieval path using shared evidence and metrics.

### Comparison areas

- source quality
- latency
- token usage
- `no_source` rate
- denied rate
- cost signals when available

### Actions

- keep evidence screenshots and query output for review
- compare evaluation outcomes between the baseline and the experimental path
- preserve operator-visible logs and traces for both paths when feasible

### Why This Matters

Migration should be evidence-driven rather than preference-driven.

## Phase M7 - Cutover Decision

### Objective

Choose whether to replace mini RAG, run side-by-side, or keep mini RAG for learning only.

### Decision questions

- does the new retrieval path improve scalability meaningfully
- does it preserve policy and grounding behavior
- does it preserve or improve evidence quality
- is rollback clear and practical
- is operational ownership clear

### Actions

- define rollback before cutover
- define owner and acceptance criteria
- decide whether the mini RAG remains a learning-only reference implementation

## Migration Risks

- policy-gate weakening if metadata filtering is mistaken for authorization
- loss of current `no_source` behavior discipline
- weaker evidence or citation quality than the current baseline
- harder evaluation comparison if the baseline path is replaced too early
- increased operational complexity without enough retrieval benefit

## Rollback Approach

The rollback approach should be simple:

- keep the current mini RAG path available until the new retrieval path is validated
- prefer a separate route or feature flag during experimentation
- do not remove the current baseline until cutover evidence is accepted
- define who can approve rollback and under what conditions

## Evidence To Capture

Capture evidence across both the baseline and experimental path for:

- denied requests
- blocked requests
- `no_source` outcomes
- grounded answers with citations or source evidence
- latency trends
- token-usage comparison where available
- operator log and dashboard views relevant to retrieval behavior

## Acceptance Criteria

The migration plan is acceptable when:

- the current baseline remains clearly defined
- the migration path preserves backend authorization before retrieval
- `no_source` and grounding behavior remain explicit requirements
- comparison evidence is required before cutover
- rollback is defined before replacement

## Current Implementation Boundary

Current implementation remains:

- DynamoDB-backed chunk and embedding storage
- metadata filtering and backend policy gate in application code
- in-Lambda ranking and similarity threshold enforcement
- grounded Bedrock generation only when valid sources exist

## Future Roadmap Boundary

Future roadmap includes:

- an experimental Bedrock Knowledge Bases path or OpenSearch/custom retrieval path
- side-by-side retrieval comparison
- eventual cutover or permanent learning-only retention of the mini RAG baseline

These are roadmap steps only. They are not implemented by this document.