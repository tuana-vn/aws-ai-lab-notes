from __future__ import annotations

from typing import Any

import boto3


class TraceRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def save_trace(self, trace_record: dict[str, Any]) -> None:
        self._table.put_item(Item=trace_record)
