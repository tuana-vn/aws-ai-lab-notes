from __future__ import annotations

from math import sqrt


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(left * right for left, right in zip(a, b))
    magnitude_a = sqrt(sum(value * value for value in a))
    magnitude_b = sqrt(sum(value * value for value in b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)
