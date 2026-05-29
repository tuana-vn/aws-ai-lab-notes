import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from common.chunking import chunk_document
from common.document_repository import DocumentRepository
from common.embedding_client import EmbeddingClient, EmbeddingInvocationError
from common.logging import get_logger, log_json
from common.response import json_response

LOGGER = get_logger(__name__)
DOCUMENT_CHUNKS_TABLE_NAME = os.environ.get("DOCUMENT_CHUNKS_TABLE_NAME", "")
EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "cohere.embed-english-v3")
DEFAULT_PROJECT_ID = "default"
DEFAULT_CUSTOMER_ID = "default"
DEFAULT_DOCUMENT_TYPE = "general"
STAGED_REPLACEMENT_MODE = "staged_replace"
VERSION_STATUS_STAGED = "staged"
VERSION_STATUS_ACTIVE = "active"
INDEXED_STATUS = "indexed"


def _parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        raise ValueError("Request body is required.")

    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
    elif isinstance(raw_body, dict):
        body = raw_body
    else:
        raise ValueError("Request body must be a JSON object.")

    document_id = body.get("documentId")
    title = body.get("title")
    content = body.get("content")
    project_id = body.get("projectId", DEFAULT_PROJECT_ID)
    customer_id = body.get("customerId", DEFAULT_CUSTOMER_ID)
    document_type = body.get("documentType", DEFAULT_DOCUMENT_TYPE)
    version = body.get("version")

    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("Field 'documentId' is required and must be a non-empty string.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Field 'title' is required and must be a non-empty string.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Field 'content' is required and must be a non-empty string.")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("Field 'projectId' must be a non-empty string when provided.")
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("Field 'customerId' must be a non-empty string when provided.")
    if not isinstance(document_type, str) or not document_type.strip():
        raise ValueError("Field 'documentType' must be a non-empty string when provided.")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise ValueError("Field 'version' must be a non-empty string when provided.")

    return {
        "documentId": document_id.strip(),
        "title": title.strip(),
        "projectId": project_id.strip(),
        "customerId": customer_id.strip(),
        "documentType": document_type.strip(),
        "content": content.strip(),
        "version": version.strip() if isinstance(version, str) else None,
    }


def _normalize_content_for_hash(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n").strip()


def _compute_content_hash(content: str) -> str:
    normalized_content = _normalize_content_for_hash(content)
    return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()


def _resolve_document_version(version: str | None, content_hash: str) -> str:
    if version:
        return version
    return f"content-{content_hash[:16]}"


def _resolve_version_status(chunk: dict[str, object]) -> str | None:
    version_status = chunk.get("version_status")
    if isinstance(version_status, str):
        return version_status
    version_status = chunk.get("versionStatus")
    if isinstance(version_status, str):
        return version_status
    return None


def _is_retrievable_chunk(chunk: dict[str, object]) -> bool:
    return _resolve_version_status(chunk) in {None, VERSION_STATUS_ACTIVE}


def _local_chunk_id(chunk_index: int) -> str:
    return f"chunk-{chunk_index + 1:04d}"


def _stored_chunk_id(document_version: str, chunk_index: int) -> str:
    return f"{document_version}#{_local_chunk_id(chunk_index)}"


def _find_matching_active_version(
    existing_chunks: list[dict[str, object]],
    document_version: str,
    content_hash: str,
    chunk_count: int,
) -> list[dict[str, object]]:
    matching_chunks = [
        chunk
        for chunk in existing_chunks
        if _is_retrievable_chunk(chunk)
        and chunk.get("document_version") == document_version
        and chunk.get("content_hash") == content_hash
    ]
    if len(matching_chunks) != chunk_count:
        return []
    return matching_chunks


def _has_conflicting_active_version(existing_chunks: list[dict[str, object]], document_version: str) -> bool:
    return any(
        _is_retrievable_chunk(chunk) and chunk.get("document_version") == document_version
        for chunk in existing_chunks
    )


def _indexed_response(body: dict[str, str | None], chunk_count: int):
    return json_response(
        200,
        {
            "documentId": body["documentId"],
            "title": body["title"],
            "chunkCount": chunk_count,
            "status": INDEXED_STATUS,
        },
    )


def _build_chunk_record(
    body: dict[str, str | None],
    chunk_index: int,
    chunk_content: str,
    embedding: list[float],
    ingestion_timestamp: str,
    document_version: str,
    content_hash: str,
    chunk_count: int,
) -> dict[str, object]:
    return {
        "document_id": body["documentId"],
        "chunk_id": _stored_chunk_id(document_version, chunk_index),
        "title": body["title"],
        "chunk_index": chunk_index,
        "content": chunk_content,
        "embedding": embedding,
        "project_id": body["projectId"],
        "customer_id": body["customerId"],
        "document_type": body["documentType"],
        "created_at": ingestion_timestamp,
        "document_version": document_version,
        "content_hash": content_hash,
        "ingestion_timestamp": ingestion_timestamp,
        "chunk_count": chunk_count,
        "replacement_mode": STAGED_REPLACEMENT_MODE,
        "version_status": VERSION_STATUS_STAGED,
    }


def lambda_handler(event, context):
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/documents"

    try:
        body = _parse_body(event)
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid document request",
            request_id=request_id,
            path=path,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})

    try:
        chunks = chunk_document(body["content"])
        ingestion_timestamp = datetime.now(timezone.utc).isoformat()
        content_hash = _compute_content_hash(body["content"])
        document_version = _resolve_document_version(body.get("version"), content_hash)
        chunk_count = len(chunks)
        chunk_records = []
        repository = DocumentRepository(DOCUMENT_CHUNKS_TABLE_NAME)
        existing_chunks = repository.list_chunks_by_document_id(body["documentId"])

        if _find_matching_active_version(existing_chunks, document_version, content_hash, chunk_count):
            log_json(
                LOGGER,
                logging.INFO,
                "document ingestion idempotent replay",
                request_id=request_id,
                path=path,
                document_id=body["documentId"],
                documentVersion=document_version,
                contentHash=content_hash,
                chunkCount=chunk_count,
                replacementMode=STAGED_REPLACEMENT_MODE,
                versionStatus=VERSION_STATUS_ACTIVE,
                projectId=body["projectId"],
                customerId=body["customerId"],
                documentType=body["documentType"],
                replay=True,
                status=INDEXED_STATUS,
            )
            return _indexed_response(body, chunk_count)

        if _has_conflicting_active_version(existing_chunks, document_version):
            log_json(
                LOGGER,
                logging.WARNING,
                "document version conflict",
                request_id=request_id,
                path=path,
                document_id=body["documentId"],
                documentVersion=document_version,
                contentHash=content_hash,
                chunkCount=chunk_count,
                replacementMode=STAGED_REPLACEMENT_MODE,
                status="conflict",
            )
            return json_response(
                409,
                {"message": "An active document version with the same version already exists for this document."},
            )

        embedding_client = EmbeddingClient(EMBEDDING_MODEL_ID)

        for chunk_index, chunk_content in enumerate(chunks):
            embedding = embedding_client.embed_document(chunk_content)
            chunk_records.append(
                _build_chunk_record(
                    body,
                    chunk_index,
                    chunk_content,
                    embedding,
                    ingestion_timestamp,
                    document_version,
                    content_hash,
                    chunk_count,
                )
            )

        repository.save_chunks(chunk_records)
        staged_chunk_count = repository.count_chunks_by_document_version(
            body["documentId"],
            document_version,
        )

        if staged_chunk_count != chunk_count:
            repository.mark_chunks_failed_by_document_version(body["documentId"], document_version)
            raise RuntimeError("Staged chunk count validation failed.")

        try:
            repository.mark_chunks_active_by_document_version(body["documentId"], document_version)
        except Exception:
            repository.mark_chunks_failed_by_document_version(body["documentId"], document_version)
            raise

        previous_version_obsolete_failed = False
        try:
            repository.mark_chunks_obsolete_by_document_id(
                body["documentId"],
                except_document_version=document_version,
            )
        except Exception:
            previous_version_obsolete_failed = True
            log_json(
                LOGGER,
                logging.WARNING,
                "document indexed but previous chunks still visible",
                request_id=request_id,
                path=path,
                document_id=body["documentId"],
                documentVersion=document_version,
                contentHash=content_hash,
                chunkCount=chunk_count,
                stagedChunkCount=staged_chunk_count,
                replacementMode=STAGED_REPLACEMENT_MODE,
                versionStatus=VERSION_STATUS_ACTIVE,
                status=INDEXED_STATUS,
            )

        log_json(
            LOGGER,
            logging.INFO,
            "document indexed",
            request_id=request_id,
            path=path,
            document_id=body["documentId"],
            documentVersion=document_version,
            contentHash=content_hash,
            chunkCount=chunk_count,
            stagedChunkCount=staged_chunk_count,
            replacementMode=STAGED_REPLACEMENT_MODE,
            versionStatus=VERSION_STATUS_ACTIVE,
            projectId=body["projectId"],
            customerId=body["customerId"],
            documentType=body["documentType"],
            chunk_count=chunk_count,
            embedding_model_id=EMBEDDING_MODEL_ID,
            previousVersionObsoleteFailed=previous_version_obsolete_failed,
            status=INDEXED_STATUS,
        )

        return _indexed_response(body, chunk_count)
    except EmbeddingInvocationError as exc:
        log_json(
            LOGGER,
            logging.ERROR,
            "document embedding invocation failed",
            request_id=request_id,
            path=path,
            document_id=body["documentId"],
            embedding_model_id=EMBEDDING_MODEL_ID,
            status="failed",
            error=str(exc),
        )
        return json_response(502, {"message": "Embedding invocation failed."})
    except Exception:
        LOGGER.exception(
            "unexpected document indexing failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": path,
                    "document_id": body["documentId"],
                    "embedding_model_id": EMBEDDING_MODEL_ID,
                    "status": "failed",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})