from __future__ import annotations

from typing import Any

from common.vector_math import cosine_similarity


def retrieve_top_chunks(
    question_embedding: list[float],
    chunks: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    scored_chunks: list[tuple[float, int, str, dict[str, Any]]] = []

    for chunk in chunks:
        raw_embedding = chunk.get("embedding")
        if not isinstance(raw_embedding, list):
            continue

        try:
            chunk_embedding = [float(value) for value in raw_embedding]
        except (TypeError, ValueError):
            continue

        similarity = cosine_similarity(question_embedding, chunk_embedding)
        if similarity <= 0.0:
            continue

        chunk_index = int(chunk.get("chunk_index", 0))
        scored_chunk = dict(chunk)
        scored_chunk["similarity"] = round(similarity, 4)
        scored_chunks.append(
            (similarity, -chunk_index, str(chunk.get("chunk_id", "")), scored_chunk)
        )

    scored_chunks.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in scored_chunks[:limit]]