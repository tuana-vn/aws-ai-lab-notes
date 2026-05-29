# Document Ingestion Data Model Proposal

## Purpose

This document proposes practical data-model options for implementing safer document replacement in the current `aws-ai-platform-poc` repository.

It does not claim that any of these fields, tables, or access patterns already exist in the current runtime.

## Current Chunk Model Summary

The current chunk model is simple:

- chunk records are stored in `DocumentChunksTable`
- records are keyed by `document_id` and `chunk_id`
- chunk metadata includes title, content, embedding, project, customer, document type, and created timestamp
- there is no explicit document version state
- there is no active version record

This is easy to understand, but it does not support safer staged replacement.

## Target Model Option A: Reuse Existing DocumentChunksTable With Added Version Fields

Description:

- keep the current chunk table as the main storage layer
- extend chunk records with version and state fields
- add a small active-version record concept without fully redesigning storage immediately

Strength:

- smallest likely storage evolution

Risk:

- retrieval and cleanup logic become more complex inside one table

## Target Model Option B: Add Separate DocumentVersionsTable Plus Version-aware Chunks

Description:

- keep chunk data in a version-aware chunk store
- add a separate version record store for active, staged, obsolete, and failed states

Strength:

- clearer separation between chunk payload and document-version lifecycle

Risk:

- higher implementation and migration complexity than the smallest-table evolution

## Target Model Option C: Separate Staging Table And Active Table

Description:

- write staged chunk data into a separate staging table
- keep active chunk data in a separate active table

Strength:

- strong physical separation between staged and active data

Risk:

- highest redesign and operational complexity for this PoC

## Comparison Table

| Criterion | Option A: existing table + version fields | Option B: separate DocumentVersionsTable | Option C: separate staging and active tables |
| --- | --- | --- | --- |
| Implementation effort | Low to medium | Medium | High |
| Migration complexity | Medium | Medium to high | High |
| Retrieval query complexity | Medium | Medium | Medium to high |
| Rollback safety | Medium | High | High |
| Cleanup simplicity | Medium | Medium to high | Medium |
| DynamoDB access pattern fit | Good for smallest evolution | Good with clearer lifecycle separation | More complex for this PoC |
| Operational clarity | Medium | High | Medium |

## Proposed Recommendation For This PoC

For this PoC, prefer the smallest safe evolution first.

The most practical direction is likely:

- add version fields to the current chunk model
- add an active document version record concept
- avoid a full storage-layer redesign in the first implementation slice

That keeps the implementation smaller while still moving away from destructive delete-then-save replacement.

## Required Fields

The future implementation likely needs fields or equivalent state for:

- `documentId`
- `version`
- `status`: `staged`, `active`, `obsolete`, `failed`
- `projectId`
- `customerId`
- `documentType`
- `contentHash`
- `chunkCount`
- `createdAt`
- `activatedAt`
- `sourceUri`

These are target fields. They do not all exist in the current code.

## Access Patterns

The future design should support:

- get active version for `documentId`
- list active chunks by `projectId` / `customerId` / `documentType`
- list chunks for `documentId + version`
- mark staged version active conditionally
- cleanup obsolete version chunks

## Open Questions

- should active version state live in the same table or a separate version record store
- how should current unversioned chunk records be treated during migration
- how much content-hash behavior belongs in the write path versus client-provided idempotency
- what is the smallest safe conditional activation model for this PoC

## Current Implementation Boundary

Current implementation is still the current chunk model in `DocumentChunksTable`, but Phase 10I adds low-risk version metadata fields to chunk records as a foundation step.

## Future Implementation Boundary

Future implementation may add version-aware chunk records and an active document version record without fully redesigning the storage layer on the first pass.