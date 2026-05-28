import logging
import os
from datetime import datetime, timezone
from time import perf_counter

from common.bedrock_client import BedrockClient, BedrockInvocationError
from common.document_repository import DocumentRepository
from common.embedding_client import EmbeddingClient, EmbeddingInvocationError
from common.guardrails import evaluate_input_guardrail
from common.logging import get_logger, log_json
from common.output_guardrails import evaluate_output_guardrail
from common.policy import AccessDeniedError, assert_filters_allowed, resolve_access_context
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
BLOCKED_ANSWER = "I cannot process this request because it violates the input safety policy."
FILTER_FIELD_MAP = {
    "projectId": "project_id",
    "customerId": "customer_id",
    "documentType": "document_type",
}
NO_MODEL_ANSWER_OUTPUT_GUARDRAIL = {
    "action": "not_applicable",
    "reason": "no_model_answer",
    "warnings": [],
}


def normalize_filters(raw_filters):
    if raw_filters is None:
        return {}
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

    return filters


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


def _build_body(request_id, user_id, answer, sources, filters, guardrail_result, output_guardrail_result, status):
    return {
        "requestId": request_id,
        "userId": user_id,
        "answer": answer,
        "sources": sources,
        "modelId": BEDROCK_MODEL_ID,
        "embeddingModelId": EMBEDDING_MODEL_ID,
        "retrievalMode": RETRIEVAL_MODE,
        "minSimilarityScore": MIN_SIMILARITY_SCORE,
        "filters": filters,
        "guardrail": {
            "action": guardrail_result["action"],
            "reason": guardrail_result["reason"],
            "matchedRule": guardrail_result["matchedRule"],
        },
        "outputGuardrail": output_guardrail_result,
        "status": status,
    }


def _build_trace_record(
    request_id,
    path,
    user_id,
    question,
    filters,
    guardrail_result,
    output_guardrail_result,
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
        "user_id": user_id,
        "question": question,
        "filters": filters,
        "answer_preview": answer_preview[:500],
        "guardrail_action": guardrail_result["action"],
        "guardrail_reason": guardrail_result["reason"],
        "guardrail_matched_rule": guardrail_result["matchedRule"],
        "output_guardrail_action": output_guardrail_result["action"],
        "output_guardrail_reason": output_guardrail_result["reason"],
        "output_guardrail_warnings": output_guardrail_result["warnings"],
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


def _save_trace(trace_record, save_trace):
    if not save_trace:
        return
    TraceRepository(TRACE_TABLE_NAME).save_trace(trace_record)


def run_rag_query(question: str, filters: dict, event: dict, request_id: str, path: str, save_trace: bool = True) -> dict:
    started_at = perf_counter()
    access_context = resolve_access_context(event)
    user_id = access_context.user_id
    guardrail_result = evaluate_input_guardrail(question)
    output_guardrail_result = dict(NO_MODEL_ANSWER_OUTPUT_GUARDRAIL)

    try:
        if not guardrail_result["allowed"]:
            latency_ms = int((perf_counter() - started_at) * 1000)
            _save_trace(
                _build_trace_record(
                    request_id,
                    path,
                    user_id,
                    question,
                    filters,
                    guardrail_result,
                    output_guardrail_result,
                    0,
                    BLOCKED_ANSWER,
                    [],
                    "blocked",
                    latency_ms,
                ),
                save_trace,
            )
            log_json(
                LOGGER,
                logging.WARNING,
                "rag query blocked by input guardrail",
                request_id=request_id,
                path=path,
                user_id=user_id,
                filters=filters,
                guardrail_action=guardrail_result["action"],
                guardrail_reason=guardrail_result["reason"],
                guardrail_matched_rule=guardrail_result["matchedRule"],
                output_guardrail_action=output_guardrail_result["action"],
                output_guardrail_reason=output_guardrail_result["reason"],
                output_guardrail_warnings=output_guardrail_result["warnings"],
                status="blocked",
            )
            return {
                "statusCode": 200,
                "body": _build_body(
                    request_id,
                    user_id,
                    BLOCKED_ANSWER,
                    [],
                    filters,
                    guardrail_result,
                    output_guardrail_result,
                    "blocked",
                ),
            }

        if "projectId" not in filters and "customerId" not in filters:
            log_json(
                LOGGER,
                logging.INFO,
                "rag query missing explicit scope filters",
                request_id=request_id,
                path=path,
                user_id=user_id,
                filters=filters,
                guardrail_action=guardrail_result["action"],
                guardrail_reason=guardrail_result["reason"],
                guardrail_matched_rule=guardrail_result["matchedRule"],
                output_guardrail_action=output_guardrail_result["action"],
                output_guardrail_reason=output_guardrail_result["reason"],
                output_guardrail_warnings=output_guardrail_result["warnings"],
                status="unscoped_request",
            )

        assert_filters_allowed(filters, access_context)

        repository = DocumentRepository(DOCUMENT_CHUNKS_TABLE_NAME)
        chunks = repository.list_chunks()
        eligible_chunks = _filter_chunks_by_metadata(chunks, filters)
        eligible_chunk_count = len(eligible_chunks)
        question_embedding = EmbeddingClient(EMBEDDING_MODEL_ID).embed_query(question)
        top_chunks = retrieve_top_chunks(
            question_embedding,
            eligible_chunks,
            min_similarity_score=MIN_SIMILARITY_SCORE,
        )
        sources = _serialize_sources(top_chunks)

        if not top_chunks:
            latency_ms = int((perf_counter() - started_at) * 1000)
            _save_trace(
                _build_trace_record(
                    request_id,
                    path,
                    user_id,
                    question,
                    filters,
                    guardrail_result,
                    output_guardrail_result,
                    eligible_chunk_count,
                    NO_SOURCE_ANSWER,
                    [],
                    "no_source",
                    latency_ms,
                ),
                save_trace,
            )
            log_json(
                LOGGER,
                logging.INFO,
                "rag query returned no source",
                request_id=request_id,
                path=path,
                user_id=user_id,
                model_id=BEDROCK_MODEL_ID,
                embedding_model_id=EMBEDDING_MODEL_ID,
                retrieval_mode=RETRIEVAL_MODE,
                min_similarity_score=MIN_SIMILARITY_SCORE,
                filters=filters,
                guardrail_action=guardrail_result["action"],
                guardrail_reason=guardrail_result["reason"],
                guardrail_matched_rule=guardrail_result["matchedRule"],
                output_guardrail_action=output_guardrail_result["action"],
                output_guardrail_reason=output_guardrail_result["reason"],
                output_guardrail_warnings=output_guardrail_result["warnings"],
                eligible_chunk_count=eligible_chunk_count,
                latency_ms=latency_ms,
                source_count=0,
                status="no_source",
            )
            return {
                "statusCode": 200,
                "body": _build_body(
                    request_id,
                    user_id,
                    NO_SOURCE_ANSWER,
                    [],
                    filters,
                    guardrail_result,
                    output_guardrail_result,
                    "no_source",
                ),
            }

        prompt = _build_grounded_prompt(question, top_chunks)
        answer = BedrockClient().converse(BEDROCK_MODEL_ID, prompt)
        output_guardrail_result = evaluate_output_guardrail(answer, sources)
        latency_ms = int((perf_counter() - started_at) * 1000)

        trace_record = _build_trace_record(
            request_id,
            path,
            user_id,
            question,
            filters,
            guardrail_result,
            output_guardrail_result,
            eligible_chunk_count,
            answer,
            sources,
            "completed",
            latency_ms,
        )
        _save_trace(trace_record, save_trace)

        log_json(
            LOGGER,
            logging.INFO,
            "rag query completed",
            request_id=request_id,
            path=path,
            user_id=user_id,
            model_id=BEDROCK_MODEL_ID,
            embedding_model_id=EMBEDDING_MODEL_ID,
            retrieval_mode=RETRIEVAL_MODE,
            min_similarity_score=MIN_SIMILARITY_SCORE,
            filters=filters,
            guardrail_action=guardrail_result["action"],
            guardrail_reason=guardrail_result["reason"],
            guardrail_matched_rule=guardrail_result["matchedRule"],
            output_guardrail_action=output_guardrail_result["action"],
            output_guardrail_reason=output_guardrail_result["reason"],
            output_guardrail_warnings=output_guardrail_result["warnings"],
            eligible_chunk_count=eligible_chunk_count,
            latency_ms=latency_ms,
            source_count=len(sources),
            status="completed",
        )
        return {
            "statusCode": 200,
            "body": _build_body(
                request_id,
                user_id,
                answer,
                sources,
                filters,
                guardrail_result,
                output_guardrail_result,
                "completed",
            ),
        }
    except AccessDeniedError as exc:
        log_json(
            LOGGER,
            logging.WARNING,
            "rag query access denied",
            request_id=request_id,
            path=path,
            user_id=user_id,
            filters=filters,
            guardrail_action=guardrail_result["action"],
            guardrail_reason=guardrail_result["reason"],
            guardrail_matched_rule=guardrail_result["matchedRule"],
            output_guardrail_action=output_guardrail_result["action"],
            output_guardrail_reason=output_guardrail_result["reason"],
            output_guardrail_warnings=output_guardrail_result["warnings"],
            status="denied",
            error=str(exc),
        )
        return {"statusCode": 403, "body": {"message": str(exc)}}
    except (EmbeddingInvocationError, BedrockInvocationError) as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_json(
            LOGGER,
            logging.ERROR,
            "rag invocation failed",
            request_id=request_id,
            path=path,
            user_id=user_id,
            model_id=BEDROCK_MODEL_ID,
            embedding_model_id=EMBEDDING_MODEL_ID,
            retrieval_mode=RETRIEVAL_MODE,
            min_similarity_score=MIN_SIMILARITY_SCORE,
            filters=filters,
            guardrail_action=guardrail_result["action"],
            guardrail_reason=guardrail_result["reason"],
            guardrail_matched_rule=guardrail_result["matchedRule"],
            output_guardrail_action=output_guardrail_result["action"],
            output_guardrail_reason=output_guardrail_result["reason"],
            output_guardrail_warnings=output_guardrail_result["warnings"],
            eligible_chunk_count=locals().get("eligible_chunk_count", 0),
            latency_ms=latency_ms,
            source_count=len(locals().get("sources", [])),
            status="failed",
            error=str(exc),
        )
        return {"statusCode": 502, "body": {"message": "Embedding or Bedrock invocation failed."}}
    except Exception:
        latency_ms = int((perf_counter() - started_at) * 1000)
        LOGGER.exception(
            "unexpected rag query failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": path,
                    "user_id": user_id,
                    "model_id": BEDROCK_MODEL_ID,
                    "embedding_model_id": EMBEDDING_MODEL_ID,
                    "retrieval_mode": RETRIEVAL_MODE,
                    "min_similarity_score": MIN_SIMILARITY_SCORE,
                    "filters": filters,
                    "guardrail_action": guardrail_result["action"],
                    "guardrail_reason": guardrail_result["reason"],
                    "guardrail_matched_rule": guardrail_result["matchedRule"],
                    "output_guardrail_action": output_guardrail_result["action"],
                    "output_guardrail_reason": output_guardrail_result["reason"],
                    "output_guardrail_warnings": output_guardrail_result["warnings"],
                    "eligible_chunk_count": locals().get("eligible_chunk_count", 0),
                    "latency_ms": latency_ms,
                    "source_count": len(locals().get("sources", [])),
                    "status": "failed",
                },
            },
        )
        return {"statusCode": 500, "body": {"message": "Internal server error."}}