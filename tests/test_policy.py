from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LAMBDA_ROOT = REPOSITORY_ROOT / "backend" / "lambda"
if str(LAMBDA_ROOT) not in sys.path:
    sys.path.insert(0, str(LAMBDA_ROOT))

from common.policy import AccessContext, AccessDeniedError, assert_filters_allowed, resolve_access_context


def _build_event(headers: dict[str, str] | None = None) -> dict:
    return {"headers": headers or {}}


class ResolveAccessContextTests(unittest.TestCase):
    def test_resolve_access_context_builds_trusted_header_context(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-User-Id": "user-learning",
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        self.assertIsInstance(access_context, AccessContext)
        self.assertEqual(access_context.user_id, "user-learning")
        self.assertEqual(access_context.principal_id, "user-learning")
        self.assertEqual(access_context.auth_source, "trusted_headers")
        self.assertEqual(access_context.allowed_project_ids, ["learning"])
        self.assertEqual(access_context.allowed_customer_ids, ["internal"])
        self.assertEqual(access_context.scopes, [])
        self.assertEqual(access_context.groups, [])

    def test_default_user_when_header_missing(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        self.assertEqual(access_context.user_id, "anonymous")
        self.assertEqual(access_context.principal_id, "anonymous")

    def test_case_insensitive_header_names(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "x-user-id": "user-learning",
                    "x-allowed-project-ids": "learning",
                    "x-allowed-customer-ids": "internal",
                }
            )
        )

        self.assertEqual(access_context.user_id, "user-learning")
        self.assertEqual(access_context.allowed_project_ids, ["learning"])
        self.assertEqual(access_context.allowed_customer_ids, ["internal"])

    def test_comma_separated_headers_with_spaces(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-User-Id": "user-learning",
                    "X-Allowed-Project-Ids": " learning, alpha , beta ",
                    "X-Allowed-Customer-Ids": " internal, customer-a ",
                }
            )
        )

        self.assertEqual(access_context.allowed_project_ids, ["learning", "alpha", "beta"])
        self.assertEqual(access_context.allowed_customer_ids, ["internal", "customer-a"])

    def test_missing_allowed_scope_headers_resolve_to_empty_lists(self):
        access_context = resolve_access_context(_build_event({"X-User-Id": "user-learning"}))

        self.assertEqual(access_context.allowed_project_ids, [])
        self.assertEqual(access_context.allowed_customer_ids, [])

    def test_empty_allowed_scope_headers_resolve_to_empty_lists(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-User-Id": "user-learning",
                    "X-Allowed-Project-Ids": "   ",
                    "X-Allowed-Customer-Ids": "",
                }
            )
        )

        self.assertEqual(access_context.allowed_project_ids, [])
        self.assertEqual(access_context.allowed_customer_ids, [])


class AssertFiltersAllowedTests(unittest.TestCase):
    def test_allowed_project_and_customer_scope(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        assert_filters_allowed(
            {"projectId": "learning", "customerId": "internal"},
            access_context,
        )

    def test_denied_project(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"projectId": "other-project"}, access_context)

    def test_denied_customer(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"customerId": "other-customer"}, access_context)

    def test_missing_allowed_project_with_requested_project_denies(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"projectId": "learning"}, access_context)

    def test_missing_allowed_customer_with_requested_customer_denies(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"customerId": "internal"}, access_context)

    def test_empty_allowed_project_header_with_requested_project_denies(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "   ",
                    "X-Allowed-Customer-Ids": "internal",
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"projectId": "learning"}, access_context)

    def test_empty_allowed_customer_header_with_requested_customer_denies(self):
        access_context = resolve_access_context(
            _build_event(
                {
                    "X-Allowed-Project-Ids": "learning",
                    "X-Allowed-Customer-Ids": "", 
                }
            )
        )

        with self.assertRaises(AccessDeniedError):
            assert_filters_allowed({"customerId": "internal"}, access_context)


if __name__ == "__main__":
    unittest.main()