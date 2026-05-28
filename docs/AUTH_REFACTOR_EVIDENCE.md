# Auth Refactor Evidence

## Purpose

This document captures evidence for the Phase 8B `AccessContext` refactor.

The goal of the refactor was to preserve the current learning-mode trusted-header behavior while making the backend policy contract explicit and fail closed when requested scope is missing or empty.

This document is evidence-oriented. It does not claim that Cognito, JWT validation, or API Gateway authorizer infrastructure has been implemented.

## Refactor Summary

- An internal `AccessContext` abstraction was introduced for backend policy evaluation.
- `auth_source` remains `trusted_headers`.
- Current learning-mode headers are still accepted.
- Missing or empty allowed scope now fails closed when a request includes `projectId` or `customerId` filters.
- No Cognito, JWT, or authorizer code is implemented yet.

## Files Changed

At the time this document was generated, `git diff --name-only` and `git status --short` produced no output in the current workspace. Populate this table from the Phase 8B commit or PR if a file-level inventory is needed.

| File | Change | Why it matters |
| --- | --- | --- |
| `backend/lambda/common/policy.py` | Introduced `AccessContext`, kept trusted-header resolver, and changed missing/empty allowed scope to fail closed when requested filters are present. | Creates the internal policy contract needed before JWT/authorizer integration. |
| `backend/lambda/common/rag_service.py` | Uses `AccessContext` from `resolve_access_context(event)` for RAG policy evaluation and trace user context. | Keeps RAG policy checks behind a stable abstraction. |
| `backend/lambda/agent_run/handler.py` | Reads user context through `resolve_access_context(event)` instead of assuming raw header structure directly. | Keeps agent trace/user behavior aligned with the shared policy abstraction. |
| `tests/test_policy.py` | Adds unit coverage for allowed, denied, fail-closed, comma-separated, case-insensitive, and anonymous-user cases. | Protects the security-sensitive policy refactor from regression. |

## Behavior Matrix

| Scenario | Headers | Filters | Expected result | Evidence command/result |
| --- | --- | --- | --- | --- |
| 1. allowed project/customer scope | `X-User-Id: user-learning` `X-Allowed-Project-Ids: learning` `X-Allowed-Customer-Ids: internal` | `projectId=learning` `customerId=internal` | Request is allowed. RAG path may return `200` with `status=completed` or another non-policy result depending on content. | Runtime: run allowed curl below and capture `HTTP_STATUS` plus `jq '.status'`. Local unit evidence: `python -m unittest tests.test_policy` passed. |
| 2. denied project scope | `X-User-Id: user-learning` `X-Allowed-Project-Ids: learning` `X-Allowed-Customer-Ids: internal` | `projectId=other-project` | Request is denied before retrieval with HTTP `403`. | Runtime: run mismatched-project curl below and capture denial body. Existing eval artifact includes policy-denied cases. |
| 3. denied customer scope | `X-User-Id: user-learning` `X-Allowed-Project-Ids: learning` `X-Allowed-Customer-Ids: internal` | `customerId=other-customer` | Request is denied before retrieval with HTTP `403`. | Local unit evidence: `python -m unittest tests.test_policy` passed for denied customer scope. Optional runtime capture can be added with a customer mismatch request. |
| 4. missing allowed project with requested project | `X-User-Id: user-learning` and no `X-Allowed-Project-Ids` | `projectId=learning` | Request is denied because missing allowed project scope now fails closed. | Runtime: run fail-closed no-allowed-header curl below. Local unit evidence: `python -m unittest tests.test_policy` passed. |
| 5. missing allowed customer with requested customer | `X-User-Id: user-learning` and no `X-Allowed-Customer-Ids` | `customerId=internal` | Request is denied because missing allowed customer scope now fails closed. | Local unit evidence: `python -m unittest tests.test_policy` passed. Optional runtime capture can be added with a customer-only request. |
| 6. empty allowed headers with requested filters | `X-User-Id: user-learning` `X-Allowed-Project-Ids:` empty `X-Allowed-Customer-Ids:` empty | requested `projectId` and or `customerId` | Request is denied because empty allowed scope now fails closed. | Runtime: run empty-header curl below and capture `HTTP_STATUS=403`. Local unit evidence: `python -m unittest tests.test_policy` passed. |
| 7. comma-separated header values with spaces | `X-Allowed-Project-Ids: learning, alpha , beta` `X-Allowed-Customer-Ids: internal, customer-a` | any matching filter from the parsed set | Values are trimmed and parsed correctly. Matching filters are allowed. | Local unit evidence: `python -m unittest tests.test_policy` passed. Optional runtime capture can use `projectId=alpha` or `customerId=customer-a`. |
| 8. case-insensitive header names | `x-user-id` `x-allowed-project-ids` `x-allowed-customer-ids` | matching scoped filters | Header resolution remains case-insensitive. | Local unit evidence: `python -m unittest tests.test_policy` passed. |
| 9. missing `X-User-Id` defaults to anonymous | no `X-User-Id` header | any request that does not require user-specific identity beyond current learning mode | Access context defaults user to `anonymous` if current code path is unchanged. | Local unit evidence: `python -m unittest tests.test_policy` passed. |

## Curl Evidence

Set the deployed stage URL first.

```bash
export API_BASE_URL="https://<api-id>.execute-api.<region>.amazonaws.com/v1"
```

Allowed RAG request:

```bash
OUTPUT_FILE="$(mktemp)"
HTTP_STATUS="$(curl -sS -o "$OUTPUT_FILE" -w "%{http_code}" \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-learning" \
  -H "X-Allowed-Project-Ids: learning" \
  -H "X-Allowed-Customer-Ids: internal" \
  -d '{
    "question": "How does API Gateway protect backend services in this PoC?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }')"

echo "$HTTP_STATUS"
jq . "$OUTPUT_FILE"
rm -f "$OUTPUT_FILE"
```

Policy denied request with mismatched project:

```bash
OUTPUT_FILE="$(mktemp)"
HTTP_STATUS="$(curl -sS -o "$OUTPUT_FILE" -w "%{http_code}" \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-learning" \
  -H "X-Allowed-Project-Ids: learning" \
  -H "X-Allowed-Customer-Ids: internal" \
  -d '{
    "question": "How does API Gateway protect backend services in this PoC?",
    "filters": {
      "projectId": "other-project",
      "customerId": "internal"
    }
  }')"

echo "$HTTP_STATUS"
jq . "$OUTPUT_FILE"
rm -f "$OUTPUT_FILE"
```

Fail-closed request with no allowed headers but requested `projectId`:

```bash
OUTPUT_FILE="$(mktemp)"
HTTP_STATUS="$(curl -sS -o "$OUTPUT_FILE" -w "%{http_code}" \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-learning" \
  -d '{
    "question": "How does API Gateway protect backend services in this PoC?",
    "filters": {
      "projectId": "learning"
    }
  }')"

echo "$HTTP_STATUS"
jq . "$OUTPUT_FILE"
rm -f "$OUTPUT_FILE"
```

Fail-closed request with empty allowed headers but requested `projectId`:

```bash
OUTPUT_FILE="$(mktemp)"
HTTP_STATUS="$(curl -sS -o "$OUTPUT_FILE" -w "%{http_code}" \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-learning" \
  -H "X-Allowed-Project-Ids:" \
  -H "X-Allowed-Customer-Ids:" \
  -d '{
    "question": "How does API Gateway protect backend services in this PoC?",
    "filters": {
      "projectId": "learning"
    }
  }')"

echo "$HTTP_STATUS"
jq . "$OUTPUT_FILE"
rm -f "$OUTPUT_FILE"
```

## Local Unit Test Evidence

Compile check:

```bash
python3 -m compileall backend/lambda
```

Observed result in the current workspace: compile completed successfully.

Repository-wide test command:

```bash
python3 -m unittest discover -s tests
```

Specific policy test command:

```bash
python3 -m unittest tests.test_policy
```

Inline smoke test option:

```bash
python3 - <<'PY'
import sys
from pathlib import Path

repo_root = Path.cwd()
lambda_root = repo_root / "backend" / "lambda"
if str(lambda_root) not in sys.path:
    sys.path.insert(0, str(lambda_root))

from common.policy import AccessDeniedError, resolve_access_context, assert_filters_allowed

allowed = resolve_access_context(
    {
        "headers": {
            "X-User-Id": "user-learning",
            "X-Allowed-Project-Ids": "learning, alpha , beta",
            "X-Allowed-Customer-Ids": "internal, customer-a",
        }
    }
)

assert allowed.user_id == "user-learning"
assert allowed.auth_source == "trusted_headers"
assert allowed.allowed_project_ids == ["learning", "alpha", "beta"]
assert allowed.allowed_customer_ids == ["internal", "customer-a"]

missing_scope = resolve_access_context({"headers": {"X-User-Id": "user-learning"}})

try:
    assert_filters_allowed({"projectId": "learning"}, missing_scope)
    raise AssertionError("expected AccessDeniedError for missing project scope")
except AccessDeniedError:
    pass

print("policy smoke test passed")
PY
```

Additional observed local test result from this workspace:

```bash
python3 -m unittest tests.test_policy
```

Observed result: `Ran 13 tests in 0.002s` and `OK`.

## Regression Evidence

Reproduction command:

```bash
python3 scripts/run_rag_eval.py
```

Expected result:

```text
RAG evaluation complete: 16/16 cases passed
```

Existing evidence artifact in this repository already records a successful evaluation run with `16/16` passed on `2026-05-28` in `reports/rag-eval-report.md`.

## Non-Production Boundary Reminder

- This still uses trusted headers.
- This is not real authentication.
- The purpose of Phase 8B is to create an internal `AccessContext` contract before adding a real authorizer.
- Real authentication and authorization come later when verified claims replace trusted headers.

## Acceptance Criteria

The Phase 8B refactor is acceptable when:

- compile passes
- policy tests pass
- allowed scope still works
- mismatched scope denies
- missing or empty allowed scope denies when filters are present
- evaluation still passes
- no Cognito, JWT, or authorizer code was added