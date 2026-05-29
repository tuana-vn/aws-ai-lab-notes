# Document Replacement Test Plan

## Purpose

This document defines the future test plan for implementing safer document replacement in the current `aws-ai-platform-poc` repository.

It is a planning artifact only. It does not add tests to the runtime today.

## Unit Test Cases

- first-time ingestion builds the expected staged version metadata
- same document same content replay returns the previous result when replay detection is enabled
- same document new content replacement creates a staged version instead of deleting the active version first
- embedding failure before staged write leaves the active version unchanged
- partial staged chunk write marks the staged version failed or incomplete
- failure before activation leaves the old version active
- failure after activation follows the defined post-cutover handling rules
- retrieval helper only resolves active versions
- cleanup logic skips active versions and only removes obsolete versions

## Integration Test Cases

- first-time ingestion creates an active version and active chunk set
- same document same content replay does not create unnecessary replacement work
- same document new content replacement preserves the old version until activation succeeds
- retrieval only sees the active version after cutover
- old version remains available until activation succeeds

## Failure Injection Test Cases

- embedding failure before staged write
- partial staged chunk write
- failure before activation
- failure after activation
- cleanup failure after obsolete marking

## Concurrency / Retry Test Cases

- retry same request with same idempotency key
- retry same document with same content hash
- retry same document with different content and no replay key
- concurrent replacements for the same `documentId`
- only one concurrent replacement wins activation

## Migration / Backfill Test Cases

- existing unversioned chunks are interpreted as one default active version
- backfill does not hide current retrievable content
- retrieval remains stable during migration window
- cleanup does not remove migrated active content unexpectedly

## RAG Regression Test Cases

- retrieval only sees active version
- old version remains available until activation succeeds
- `no_source` does not increase unexpectedly after successful replacement
- source selection remains stable after cutover
- replacement does not expose staged chunks to normal retrieval

## Evidence To Capture

Capture evidence for:

- staged chunk count versus active chunk count
- active version before and after cutover
- same-content replay result
- concurrent replacement winner and loser behavior
- retrieval result before activation and after activation
- cleanup behavior for obsolete versions
- RAG query outputs showing that active content remains retrievable during replacement

## Current Implementation Boundary

Current implementation does not include version-aware replacement tests yet.

Phase 10I adds metadata-foundation behavior that future tests can assert without implementing staged replacement.

## Future Implementation Boundary

Future implementation should add these tests alongside the safer replacement slices so retrieval and replacement safety regressions are visible early.