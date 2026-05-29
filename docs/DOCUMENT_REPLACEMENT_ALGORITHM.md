# Document Replacement Algorithm

## Purpose

This document describes the current and target algorithms for document replacement in the current `aws-ai-platform-poc` repository.

The pseudocode is algorithm-level only. It does not change runtime code.

## Current Delete-then-save Algorithm

Current behavior is effectively:

```python
def replace_document(document_request):
    validate(document_request)
    chunks = chunk_document(document_request.content)
    chunk_records = []

    for chunk in chunks:
        embedding = embed(chunk)
        chunk_records.append(build_chunk_record(document_request, chunk, embedding))

    delete_chunks_by_document_id(document_request.document_id)
    save_chunks(chunk_records)
    return indexed_response(chunk_count=len(chunk_records))
```

This is easy to follow, but not safe for production replacement because old data is removed before the new set is fully safe.

## Target Staged Replacement Algorithm

Target behavior should be closer to:

```python
def replace_document_safely(document_request):
    validate(document_request)
    metadata = normalize_metadata(document_request)
    content_hash = compute_content_hash_if_enabled(document_request.content)
    active_version = get_active_version(document_request.document_id)

    if same_content_is_already_active(active_version, content_hash):
        return existing_result(active_version)

    staged_version = create_staged_version(metadata, content_hash)
    staged_chunks = []

    for chunk in chunk_document(document_request.content):
        embedding = embed(chunk)
        staged_chunks.append(build_versioned_chunk_record(staged_version, chunk, embedding))

    save_staged_chunks(staged_version, staged_chunks)
    validate_staged_chunk_count(staged_version, expected_count=len(staged_chunks))
    activate_version_conditionally(document_request.document_id, staged_version, active_version)
    mark_previous_version_obsolete_after_activation(active_version)
    return indexed_response(version=staged_version.version, chunk_count=len(staged_chunks))
```

## Same-content Replay Handling

Target behavior:

```python
if active_version and active_version.content_hash == content_hash:
    return already_indexed_response(active_version)
```

Goal:

- avoid unnecessary replacement when the same content is already active

## New-content Replacement Handling

Target behavior:

```python
if active_version and active_version.content_hash != content_hash:
    staged_version = create_staged_version(...)
    build_and_save_staged_chunks(staged_version)
    activate_version_conditionally(...)
```

Goal:

- treat real content change as a new versioned replacement, not as a blind overwrite

## Concurrent Replacement Handling

Target behavior:

```python
def activate_version_conditionally(document_id, staged_version, previous_active_version):
    # only one staged candidate should win activation
    conditional_update_active_pointer(
        document_id=document_id,
        expected_previous_version=previous_active_version,
        new_active_version=staged_version,
    )
```

Goal:

- if concurrent replacements happen, only one should win activation

## Cutover Algorithm

Target behavior:

```python
def cutover(document_id, staged_version, active_version):
    assert staged_version.status == "staged"
    assert staged_version.chunk_count_is_valid
    conditional_switch_active_version(document_id, active_version, staged_version)
    mark_version_active(staged_version)
    mark_previous_version_obsolete(active_version)
```

Goal:

- the old active version remains visible until the new version is activated
- active version switch is conditional rather than blind

## Rollback Algorithm

Target behavior:

```python
def rollback_failed_replacement(document_id, staged_version, active_version):
    if staged_version_is_incomplete(staged_version):
        mark_version_failed(staged_version)
        keep_active_version(active_version)
        return active_version
```

Goal:

- rollback usually means do not cut over, not delete old active data first

## Cleanup Algorithm

Target behavior:

```python
def cleanup_obsolete_versions(document_id):
    obsolete_versions = list_obsolete_versions(document_id)
    for version in obsolete_versions:
        if cleanup_window_has_passed(version):
            delete_version_chunks(version)
            mark_cleanup_complete(version)
```

Goal:

- cleanup happens after activation, not before replacement safety is established

## Retrieval Algorithm After Active Version Support

Target behavior:

```python
def list_retrievable_chunks(filters):
    active_versions = resolve_active_versions(filters)
    return list_chunks_for_active_versions(active_versions)
```

Goal:

- retrieval only sees the active version under normal query handling

## Failure Handling Table

| Failure case | Current behavior | Target behavior |
| --- | --- | --- |
| invalid request | fail before writes | keep fast fail before writes |
| embedding failure before delete | fail before replacement write | keep active version unchanged |
| staged chunk write failure | not applicable today | mark staged version failed and keep old active version |
| failure before activation | not applicable today | keep old active version visible |
| failure after activation | not explicitly handled | require cleanup and rollback review, but do not reactivate blindly without rules |
| same content replay | rewrites by default | return prior result when active content hash or idempotency key matches |
| concurrent replacement | race-prone | conditional activation so only one candidate wins |

## Current Implementation Boundary

Current implementation remains the delete-then-save algorithm.

## Future Implementation Boundary

Future implementation may add staged writes, conditional cutover, replay handling, version-aware retrieval, and delayed cleanup.