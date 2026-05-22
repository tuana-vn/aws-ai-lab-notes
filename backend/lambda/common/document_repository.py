from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


class DocumentRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def _serialize_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        serialized_chunk = dict(chunk)
        embedding = serialized_chunk.get("embedding")
        if isinstance(embedding, list):
            serialized_chunk["embedding"] = [Decimal(str(value)) for value in embedding]
        return serialized_chunk

    def _deserialize_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        deserialized_chunk = dict(chunk)
        embedding = deserialized_chunk.get("embedding")
        if isinstance(embedding, list):
            deserialized_chunk["embedding"] = [float(value) for value in embedding]
        return deserialized_chunk

    def delete_chunks_by_document_id(self, document_id: str) -> None:
        # This query-and-delete flow is acceptable for a learning PoC because it is easy to follow.
        # In production, re-indexing should use a more deliberate bulk replacement strategy.
        response = self._table.query(KeyConditionExpression=Key("document_id").eq(document_id))
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = self._table.query(
                KeyConditionExpression=Key("document_id").eq(document_id),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        for item in items:
            self._table.delete_item(
                Key={
                    "document_id": item["document_id"],
                    "chunk_id": item["chunk_id"],
                }
            )

    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            self._table.put_item(Item=self._serialize_chunk(chunk))

    def list_chunks(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response = self._table.scan()
        items.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            response = self._table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))

        return [self._deserialize_chunk(item) for item in items]