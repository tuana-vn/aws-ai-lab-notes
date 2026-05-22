from __future__ import annotations


def chunk_document(content: str, max_chunk_length: int = 800) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        paragraphs = [content.strip()]

    chunks: list[str] = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(paragraph) <= max_chunk_length:
            candidate = paragraph if not current_chunk else f"{current_chunk}\n\n{paragraph}"
            if len(candidate) <= max_chunk_length:
                current_chunk = candidate
            else:
                chunks.append(current_chunk)
                current_chunk = paragraph
            continue

        if current_chunk:
            chunks.append(current_chunk)
            current_chunk = ""

        start_index = 0
        while start_index < len(paragraph):
            chunks.append(paragraph[start_index : start_index + max_chunk_length].strip())
            start_index += max_chunk_length

    if current_chunk:
        chunks.append(current_chunk)

    return [chunk for chunk in chunks if chunk]