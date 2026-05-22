from __future__ import annotations

import re
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


def retrieve_top_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    question_tokens = tokenize(question)
    scored_chunks: list[tuple[int, int, dict[str, Any]]] = []

    for chunk in chunks:
        chunk_tokens = tokenize(str(chunk.get("content", "")))
        overlap_score = len(question_tokens & chunk_tokens)
        if overlap_score <= 0:
            continue

        chunk_index = int(chunk.get("chunk_index", 0))
        scored_chunks.append((overlap_score, -chunk_index, chunk))

    scored_chunks.sort(key=lambda item: (-item[0], -item[1], item[2].get("chunk_id", "")))
    return [item[2] for item in scored_chunks[:limit]]