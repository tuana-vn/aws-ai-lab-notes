# Phase 10J Staged Chunk Write Path

## Purpose

This document describes the small reliability slice added in Phase 10J for safer document replacement in the current `aws-ai-platform-poc` repository.

## Why This Phase Exists

Before Phase 10J, `/documents` deleted old chunks before writing the replacement set. That made replacement vulnerable to partial-write failures.

Phase 10J changes the write path so new chunks are saved as staged records first, validated, and only then promoted for retrieval.

## Behavior Added

Phase 10J adds:

- staged chunk writes using `version_status="staged"`
- versioned stored chunk keys using `<documentVersion>#chunk-0001` so staged writes do not overwrite older chunks for the same `documentId`
- staged chunk count validation after save
- promotion of the new document version to `active`
- marking older chunks for the same `documentId` as `obsolete` only after the new version is active
- retrieval filtering that includes only legacy chunks with no version status and chunks marked `active`

Successful ingestion now logs:

- `document_id`
- `documentVersion`
- `contentHash`
- `chunkCount`
- `stagedChunkCount`
- `replacementMode`
- `versionStatus="active"`
- `status="indexed"`

## Compatibility With Legacy Chunks

Existing chunk records without `version_status` remain retrievable for backward compatibility.

Existing legacy chunk keys such as `chunk-0001` also remain retrievable. New version-aware chunk writes use version-prefixed keys to avoid overwriting legacy or previous-version records during staging.

Phase 10J only changes retrieval to ignore chunks explicitly marked as:

- `staged`
- `obsolete`
- `failed`

## What Remains Unchanged

Phase 10J does not change:

- the current single-table mini RAG storage model
- authorization behavior
- the `/documents` response contract
- the current RAG answer behavior beyond ignoring non-retrievable chunk states
- infrastructure resources or `template.yaml`

## Remaining Limitations

- there is still no separate active version pointer table
- there is still no background cleanup job for obsolete or failed chunks
- activation and obsolete marking are still multi-step updates, not a transactional version lifecycle
- if marking the new version active succeeds but marking older chunks obsolete fails, retrieval may temporarily see both old and new active content until repair or retry occurs
- full production-grade concurrency control and delayed cleanup remain future work

## Manual Verification Commands

Example document ingestion call:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d @test-data/requests/document-request.json
```

Run focused tests:

```bash
python -m unittest tests.test_documents_handler tests.test_rag_service
```

Review document-ingestion logs without exposing raw content:

```bash
python scripts/query_logs.py \
  --log-group /aws/lambda/<documents-function-log-group> \
  --preset document-ingestion \
  --start-minutes-ago 60
```

## Acceptance Criteria

Phase 10J is acceptable when:

- new chunks are saved as staged before activation
- new chunks use versioned chunk keys so staging does not overwrite existing document chunks
- staged chunk count is validated before success is returned
- retrieval ignores staged, obsolete, and failed chunks
- legacy chunks without version status remain retrievable
- old chunks are not deleted before staged save is attempted
- `/documents` keeps the same response contract

## Current Implementation Boundary

Current implementation now supports staged chunk write and active-status retrieval filtering within the existing chunk table.

## Future Implementation Boundary

Future work may add a separate active-version pointer, background cleanup, stronger concurrency handling, and broader version lifecycle controls.