from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAMBDA_ROOT = REPOSITORY_ROOT / "backend" / "lambda"
if str(LAMBDA_ROOT) not in sys.path:
    sys.path.insert(0, str(LAMBDA_ROOT))

if "boto3" not in sys.modules:
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda *args, **kwargs: None
    sys.modules["boto3"] = fake_boto3

from common.bedrock_client import BedrockClient


class BedrockClientUsageExtractionTests(unittest.TestCase):
    def test_extract_usage_returns_usage_and_metrics_without_model_id(self):
        client = BedrockClient.__new__(BedrockClient)

        usage = client._extract_usage(
            {
                "usage": {
                    "inputTokens": 123,
                    "outputTokens": 45,
                    "totalTokens": 168,
                },
                "metrics": {
                    "latencyMs": 789,
                },
            },
            "apac.amazon.nova-lite-v1:0",
        )

        self.assertEqual(
            usage,
            {
                "inputTokens": 123,
                "outputTokens": 45,
                "totalTokens": 168,
                "bedrockLatencyMs": 789,
            },
        )
        self.assertNotIn("modelId", usage)


if __name__ == "__main__":
    unittest.main()