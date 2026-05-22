from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value


def lookup_trace(request_id: str, table_name: str) -> dict | None:
    table = boto3.resource("dynamodb").Table(table_name)
    response = table.get_item(Key={"request_id": request_id})
    item = response.get("Item")
    if not item:
        return None

    return _normalize_value(item)