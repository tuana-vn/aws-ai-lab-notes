from __future__ import annotations

import json
import os

import boto3


class EmbeddingInvocationError(Exception):
    pass


class EmbeddingClient:
    def __init__(self, model_id: str | None = None) -> None:
        self._client = boto3.client("bedrock-runtime")
        self.model_id = model_id or os.environ.get(
            "EMBEDDING_MODEL_ID", "cohere.embed-english-v3"
        )

    def embed_document(self, text: str) -> list[float]:
        return self._embed_text(text, input_type="search_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text, input_type="search_query")

    def _embed_text(self, text: str, input_type: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingInvocationError("Embedding text must be a non-empty string.")

        request_body = {
            "texts": [text],
            "input_type": input_type,
            "truncate": "END",
        }

        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )
        except Exception as exc:
            raise EmbeddingInvocationError(
                f"Embedding invocation failed for model_id={self.model_id}: {exc}"
            ) from exc

        try:
            payload = json.loads(response["body"].read())
            embeddings = payload["embeddings"]
            embedding = embeddings[0]
            if not isinstance(embedding, list) or not embedding:
                raise TypeError("Embedding vector is missing or empty.")
            return [float(value) for value in embedding]
        except Exception as exc:
            raise EmbeddingInvocationError(
                f"Invalid embedding response for model_id={self.model_id}: {exc}"
            ) from exc
