from __future__ import annotations

import re


REQUEST_ID_PATTERN = re.compile(
    r'"(?:request_id|requestId)"\s*:\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"'
)


def extract_request_ids_from_log_events(events: list[dict], limit: int = 3) -> list[str]:
    request_ids: list[str] = []
    seen_request_ids: set[str] = set()

    for event in events:
        message_preview = event.get("messagePreview", "")
        if not isinstance(message_preview, str):
            continue

        for match in REQUEST_ID_PATTERN.finditer(message_preview):
            request_id = match.group(1)
            if request_id in seen_request_ids:
                continue
            seen_request_ids.add(request_id)
            request_ids.append(request_id)
            if len(request_ids) >= limit:
                return request_ids

    return request_ids


def summarize_investigation(log_summary: dict, inspected_traces: list[dict]) -> str:
    matched_events = int(log_summary.get("matchedEvents", 0) or 0)
    minutes = int(log_summary.get("minutes", 0) or 0)

    if matched_events == 0:
        return f"No blocked log events were found in the last {minutes} minutes."

    if not inspected_traces:
        return (
            f"Found {matched_events} blocked log event(s) in the last {minutes} minutes, "
            "but no request IDs could be extracted from log previews."
        )

    reasons: list[str] = []
    for trace in inspected_traces:
        if trace.get("status") != "blocked":
            continue
        reason = trace.get("guardrailReason")
        if isinstance(reason, str) and reason and reason not in reasons:
            reasons.append(reason)

    if reasons:
        reasons_text = ", ".join(reasons)
        return (
            f"Found {matched_events} blocked log event(s). Inspected {len(inspected_traces)} trace record(s). "
            f"Common blocked reasons: {reasons_text}."
        )

    return (
        f"Found {matched_events} blocked log event(s). Inspected {len(inspected_traces)} trace record(s). "
        "No common blocked reason was identified."
    )