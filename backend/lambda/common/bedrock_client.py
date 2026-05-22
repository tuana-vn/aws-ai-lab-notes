from __future__ import annotations

import boto3


class BedrockInvocationError(Exception):
    pass


class BedrockClient:
    def __init__(self) -> None:
        self._client = boto3.client("bedrock-runtime")

    def converse(self, model_id: str, user_message: str) -> str:
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
            return response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            raise BedrockInvocationError(
                f"Bedrock invocation failed for model_id={model_id}: {exc}"
            ) from exc