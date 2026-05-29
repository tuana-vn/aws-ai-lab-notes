# Document Ingestion Failure Mode Review

## Purpose

This document reviews failure modes for the current `/documents` ingestion path and describes the future behavior needed to make replacement safer.

It stays grounded in the current repository behavior and does not claim that safer replacement is already implemented.

## Current Ingestion Flow

The current ingestion flow is:

1. validate request body
2. chunk the incoming content
3. generate embeddings for each chunk
4. delete old chunks for the same `documentId`
5. save the new chunk set
6. log success or failure

This flow is clear for learning, but replacement safety is weak because delete happens before new data is fully committed.

## Failure Modes

### Invalid Request

- What can happen today: the handler returns `400` before chunking or writing.
- Risk: low.
- Recommended future behavior: keep fast validation failure before any replacement work begins.
- Priority: P2.

### Embedding Failure

- What can happen today: embedding generation fails before delete-and-save replacement begins, and the route returns `502`.
- Risk: lower than replacement-time failures because old chunks have not been deleted yet.
- Recommended future behavior: keep old active data untouched and fail cleanly before staged promotion begins.
- Priority: P1.

### Partial Chunk Write

- What can happen today: some new chunks may be written before the handler fails.
- Risk: partial document state can become visible if old chunks were already removed.
- Recommended future behavior: write staged chunks separately and validate completeness before cutover.
- Priority: P0.

### Delete Old Chunks Succeeds But New Write Fails

- What can happen today: the old document evidence is removed and the new replacement is incomplete or absent.
- Risk: retrieval can lose valid evidence or return partial results.
- Recommended future behavior: do not delete the old version first; preserve it until new replacement is complete and ready for cutover.
- Priority: P0.

### Client Timeout After Partial Write

- What can happen today: the caller may not know whether replacement completed, partially completed, or failed.
- Risk: the client retries without knowing the current document state.
- Recommended future behavior: future ingestion design should expose a clearer idempotency or versioning model so the caller can determine whether the same replacement is already staged or active.
- Priority: P1.

### Retry With Same Document

- What can happen today: the same request may delete and rewrite the document again.
- Risk: repeated work, repeated embeddings, and possible replacement instability under failure.
- Recommended future behavior: detect exact replay through version, content hash, or idempotency key.
- Priority: P1.

### Retry With Different Content Same documentId

- What can happen today: a later request silently replaces the old content for the same `documentId`.
- Risk: replacement intent is ambiguous and older content can disappear before the new content is fully safe.
- Recommended future behavior: treat this as a versioned replacement, not as a blind overwrite.
- Priority: P0.

### Concurrent Replacement For Same documentId

- What can happen today: concurrent requests for the same `documentId` can race, overwrite each other, or create unclear final state.
- Risk: retrieval state becomes hard to reason about.
- Recommended future behavior: use version-aware staging and conditional cutover so only one candidate becomes active.
- Priority: P0.

### Trace / Log Write Failure

- What can happen today: `/documents` relies on logs for ingestion evidence and does not write a trace-table record.
- Risk: investigation quality is weaker if logs are incomplete or late.
- Recommended future behavior: decide whether ingestion evidence should remain log-only or gain stronger structured evidence in a later hardening phase.
- Priority: P2.

## Operator Investigation Steps

If document-ingestion failure is suspected, operators should:

1. inspect the `/documents` request log entries for the document ID
2. determine whether embedding failure occurred before replacement write activity
3. inspect the chunk table state for the affected `documentId` if direct access is available
4. compare expected chunk count versus actual stored chunk count
5. rerun ingestion only after understanding whether the current state is empty, partial, or fully replaced

## Evidence To Capture

Capture:

- `documentId`
- ingestion request time window
- chunk count expected by the request
- chunk count actually observed if the table can be inspected
- relevant Lambda log entries for success or failure
- any repeated ingestion attempts for the same document in the same window

## Acceptance Criteria Before Implementation

Before implementing a safer replacement flow:

- the team must define how document identity differs from version identity
- the team must define how same-content replay is detected
- the team must define how staged data becomes active
- the team must define how old versions remain available until cutover succeeds
- the team must define cleanup and rollback rules for obsolete versions

## Current Implementation Boundary

Current implementation means `/documents` still uses a direct chunk replacement flow without staged versions.

## Future Implementation Boundary

Future implementation means staged replacement, explicit cutover, and delayed cleanup for safer document ingestion.

Phase 10H turns that future design into an implementation plan, but it does not implement runtime changes.