from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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

from documents import handler


def _build_event(body: dict[str, object]) -> dict:
    return {
        "rawPath": "/documents",
        "path": "/documents",
        "body": json.dumps(body),
    }


class DocumentsHandlerMetadataTests(unittest.TestCase):
    @patch.object(handler, "DocumentRepository")
    @patch.object(handler, "EmbeddingClient")
    @patch.object(handler, "chunk_document")
    def test_default_document_version_and_metadata_are_added_to_chunk_records(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one", "chunk two"]
        embedding_client = embedding_client_class.return_value
        embedding_client.embed_document.side_effect = [[0.1, 0.2], [0.3, 0.4]]
        repository = document_repository_class.return_value

        response = handler.lambda_handler(
            _build_event(
                {
                    "documentId": "doc-123",
                    "title": "Incident Guide",
                    "content": "First paragraph\n\nSecond paragraph",
                    "projectId": "learning",
                    "customerId": "internal",
                    "documentType": "runbook",
                }
            ),
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(
            body,
            {
                "documentId": "doc-123",
                "title": "Incident Guide",
                "chunkCount": 2,
                "status": "indexed",
            },
        )

        repository.delete_chunks_by_document_id.assert_called_once_with("doc-123")
        repository.save_chunks.assert_called_once()
        saved_chunks = repository.save_chunks.call_args.args[0]
        self.assertEqual(len(saved_chunks), 2)
        self.assertEqual(saved_chunks[0]["document_id"], "doc-123")
        self.assertEqual(saved_chunks[0]["project_id"], "learning")
        self.assertEqual(saved_chunks[0]["customer_id"], "internal")
        self.assertEqual(saved_chunks[0]["document_type"], "runbook")
        self.assertIn("document_version", saved_chunks[0])
        self.assertIn("content_hash", saved_chunks[0])
        self.assertIn("ingestion_timestamp", saved_chunks[0])
        self.assertEqual(saved_chunks[0]["chunk_count"], 2)
        self.assertEqual(saved_chunks[0]["replacement_mode"], "direct_replace")
        self.assertEqual(saved_chunks[0]["document_version"], saved_chunks[1]["document_version"])
        self.assertEqual(saved_chunks[0]["content_hash"], saved_chunks[1]["content_hash"])

    @patch.object(handler, "DocumentRepository")
    @patch.object(handler, "EmbeddingClient")
    @patch.object(handler, "chunk_document")
    def test_provided_version_is_preserved(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one"]
        embedding_client_class.return_value.embed_document.return_value = [0.1, 0.2]

        response = handler.lambda_handler(
            _build_event(
                {
                    "documentId": "doc-123",
                    "title": "Incident Guide",
                    "content": "First paragraph",
                    "version": "v-2026-05-29",
                }
            ),
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        saved_chunks = document_repository_class.return_value.save_chunks.call_args.args[0]
        self.assertEqual(saved_chunks[0]["document_version"], "v-2026-05-29")

    def test_content_hash_is_stable_for_same_content(self):
        hash_one = handler._compute_content_hash("hello\r\nworld\n")
        hash_two = handler._compute_content_hash("hello\nworld")

        self.assertEqual(hash_one, hash_two)


if __name__ == "__main__":
    unittest.main()