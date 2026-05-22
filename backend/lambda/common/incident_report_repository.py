from __future__ import annotations

import boto3

from common.approval_repository import _deserialize_value, _serialize_value


class IncidentReportRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def create_report(self, record: dict) -> None:
        self._table.put_item(Item=_serialize_value(record))

    def get_report(self, report_id: str) -> dict | None:
        response = self._table.get_item(Key={"report_id": report_id})
        item = response.get("Item")
        if not item:
            return None
        return _deserialize_value(item)