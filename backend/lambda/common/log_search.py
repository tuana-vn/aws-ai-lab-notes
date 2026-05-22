from __future__ import annotations

from datetime import datetime, timedelta, timezone

import boto3


SUPPORTED_PRESETS = {"raw", "blocked", "no_source", "errors"}
MESSAGE_PREVIEW_LIMIT = 500


def _to_iso8601(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _message_preview(message: str) -> str:
    compact_message = str(message).strip()
    if len(compact_message) <= MESSAGE_PREVIEW_LIMIT:
        return compact_message
    return compact_message[:MESSAGE_PREVIEW_LIMIT]


def _build_filter_pattern(preset: str) -> str:
    if preset == "blocked":
        return '"blocked"'
    if preset == "no_source":
        return '"no_source"'
    return ""


def _matches_error_preset(message: str) -> bool:
    normalized = str(message).casefold()
    return "error" in normalized or "failed" in normalized


def _format_events(events: list[dict], preset: str, limit: int) -> list[dict]:
    formatted_events = []
    for event in events:
        message = event.get("message", "")
        if preset == "errors" and not _matches_error_preset(message):
            continue

        timestamp = event.get("timestamp")
        if not isinstance(timestamp, int):
            continue

        formatted_events.append(
            {
                "timestamp": _to_iso8601(timestamp),
                "messagePreview": _message_preview(message),
            }
        )
        if len(formatted_events) >= limit:
            break

    return formatted_events


def search_logs(log_group_name: str, preset: str, minutes: int, limit: int = 10) -> dict:
    client = boto3.client("logs")
    start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    filter_pattern = _build_filter_pattern(preset)
    request = {
        "logGroupName": log_group_name,
        "startTime": int(start_time.timestamp() * 1000),
        "limit": max(limit, 1) if preset != "errors" else max(limit * 5, 20),
    }
    if filter_pattern:
        request["filterPattern"] = filter_pattern

    response = client.filter_log_events(**request)
    events = _format_events(response.get("events", []), preset, max(limit, 1))

    return {
        "preset": preset,
        "minutes": minutes,
        "matchedEvents": len(events),
        "events": events,
    }