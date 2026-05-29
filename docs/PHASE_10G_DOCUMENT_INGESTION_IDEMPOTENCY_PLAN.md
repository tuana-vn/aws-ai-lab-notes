# Phase 10G Document Ingestion Idempotency Plan

## Purpose

This document defines a practical plan for making document ingestion safer and more idempotent in the current `aws-ai-platform-poc` repository.

The goal is not to redesign the whole retrieval system immediately. The goal is to define the next hardening slice for `/documents` so document replacement becomes safer than the current delete-then-save flow.

## Current Baseline

The current repository baseline for `/documents` is:

- request validation for `documentId`, `title`, `content`, and optional metadata
- content chunking in Lambda
- embedding generation for each chunk
- deletion of existing chunks for the same `documentId`
- saving the new chunk set into the current DynamoDB-backed mini RAG store

This behavior is useful for learning because it is easy to follow in code and keeps the current mini RAG ingestion path simple.

## Current Ingestion Risk

The current replacement shape is risky for production because the handler deletes old chunks before saving the new chunk set.

If deletion succeeds and replacement fails before all new chunks are written, retrieval can:

- lose valid document evidence entirely
- see a partial chunk set for the document
- produce inconsistent RAG behavior until another ingestion attempt repairs the state

## Why Document Ingestion Idempotency Matters

Document ingestion idempotency matters because `/rag/query` depends on these chunk records as the current retrieval corpus.

If ingestion is not replay-safe and replacement-safe, the platform can lose or corrupt the evidence base that retrieval depends on. This matters even in a learning-oriented mini RAG because reliability failures in ingestion become retrieval failures later.

## What This Phase Does Not Implement

This phase does not implement:

- application code changes
- DynamoDB schema changes
- document versioning in the live code path
- active version pointers
- staged chunk writes in the runtime
- new AWS resources
- production ingestion workflow changes

## Recommended Hardening Goals

The Phase 10G goals are:

- preserve old chunks until replacement chunks are fully ready
- make duplicate ingestion easier to detect and classify
- distinguish same-content replay from real replacement
- reduce the chance that partial failure damages retrieval state
- define an upgrade path that still fits the current learning baseline and future retrieval migration options

## Proposed Target Behavior

The target behavior should be:

1. accept a replacement request without immediately deleting the current active chunk set
2. generate a staged replacement version first
3. validate that the staged chunk set is complete enough to promote
4. cut over to the new version only after the staged version is fully ready
5. keep the old version available until cutover succeeds
6. clean up old versions later instead of deleting them up front

This is the core design shift for safer replacement.

## Priority Recommendations

### P0

- stop treating delete-then-save as the long-term replacement model
- define a staged replacement flow that preserves old chunks until the new chunk set is ready
- define the minimum document identity model needed for safe replacement

### P1

- define duplicate-ingestion handling for same content versus new content with the same `documentId`
- define a practical idempotency-key strategy for future implementation
- define cleanup rules for obsolete versions after cutover succeeds

### P2

- evaluate how this design should evolve if the retrieval backend later moves to Bedrock Knowledge Bases or OpenSearch
- refine operator tooling for version inspection and failed-ingestion investigation

## Suggested Future Implementation Order

1. define the target document identity model and version metadata
2. define staged chunk write behavior and cutover rules
3. define duplicate-ingestion handling and idempotency-key options
4. define cleanup behavior for obsolete versions
5. implement the safer replacement flow in a later phase

## Acceptance Criteria

Phase 10G is acceptable when:

- the current `/documents` behavior is described honestly as useful for learning but risky for production replacement
- the design clearly states that old chunks should remain available until the new chunk set is fully ready
- the target behavior distinguishes current implementation from future implementation
- the design stays practical and backend-architect friendly
- the phase does not claim safer replacement is already implemented

## Current Implementation Boundary

Current implementation means `/documents` still uses the simple mini RAG ingestion path with delete-then-save replacement in the live code path.

## Future Roadmap Boundary

Future roadmap means staged replacement, explicit version metadata, safer cutover, and delayed cleanup of obsolete document versions.