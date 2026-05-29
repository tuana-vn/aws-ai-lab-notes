# Phase 10H Document Replacement Implementation Plan

## Purpose

This document turns the Phase 10G safer document replacement design into a practical implementation blueprint for a later coding phase.

The goal is to describe a realistic sequence of implementation slices without claiming that any of those runtime changes already exist.

## Current Baseline

The current `/documents` path still:

- validates the request
- chunks document content
- generates embeddings
- deletes existing chunks for the same `documentId`
- saves the replacement chunk set into the current DynamoDB-backed mini RAG store

`/rag/query` still retrieves from that current chunk store.

## Why This Is Still Documentation-only

Phase 10H does not change runtime behavior. It exists so a later implementation phase can be scoped cleanly before code, data-model, and retrieval changes begin.

That matters because safer replacement will affect:

- ingestion logic
- chunk storage shape
- retrieval filtering rules
- cleanup behavior
- test coverage
- migration or backfill planning for existing chunk data

## Implementation Goals

The later implementation should aim to:

- preserve old active content until replacement content is fully ready
- make replacement idempotent enough to classify replay versus real change
- keep the current mini RAG baseline understandable while improving replacement safety
- keep retrieval behavior stable during the transition
- allow cleanup only after cutover succeeds

## Proposed Implementation Slices

### H1: Introduce Version Metadata Model

- Objective: define the minimum version-aware metadata needed to distinguish active, staged, obsolete, and failed document versions.
- Files likely affected: `backend/lambda/documents/handler.py`, `backend/lambda/common/document_repository.py`, retrieval-related repository or filtering helpers, future tests.
- Data model impact: adds version-related fields and document-version state concepts.
- Behavior impact: ingestion stops treating all writes for a `documentId` as one undifferentiated replacement event.
- Risk: medium because identity and retrieval assumptions start to change.
- Validation: unit tests for metadata construction and retrieval filtering assumptions.

### H2: Add Staged Chunk Write Path

- Objective: save replacement chunks as staged data before they are visible as the active version.
- Files likely affected: `backend/lambda/documents/handler.py`, `backend/lambda/common/document_repository.py`.
- Data model impact: staged chunk writes must be distinguishable from active chunks.
- Behavior impact: old active chunks remain intact while the new candidate is still being built.
- Risk: high because this is the main replacement-safety shift.
- Validation: failure-injection tests for partial staged writes and embedding failures.

### H3: Add Active Version Pointer Concept

- Objective: create a single authoritative record or condition that identifies which version retrieval should treat as active.
- Files likely affected: document repository, retrieval helpers, future version-state helpers.
- Data model impact: introduces active-version state and conditional cutover logic.
- Behavior impact: retrieval and cleanup no longer infer activeness from raw chunk presence alone.
- Risk: high because cutover correctness matters.
- Validation: tests confirming only the active version is used after cutover.

### H4: Update Retrieval To Use Only Active Version

- Objective: make retrieval ignore staged and obsolete versions during normal query handling.
- Files likely affected: `backend/lambda/common/rag_service.py`, `backend/lambda/common/document_repository.py`, future tests.
- Data model impact: retrieval access patterns become version-aware.
- Behavior impact: `/rag/query` stops depending on a single unversioned chunk set.
- Risk: high because retrieval regressions are user-visible.
- Validation: RAG regression tests proving old versions remain available until activation and only the active version is retrieved after cutover.

### H5: Add Idempotency Handling

- Objective: classify same-content replay, repeated request replay, and new-content replacement separately.
- Files likely affected: document handler, document repository, future request-state or version-state helpers.
- Data model impact: may add `contentHash`, request correlation, or idempotency key support.
- Behavior impact: the system can avoid unnecessary replacement work for exact replay.
- Risk: medium because duplicate classification rules must be explicit.
- Validation: tests for same-content replay, client retry, and conflicting replacement attempts.

### H6: Add Cleanup Strategy For Obsolete Versions

- Objective: remove obsolete chunk sets only after activation and rollback windows are satisfied.
- Files likely affected: document repository, future cleanup helpers, future operational scripts.
- Data model impact: obsolete state and cleanup timing become explicit.
- Behavior impact: deletion moves from pre-replacement to post-cutover cleanup.
- Risk: medium because cleanup mistakes can remove rollback safety.
- Validation: tests that obsolete cleanup does not remove the active version.

### H7: Add Migration / Backfill Strategy For Existing Chunks

- Objective: define how the current unversioned chunk records become compatible with the future version-aware model.
- Files likely affected: future migration scripts or repository helpers, future docs, future evidence workflow.
- Data model impact: existing chunk data needs a default active-version interpretation.
- Behavior impact: migration should not break current retrieval or require immediate reingestion of everything.
- Risk: medium to high depending on migration path chosen.
- Validation: migration and backfill tests against representative current chunk records.

### H8: Add Tests And Evidence Workflow

- Objective: define the minimum test and evidence workflow needed to prove safer replacement works.
- Files likely affected: future unit and integration tests, future evaluation docs or evidence pack updates.
- Data model impact: none directly, but tests must understand version state.
- Behavior impact: creates the proof that staged replacement and active cutover behave correctly.
- Risk: low if done after core behavior is stable.
- Validation: test plan execution and evidence capture.

## Recommended Implementation Order

1. H1 introduce version metadata model
2. H2 add staged chunk write path
3. H3 add active version pointer concept
4. H4 update retrieval to use only active version
5. H5 add idempotency handling
6. H6 add cleanup strategy for obsolete versions
7. H7 add migration and backfill strategy
8. H8 add tests and evidence workflow

## Acceptance Criteria

Phase 10H is acceptable when:

- the plan maps the safer replacement design into concrete implementation slices
- each slice identifies likely files, behavior impact, and risk
- retrieval impact is treated as a first-class implementation concern
- the plan stays honest about what is not implemented yet
- current implementation is clearly separated from future implementation

## Current Implementation Boundary

Current implementation still uses delete-then-save replacement in `/documents` and current chunk retrieval in the mini RAG baseline.

Phase 10I adds version-related metadata fields to ingestion records and logs, but it does not implement staged replacement, active version pointers, or cutover logic.

## Future Implementation Boundary

Future implementation may add version metadata, staged chunk writes, active version selection, idempotency handling, delayed cleanup, and migration logic without discarding the current mini RAG learning baseline abruptly.