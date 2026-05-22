from __future__ import annotations


def evaluate_output_guardrail(answer: str, sources: list[dict]) -> dict:
    if not answer.strip():
        return {
            "action": "warn",
            "reason": "empty_answer",
            "warnings": ["empty_answer"],
        }

    if sources and "documentId=" not in answer and "Source" not in answer:
        return {
            "action": "warn",
            "reason": "missing_source_reference",
            "warnings": ["answer_does_not_reference_sources"],
        }

    return {
        "action": "allow",
        "reason": "valid_grounded_answer",
        "warnings": [],
    }