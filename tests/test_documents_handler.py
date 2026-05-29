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
    def test_successful_ingestion_stages_then_promotes_new_chunks(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one", "chunk two"]
        embedding_client = embedding_client_class.return_value
        embedding_client.embed_document.side_effect = [[0.1, 0.2], [0.3, 0.4]]
        repository = document_repository_class.return_value
        repository.list_chunks_by_document_id.return_value = [
            {"document_id": "doc-123", "chunk_id": "chunk-0001"},
            {"document_id": "doc-123", "chunk_id": "chunk-0002"},
        ]
        repository.count_chunks_by_document_version.return_value = 2

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
        self.assertEqual(body, {"documentId": "doc-123", "title": "Incident Guide", "chunkCount": 2, "status": "indexed"})

        repository.delete_chunks_by_document_id.assert_not_called()
        repository.save_chunks.assert_called_once()
        repository.count_chunks_by_document_version.assert_called_once_with("doc-123", unittest.mock.ANY)
        repository.mark_chunks_active_by_document_version.assert_called_once_with(
            "doc-123",
            unittest.mock.ANY,
        )
        repository.mark_chunks_obsolete_by_document_id.assert_called_once_with(
            "doc-123",
            except_document_version=unittest.mock.ANY,
        )
        saved_chunks = repository.save_chunks.call_args.args[0]
        self.assertEqual(len(saved_chunks), 2)
        self.assertEqual(saved_chunks[0]["document_id"], "doc-123")
        self.assertEqual(saved_chunks[0]["chunk_id"], f"{saved_chunks[0]['document_version']}#chunk-0001")
        self.assertEqual(saved_chunks[1]["chunk_id"], f"{saved_chunks[1]['document_version']}#chunk-0002")
        self.assertNotEqual(saved_chunks[0]["chunk_id"], "chunk-0001")
        self.assertEqual(saved_chunks[0]["project_id"], "learning")
        self.assertEqual(saved_chunks[0]["customer_id"], "internal")
        self.assertEqual(saved_chunks[0]["document_type"], "runbook")
        self.assertIn("document_version", saved_chunks[0])
        self.assertIn("content_hash", saved_chunks[0])
        self.assertIn("ingestion_timestamp", saved_chunks[0])
        self.assertEqual(saved_chunks[0]["chunk_count"], 2)
        self.assertEqual(saved_chunks[0]["replacement_mode"], "staged_replace")
        self.assertEqual(saved_chunks[0]["version_status"], "staged")
        self.assertEqual(saved_chunks[0]["document_version"], saved_chunks[1]["document_version"])
        self.assertEqual(saved_chunks[0]["content_hash"], saved_chunks[1]["content_hash"])
        self.assertEqual(
            repository.method_calls,
            [
                unittest.mock.call.list_chunks_by_document_id("doc-123"),
                unittest.mock.call.save_chunks(saved_chunks),
                unittest.mock.call.count_chunks_by_document_version("doc-123", saved_chunks[0]["document_version"]),
                unittest.mock.call.mark_chunks_active_by_document_version(
                    "doc-123",
                    saved_chunks[0]["document_version"],
                ),
                unittest.mock.call.mark_chunks_obsolete_by_document_id(
                    "doc-123",
                    except_document_version=saved_chunks[0]["document_version"],
                ),
            ],
        )

    @patch.object(handler, "DocumentRepository")
    @patch.object(handler, "EmbeddingClient")
    @patch.object(handler, "chunk_document")
    def test_old_chunks_are_not_touched_when_staged_save_fails(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one"]
        embedding_client_class.return_value.embed_document.return_value = [0.1, 0.2]
        repository = document_repository_class.return_value
        repository.list_chunks_by_document_id.return_value = [{"document_id": "doc-123", "chunk_id": "chunk-0001"}]
        repository.save_chunks.side_effect = RuntimeError("put failed")

        response = handler.lambda_handler(
            _build_event(
                {
                    "documentId": "doc-123",
                    "title": "Incident Guide",
                    "content": "First paragraph",
                }
            ),
            None,
        )

        self.assertEqual(response["statusCode"], 500)
        repository.delete_chunks_by_document_id.assert_not_called()
        repository.mark_chunks_obsolete_by_document_id.assert_not_called()
        repository.mark_chunks_active_by_document_version.assert_not_called()

    @patch.object(handler, "DocumentRepository")
    @patch.object(handler, "EmbeddingClient")
    @patch.object(handler, "chunk_document")
    def test_activation_failure_marks_new_chunks_failed_without_touching_previous_chunks(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one"]
        embedding_client_class.return_value.embed_document.return_value = [0.1, 0.2]
        repository = document_repository_class.return_value
        repository.list_chunks_by_document_id.return_value = [{"document_id": "doc-123", "chunk_id": "chunk-0001"}]
        repository.count_chunks_by_document_version.return_value = 1
        repository.mark_chunks_active_by_document_version.side_effect = RuntimeError("activate failed")

        response = handler.lambda_handler(
            _build_event(
                {
                    "documentId": "doc-123",
                    "title": "Incident Guide",
                    "content": "First paragraph",
                }
            ),
            None,
        )

        self.assertEqual(response["statusCode"], 500)
        saved_chunks = repository.save_chunks.call_args.args[0]
        document_version = saved_chunks[0]["document_version"]
        repository.mark_chunks_failed_by_document_version.assert_called_once_with("doc-123", document_version)
        repository.mark_chunks_obsolete_by_document_id.assert_not_called()

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
        document_repository_class.return_value.list_chunks_by_document_id.return_value = []
        document_repository_class.return_value.count_chunks_by_document_version.return_value = 1

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
        self.assertEqual(saved_chunks[0]["chunk_id"], "v-2026-05-29#chunk-0001")
        self.assertEqual(json.loads(response["body"])["status"], "indexed")

    @patch.object(handler, "DocumentRepository")
    @patch.object(handler, "EmbeddingClient")
    @patch.object(handler, "chunk_document")
    def test_same_document_same_content_replay_returns_indexed_without_rewrite(
        self,
        chunk_document,
        embedding_client_class,
        document_repository_class,
    ):
        chunk_document.return_value = ["chunk one", "chunk two"]
        repository = document_repository_class.return_value
        content_hash = handler._compute_content_hash("First paragraph\n\nSecond paragraph")
        document_version = handler._resolve_document_version(None, content_hash)
        repository.list_chunks_by_document_id.return_value = [
            {
                "document_id": "doc-123",
                "chunk_id": f"{document_version}#chunk-0001",
                "document_version": document_version,
                "content_hash": content_hash,
                "version_status": "active",
            },
            {
                "document_id": "doc-123",
                "chunk_id": f"{document_version}#chunk-0002",
                "document_version": document_version,
                "content_hash": content_hash,
                "version_status": "active",
            },
        ]

        response = handler.lambda_handler(
            _build_event(
                {
                    "documentId": "doc-123",
                    "title": "Incident Guide",
                    "content": "First paragraph\n\nSecond paragraph",
                }
            ),
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]),
            {"documentId": "doc-123", "title": "Incident Guide", "chunkCount": 2, "status": "indexed"},
        )
        embedding_client_class.assert_not_called()
        repository.save_chunks.assert_not_called()
        repository.count_chunks_by_document_version.assert_not_called()
        repository.mark_chunks_active_by_document_version.assert_not_called()
        repository.mark_chunks_obsolete_by_document_id.assert_not_called()

    def test_content_hash_is_stable_for_same_content(self):
        hash_one = handler._compute_content_hash("hello\r\nworld\n")
        hash_two = handler._compute_content_hash("hello\nworld")

        self.assertEqual(hash_one, hash_two)


if __name__ == "__main__":
    unittest.main()