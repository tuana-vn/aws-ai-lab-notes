from __future__ import annotations

import boto3


class BedrockInvocationError(Exception):
    pass


class BedrockClient:
    def __init__(self) -> None:
        self._client = boto3.client("bedrock-runtime")

    def _extract_usage(self, response: dict, model_id: str) -> dict:
        usage = response.get("usage") or {}
        metrics = response.get("metrics") or {}

        normalized_usage = {}
        if usage.get("inputTokens") is not None:
            normalized_usage["inputTokens"] = usage["inputTokens"]
        if usage.get("outputTokens") is not None:
            normalized_usage["outputTokens"] = usage["outputTokens"]
        if usage.get("totalTokens") is not None:
            normalized_usage["totalTokens"] = usage["totalTokens"]
        if metrics.get("latencyMs") is not None:
            normalized_usage["bedrockLatencyMs"] = metrics["latencyMs"]
        return normalized_usage

    def converse(self, model_id: str, user_message: str) -> dict:
        try:
            response = self._client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_message}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.2,
                },
            )
            return {
                "answer": response["output"]["message"]["content"][0]["text"],
                "usage": self._extract_usage(response, model_id),
            }
        except Exception as exc:
            raise BedrockInvocationError(
                f"Bedrock invocation failed for model_id={model_id}: {exc}"
            ) from exc