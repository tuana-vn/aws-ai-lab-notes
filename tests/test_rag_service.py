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
    fake_boto3.resource = lambda *args, **kwargs: None
    sys.modules["boto3"] = fake_boto3

if "boto3.dynamodb" not in sys.modules:
    sys.modules["boto3.dynamodb"] = types.ModuleType("boto3.dynamodb")

if "boto3.dynamodb.conditions" not in sys.modules:
    fake_conditions = types.ModuleType("boto3.dynamodb.conditions")

    class _FakeKey:
        def __init__(self, *_args, **_kwargs):
            pass

        def eq(self, *_args, **_kwargs):
            return None

    fake_conditions.Key = _FakeKey
    sys.modules["boto3.dynamodb.conditions"] = fake_conditions

from common import rag_service


class RagServiceVersionStatusFilterTests(unittest.TestCase):
    def test_staged_obsolete_and_failed_chunks_are_not_retrievable(self):
        chunks = [
            {"document_id": "doc-1", "chunk_id": "v2#chunk-1", "version_status": "active"},
            {"document_id": "doc-1", "chunk_id": "v2#chunk-2", "version_status": "staged"},
            {"document_id": "doc-1", "chunk_id": "v1#chunk-3", "version_status": "obsolete"},
            {"document_id": "doc-1", "chunk_id": "v3#chunk-4", "version_status": "failed"},
        ]

        retrievable_chunks = rag_service._filter_retrievable_chunks(chunks)

        self.assertEqual(retrievable_chunks, [{"document_id": "doc-1", "chunk_id": "v2#chunk-1", "version_status": "active"}])

    def test_legacy_chunks_without_version_status_remain_retrievable(self):
        chunks = [
            {"document_id": "doc-1", "chunk_id": "chunk-1"},
            {"document_id": "doc-2", "chunk_id": "v2#chunk-2", "versionStatus": "active"},
            {"document_id": "doc-3", "chunk_id": "v3#chunk-3", "version_status": "staged"},
        ]

        retrievable_chunks = rag_service._filter_retrievable_chunks(chunks)

        self.assertEqual(
            retrievable_chunks,
            [
                {"document_id": "doc-1", "chunk_id": "chunk-1"},
                {"document_id": "doc-2", "chunk_id": "v2#chunk-2", "versionStatus": "active"},
            ],
        )


if __name__ == "__main__":
    unittest.main()