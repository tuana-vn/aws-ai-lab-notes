import json
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from common.bedrock_client import BedrockClient, BedrockInvocationError
from common.document_repository import DocumentRepository
from common.logging import get_logger, log_json
from common.response import json_response
from common.retrieval import retrieve_top_chunks
from common.trace_repository import TraceRepository

LOGGER = get_logger(__name__)
DOCUMENT_CHUNKS_TABLE_NAME = os.environ.get("DOCUMENT_CHUNKS_TABLE_NAME", "")
TRACE_TABLE_NAME = os.environ.get("TRACE_TABLE_NAME", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "apac.amazon.nova-lite-v1:0")
NO_SOURCE_ANSWER = "I do not know based on the available documents."


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
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Field 'question' is required and must be a non-empty string.")

    return question.strip()


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
        }
        for chunk in chunks
    ]


def lambda_handler(event, context):
    request_id = str(uuid4())
    path = event.get("rawPath") or event.get("path") or "/rag/query"

    try:
        question = _parse_body(event)
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
        repository = DocumentRepository(DOCUMENT_CHUNKS_TABLE_NAME)
        chunks = repository.list_chunks()
        top_chunks = retrieve_top_chunks(question, chunks)
        sources = _serialize_sources(top_chunks)

        if not top_chunks:
            latency_ms = int((perf_counter() - started_at) * 1000)
            TraceRepository(TRACE_TABLE_NAME).save_trace(
                {
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": path,
                    "question": question,
                    "answer_preview": NO_SOURCE_ANSWER[:500],
                    "model_id": BEDROCK_MODEL_ID,
                    "source_count": 0,
                    "sources": [],
                    "status": "no_source",
                    "latency_ms": latency_ms,
                }
            )
            log_json(
                LOGGER,
                logging.INFO,
                "rag query returned no source",
                request_id=request_id,
                path=path,
                model_id=BEDROCK_MODEL_ID,
                latency_ms=latency_ms,
                source_count=0,
                status="no_source",
            )
            return json_response(
                200,
                {
                    "requestId": request_id,
                    "answer": NO_SOURCE_ANSWER,
                    "sources": [],
                    "status": "no_source",
                },
            )

        prompt = _build_grounded_prompt(question, top_chunks)
        answer = BedrockClient().converse(BEDROCK_MODEL_ID, prompt)
        latency_ms = int((perf_counter() - started_at) * 1000)

        trace_record = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "question": question,
            "answer_preview": answer[:500],
            "model_id": BEDROCK_MODEL_ID,
            "source_count": len(sources),
            "sources": sources,
            "status": "completed",
            "latency_ms": latency_ms,
        }
        TraceRepository(TRACE_TABLE_NAME).save_trace(trace_record)

        log_json(
            LOGGER,
            logging.INFO,
            "rag query completed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
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
                "status": "completed",
            },
        )
    except BedrockInvocationError as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        source_count = len(locals().get("sources", []))
        log_json(
            LOGGER,
            logging.ERROR,
            "bedrock rag invocation failed",
            request_id=request_id,
            path=path,
            model_id=BEDROCK_MODEL_ID,
            latency_ms=latency_ms,
            source_count=source_count,
            status="failed",
            error=str(exc),
        )
        return json_response(502, {"message": "Bedrock invocation failed."})
    except Exception:
        latency_ms = int((perf_counter() - started_at) * 1000)
        source_count = len(locals().get("sources", []))
        LOGGER.exception(
            "unexpected rag query failure",
            extra={
                "request_id": request_id,
                "extra_fields": {
                    "path": path,
                    "model_id": BEDROCK_MODEL_ID,
                    "latency_ms": latency_ms,
                    "source_count": source_count,
                    "status": "failed",
                },
            },
        )
        return json_response(500, {"message": "Internal server error."})