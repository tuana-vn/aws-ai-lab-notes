import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.bedrock_client import BedrockClient, BedrockInvocationError
from common.document_repository import DocumentRepository
from common.embedding_client import EmbeddingClient, EmbeddingInvocationError
from common.logging import get_logger, log_json
from common.response import json_response
from common.retrieval import retrieve_top_chunks
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
DOCUMENT_CHUNKS_TABLE_NAME = os.environ.get("DOCUMENT_CHUNKS_TABLE_NAME", "")
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "apac.amazon.nova-lite-v1:0")
EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "cohere.embed-english-v3")
MIN_SIMILARITY_SCORE = float(os.environ.get("MIN_SIMILARITY_SCORE", "0.25"))
RETRIEVAL_MODE = "embedding"
NO_SOURCE_ANSWER = "I do not know based on the available documents."
FILTER_FIELD_MAP = {
    "projectId": "project_id",
    "customerId": "customer_id",
    "documentType": "document_type",
}


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

    question = body.get("question")
    raw_filters = body.get("filters", {})
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Field 'question' is required and must be a non-empty string.")
    if raw_filters is None:
        raw_filters = {}
    if not isinstance(raw_filters, dict):
        raise ValueError("Field 'filters' must be a JSON object when provided.")

    filters = {}
    for api_field in FILTER_FIELD_MAP:
        value = raw_filters.get(api_field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Field 'filters.{api_field}' must be a non-empty string when provided.")
        filters[api_field] = value.strip()

    return {
        "question": question.strip(),
        "filters": filters,
    }


def _filter_chunks_by_metadata(chunks, filters):
    if not filters:
        return list(chunks)

    eligible_chunks = []
    for chunk in chunks:
        matches_all_filters = True
        for api_field, storage_field in FILTER_FIELD_MAP.items():
            expected_value = filters.get(api_field)
            if expected_value is None:
                continue
            if chunk.get(storage_field) != expected_value:
                matches_all_filters = False
                break

        if matches_all_filters:
            eligible_chunks.append(chunk)

    return eligible_chunks


def _build_grounded_prompt(question, chunks):
    context_blocks = []
    for chunk in chunks:
        context_blocks.append(
            "\n".join(
                [
                    f"[Source: documentId={chunk['document_id']}, chunkId={chunk['chunk_id']}, title={chunk['title']}]",
                    chunk["content"],
                ]
            )
        )

    context_text = "\n\n".join(context_blocks)
    return (
        "You are a technical document assistant.\n"
        "Answer the user's question using only the context below.\n"
        'If the answer is not in the context, say: "I do not know based on the available documents."\n'
        "Do not invent facts.\n"
        "Keep the answer concise.\n"
        "Include source references by documentId and chunkId where relevant.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question:\n{question}"
    )


def _serialize_sources(chunks):
    return [
        {
            "documentId": chunk["document_id"],
            "chunkId": chunk["chunk_id"],
            "title": chunk["title"],
            "chunkIndex": int(chunk["chunk_index"]),
            "similarity": round(float(chunk["similarity"]), 4),
            "projectId": chunk.get("project_id", "default"),
            "customerId": chunk.get("customer_id", "default"),
            "documentType": chunk.get("document_type", "general"),
        }
        for chunk in chunks
    ]


def _serialize_sources_for_trace(sources):
    return [
        {
            **source,
            "similarity": str(source["similarity"]),
        }
        for source in sources
    ]


def _build_no_source_response(request_id, filters):
    return {
        "requestId": request_id,
        "answer": NO_SOURCE_ANSWER,
        "sources": [],
        "modelId": BEDROCK_MODEL_ID,
        "embeddingModelId": EMBEDDING_MODEL_ID,
        "retrievalMode": RETRIEVAL_MODE,
        "minSimilarityScore": MIN_SIMILARITY_SCORE,
        "filters": filters,
        "status": "no_source",
    }


def _build_trace_record(
    request_id,
    path,
    question,
    filters,
    eligible_chunk_count,
    answer_preview,
    sources,
    status,
    latency_ms,
):
    return {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "question": question,
        "filters": filters,
        "answer_preview": answer_preview[:500],
        "model_id": BEDROCK_MODEL_ID,
        "embedding_model_id": EMBEDDING_MODEL_ID,
        "retrieval_mode": RETRIEVAL_MODE,
        "min_similarity_score": str(MIN_SIMILARITY_SCORE),
        "eligible_chunk_count": eligible_chunk_count,
        "source_count": len(sources),
        "sources": _serialize_sources_for_trace(sources),
        "status": status,
        "latency_ms": latency_ms,
    }


def lambda_handler(event, context):
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/rag/query"

    try:
        request_payload = _parse_body(event)
    except ValueError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "invalid rag query request",
            request_id=request_id,
            path=path,
            error=str(exc),
        )
        return json_response(400, {"message": str(exc)})

    started_at = perf_counter()

    try:
        question = request_payload["question"]
        filters = request_payload["filters"]
        repository = DocumentRepository(DOCUMENT_CHUNKS_TABLE_NAME)
        chunks = repository.list_chunks()
        eligible_chunks = _filter_chunks_by_metadata(chunks, filters)
        eligible_chunk_count = len(eligible_chunks)
        question_embedding = EmbeddingClient(EMBEDDING_MODEL_ID).embed_query(question)
        # This scan-and-score approach is intentionally simple for a learning PoC.
        # Production retrieval should use a proper vector store or Bedrock Knowledge Bases.
        top_chunks = retrieve_top_chunks(
            question_embedding,
            eligible_chunks,
            min_similarity_score=MIN_SIMILARITY_SCORE,
        )
        sources = _serialize_sources(top_chunks)

        if not top_chunks:
            latency_ms = int((perf_counter() - started_at) * 1000)
            TraceRepository(TRACE_TABLE_NAME).save_trace(
                _build_trace_record(
                    request_id,
                    path,
                    question,
                    filters,
                    eligible_chunk_count,
                    NO_SOURCE_ANSWER,
                    [],
                    "no_source",
                    latency_ms,
                )
            )
            log_json(
                LOGGER,
                logging.INFO,
                "rag query returned no source",
                request_id=request_id,
                path=path,
                model_id=BEDROCK_MODEL_ID,
                embedding_model_id=EMBEDDING_MODEL_ID,
                retrieval_mode=RETRIEVAL_MODE,
                min_similarity_score=MIN_SIMILARITY_SCORE,
                filters=filters,
                eligible_chunk_count=eligible_chunk_count,
                latency_ms=latency_ms,
                source_count=0,
                status="no_source",
            )
            return json_response(200, _build_no_source_response(request_id, filters))

        prompt = _build_grounded_prompt(question, top_chunks)
        answer = BedrockClient().converse(BEDROCK_MODEL_ID, prompt)
        latency_ms = int((perf_counter() - started_at) * 1000)

        trace_record = _build_trace_record(
            request_id,
            path,
            question,
            filters,
            eligible_chunk_count,
            answer,
            sources,
            "completed",
            latency_ms,
        )
        TraceRepository(TRACE_TABLE_NAME).save_trace(trace_record)

        log_json(
            LOGGER,
            logging.INFO,
            "rag query completed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
            embedding_model_id=EMBEDDING_MODEL_ID,
            retrieval_mode=RETRIEVAL_MODE,
            min_similarity_score=MIN_SIMILARITY_SCORE,
            filters=filters,
            eligible_chunk_count=eligible_chunk_count,
            latency_ms=latency_ms,
            source_count=len(sources),
            status="completed",
        )

        return json_response(
            200,
            {
                "requestId": request_id,
                "answer": answer,
                "sources": sources,
                "modelId": BEDROCK_MODEL_ID,
                "embeddingModelId": EMBEDDING_MODEL_ID,
                "retrievalMode": RETRIEVAL_MODE,
                "minSimilarityScore": MIN_SIMILARITY_SCORE,
                "filters": filters,
                "status": "completed",
            },
        )
    except (EmbeddingInvocationError, BedrockInvocationError) as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        source_count = len(locals().get("sources", []))
        eligible_chunk_count = locals().get("eligible_chunk_count", 0)
        log_json(
            LOGGER,
            logging.ERROR,
            "rag invocation failed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
            embedding_model_id=EMBEDDING_MODEL_ID,
            retrieval_mode=RETRIEVAL_MODE,
            min_similarity_score=MIN_SIMILARITY_SCORE,
            filters=locals().get("filters", {}),
            eligible_chunk_count=eligible_chunk_count,
            latency_ms=latency_ms,
            source_count=source_count,
            status="failed",
            error=str(exc),
        )
        return json_response(502, {"message": "Embedding or Bedrock invocation failed."})
    except Exception:
        latency_ms = int((perf_counter() - started_at) * 1000)
        source_count = len(locals().get("sources", []))
        eligible_chunk_count = locals().get("eligible_chunk_count", 0)
        LOGGER.exception(
            "unexpected rag query failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": path,
                    "model_id": BEDROCK_MODEL_ID,
                    "embedding_model_id": EMBEDDING_MODEL_ID,
                    "retrieval_mode": RETRIEVAL_MODE,
                    "min_similarity_score": MIN_SIMILARITY_SCORE,
                    "filters": locals().get("filters", {}),
                    "eligible_chunk_count": eligible_chunk_count,
                    "latency_ms": latency_ms,
                    "source_count": source_count,
                    "status": "failed",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})