from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3


def _serialize_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _deserialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _deserialize_value(item) for key, item in value.items()}
    return value


class ApprovalRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def create_approval(self, record: dict) -> None:
        self._table.put_item(Item=_serialize_value(record))

    def get_approval(self, approval_id: str) -> dict | None:
        response = self._table.get_item(Key={"approval_id": approval_id})
        item = response.get("Item")
        if not item:
            return None
        return _deserialize_value(item)

    def update_decision(self, approval_id: str, decision: str, decided_by: str, comment: str | None) -> dict:
        status = "approved" if decision == "approved" else "rejected"
        execution_status = "approved_not_executed" if decision == "approved" else "rejected_not_executed"
        response = self._table.update_item(
            Key={"approval_id": approval_id},
            UpdateExpression=(
                "SET #status = :status, #decision = :decision, decided_by = :decided_by, "
                "decided_at = :decided_at, #comment = :comment, execution_status = :execution_status"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#decision": "decision",
                "#comment": "comment",
            },
            ExpressionAttributeValues=_serialize_value(
                {
                    ":status": status,
                    ":decision": decision,
                    ":decided_by": decided_by,
                    ":decided_at": datetime.now(timezone.utc).isoformat(),
                    ":comment": comment,
                    ":execution_status": execution_status,
                }
            ),
            ReturnValues="ALL_NEW",
        )
        return _deserialize_value(response.get("Attributes", {}))