# Phase 10I Document Version Metadata Foundation

## Purpose

This document explains the runtime metadata foundation added in Phase 10I for future version-aware document replacement.

The goal of this phase is intentionally small: add low-risk version-related metadata to document ingestion records and logs so later safer-replacement work has a cleaner starting point.

## Why This Is A Foundation-only Phase

Phase 10I does not implement staged replacement, active version selection, delayed cleanup, or idempotent cutover.

It only adds metadata that makes those future changes easier to implement and easier to observe.

## What Was Added

Phase 10I adds metadata generation in the `/documents` handler for:

- `document_version`
- `content_hash`
- `ingestion_timestamp`
- `chunk_count`
- `replacement_mode`

The successful ingestion log now also includes structured evidence fields such as:

- `request_id`
- `document_id`
- `documentVersion`
- `contentHash`
- `chunkCount`
- `replacementMode`
- `projectId`
- `customerId`
- `documentType`
- `status`

If the request provides `version`, that value is preserved. Otherwise a deterministic default version is generated from the content hash prefix.

## What Intentionally Remains Unchanged

Phase 10I does not change:

- the current delete-then-save replacement behavior
- the current `/rag/query` retrieval behavior
- the current metadata filtering behavior in retrieval
- the current DynamoDB table shape in infrastructure
- the current authorization behavior
- the current RAG answer behavior

## Current Behavior

Current runtime behavior still is:

1. validate the document request
2. chunk content
3. generate embeddings
4. delete existing chunks for the same `documentId`
5. save the replacement chunk set

The new metadata does not change that replacement algorithm. It only enriches the saved chunk records and structured ingestion logs.

## Future Behavior Enabled By This Change

Phase 10I makes later phases easier because future code can build on consistent metadata for:

- document version identity
- same-content replay detection through `content_hash`
- chunk-set completeness checks through `chunk_count`
- migration from direct replacement toward staged replacement
- ingestion evidence review through structured logs

## Manual Verification Commands

Example document ingestion call:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d @test-data/requests/document-request.json
```

Example log review using the new preset:

```bash
python scripts/query_logs.py \
  --log-group /aws/lambda/<documents-function-log-group> \
  --preset document-ingestion \
  --start-minutes-ago 60
```

Do not paste raw JWTs, passwords, or other secrets into commands or saved evidence.

## Acceptance Criteria

Phase 10I is acceptable when:

- document ingestion records include low-risk version metadata
- provided request version is preserved when present
- default version generation is deterministic when version is omitted
- structured logs expose the new metadata without logging raw document content
- existing `/documents` response behavior remains compatible
- existing retrieval-required chunk fields remain unchanged

## Known Limitations

- replacement is still direct delete-then-save
- there is still no active version pointer
- there is still no staged replacement or conditional cutover
- `content_hash` and `document_version` improve evidence and future migration readiness, but they do not make replacement safe by themselves

## Current Implementation Boundary

Current implementation includes version-related metadata on chunk records and ingestion logs, but not staged replacement.

## Future Implementation Boundary

Future implementation may use this metadata foundation for staged writes, active-version selection, replay handling, cleanup, and migration.