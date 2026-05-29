# Document Versioning And Replacement Design

## Purpose

This document defines a practical target design for safer document replacement in the current `aws-ai-platform-poc` repository.

It does not claim that document versioning, active version pointers, or staged replacement already exist. This is a design target for a later implementation phase.

## Document Identity Model

The target document identity model should distinguish document identity from document version identity.

Suggested fields:

- `documentId`: stable document identity across replacements
- `projectId`: retrieval and ownership boundary metadata
- `customerId`: retrieval and ownership boundary metadata
- `documentType`: retrieval and classification metadata
- `version`: replacement generation identifier
- `sourceUri`: optional upstream source reference if available
- `ingestionTimestamp`: time the candidate version was ingested
- `contentHash`: useful for duplicate detection when the same content is submitted again

## Current-state Model

Current state is simpler:

- chunk records are keyed by `documentId` and `chunkId`
- replacement is modeled as delete old chunks, then save new chunks
- there is no explicit version record
- there is no active version pointer
- there is no staged replacement state

This is acceptable for the current learning baseline, but weak for safe replacement.

## Target-state Model

Target state should separate:

- stable document identity
- candidate replacement version
- currently active version

This means replacement can be prepared before it becomes visible to retrieval.

## Active Version Pointer Concept

The active version pointer is the concept that retrieval should follow only one designated document version for normal query use.

Important boundary:

- this concept does not exist in the current implementation
- it is a design target for safer replacement

## Staging Version Concept

A staging version is a candidate document version that has been accepted for processing but is not yet active for retrieval.

Its purpose is simple:

- let the system prepare chunks and embeddings safely
- keep the old version available while the new version is still incomplete

## Chunk Records For Versions

In a future version-aware model, chunk records should be associated with a specific version rather than only the stable document identity.

That lets the system:

- keep old and new chunk sets side by side temporarily
- validate the staged chunk set before cutover
- clean up obsolete chunk sets later rather than first

## Safe Replacement Flow

### 1. Receive document replacement request

Accept a request that identifies the document and candidate replacement content.

### 2. Validate metadata and permissions

Validate required metadata and ensure the request is permitted under the target access model.

### 3. Compute content hash if available

If practical, compute a `contentHash` so the system can distinguish exact replay from real content change.

### 4. Create new staged version

Create a staged replacement version identifier without disturbing the current active version.

### 5. Generate chunks and embeddings

Prepare the candidate chunk set and embeddings for that staged version.

### 6. Save staged chunks

Write the staged chunk set without deleting the currently active chunk set.

### 7. Validate staged chunk count

Confirm that the staged version has the expected chunk count and basic completeness indicators before promotion.

### 8. Atomically or conditionally mark new version active

Only after staged data is ready should the system cut over the active version pointer.

### 9. Keep old version available until cutover succeeds

The currently active version should remain retrievable until the new version is fully ready and promoted.

### 10. Cleanup old versions later

Cleanup should happen after successful cutover, not before replacement work begins.

## Idempotency Key Options

### documentId + version

Use when the caller or system can provide a stable version identifier.

Strength:

- explicit version identity

Tradeoff:

- requires stronger version discipline

### documentId + contentHash

Use when the goal is to detect exact same-content replay.

Strength:

- good duplicate-ingestion detection without forcing the client to manage versions directly

Tradeoff:

- requires content hashing and clear policy for hash collisions or normalization

### Client-provided idempotency key

Use when the caller can manage request replay tracking explicitly.

Strength:

- flexible request-level replay handling

Tradeoff:

- requires request-key governance and retention rules

## Duplicate Ingestion Handling

The future design should distinguish:

- exact replay of the same content
- new content with the same `documentId`
- concurrent conflicting replacement attempts

Those are different operational situations and should not all be treated as simple replacement.

## Rollback Behavior

Rollback should prefer preserving the old active version until the new version is proven complete.

That means rollback is mostly:

- avoid cutover if staged data is incomplete
- keep the old active version in place
- retry or replace the staged version later

## Cleanup Strategy

Cleanup should be delayed and deliberate.

The system should remove obsolete versions only after:

- the new version is active
- validation is complete
- rollback is no longer needed for the old version

## Current Implementation Boundary

Current implementation does not include active version pointers, staged versions, version-aware chunk sets, or delayed cleanup.

## Future Implementation Boundary

Future implementation may add version metadata, staged replacement, explicit cutover, and delayed cleanup to make ingestion safer and more idempotent.