import json
import logging
import os
from datetime import datetime, timezone

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

    return {
        "documentId": document_id.strip(),
        "title": title.strip(),
        "projectId": project_id.strip(),
        "customerId": customer_id.strip(),
        "documentType": document_type.strip(),
        "content": content.strip(),
    }


def lambda_handler(event, context):
    path = event.get("rawPath") or event.get("path") or "/documents"

    try:
        body = _parse_body(event)
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid document request",
            path=path,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})

    try:
        chunks = chunk_document(body["content"])
        created_at = datetime.now(timezone.utc).isoformat()
        chunk_records = []
        repository = DocumentRepository(DOCUMENT_CHUNKS_TABLE_NAME)
        embedding_client = EmbeddingClient(EMBEDDING_MODEL_ID)

        for chunk_index, chunk_content in enumerate(chunks):
            embedding = embedding_client.embed_document(chunk_content)
            chunk_records.append(
                {
                    "document_id": body["documentId"],
                    "chunk_id": f"chunk-{chunk_index + 1:04d}",
                    "title": body["title"],
                    "chunk_index": chunk_index,
                    "content": chunk_content,
                    "embedding": embedding,
                    "project_id": body["projectId"],
                    "customer_id": body["customerId"],
                    "document_type": body["documentType"],
                    "created_at": created_at,
                }
            )

        repository.delete_chunks_by_document_id(body["documentId"])
        repository.save_chunks(chunk_records)

        log_json(
            LOGGER,
            logging.INFO,
            "document indexed",
            path=path,
            document_id=body["documentId"],
            chunk_count=len(chunk_records),
            embedding_model_id=EMBEDDING_MODEL_ID,
            status="indexed",
        )

        return json_response(
            200,
            {
                "documentId": body["documentId"],
                "title": body["title"],
                "chunkCount": len(chunk_records),
                "status": "indexed",
            },
        )
    except EmbeddingInvocationError as exc:
        log_json(
            LOGGER,
            logging.ERROR,
            "document embedding invocation failed",
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
                "extra_fields": {
                    "path": path,
                    "document_id": body["documentId"],
                    "embedding_model_id": EMBEDDING_MODEL_ID,
                    "status": "failed",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})