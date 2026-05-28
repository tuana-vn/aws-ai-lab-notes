# Authorizer Claims Resolver Evidence

## Purpose

This document captures evidence for Phase 8E.

Phase 8E added a second `AccessContext` source based on `requestContext.authorizer.claims` while preserving the existing trusted-header learning path. This document records what changed, how it was verified, and what this phase does not claim.

## Implementation Summary

- `resolve_access_context(event)` now supports `requestContext.authorizer.claims`.
- `auth_source` becomes `mock_authorizer_claims` when the claim-based resolver path is used.
- trusted-header fallback remains in place.
- the backend policy gate remains unchanged.
- no Cognito, JWT validation, or API Gateway authorizer infrastructure is implemented.

## Files Changed

| File | Change | Why it matters |
| --- | --- | --- |
| `backend/lambda/common/policy.py` | Added a claim-based `AccessContext` resolver path using `requestContext.authorizer.claims`, while preserving trusted-header fallback. | Extends the internal auth context contract without changing the backend policy gate or adding infrastructure. |
| `tests/test_policy.py` | Added unittest coverage for claim mapping, fallback behavior, and fail-closed scope handling. | Protects the new resolver path and existing trusted-header behavior from regression. |

## Behavior Matrix

| Scenario | Expected behavior | Evidence |
| --- | --- | --- |
| 1. trusted headers still map to `AccessContext` | Header-based requests still resolve `user_id`, allowed project scope, allowed customer scope, and `auth_source=trusted_headers`. | Covered by `python3 -m unittest tests.test_policy` with passing trusted-header tests. |
| 2. authorizer claims map `user_id`, `principal_id`, and `auth_source` | Claim-based requests resolve `user_id` from `preferred_username`, `username`, or `sub`; `principal_id` prefers `sub`; `auth_source=mock_authorizer_claims`. | Covered by `python3 -m unittest tests.test_policy` with passing claim mapping tests. |
| 3. authorizer claims map project and customer scopes | `custom:project_ids` and `custom:customer_ids` become allowed scope lists and permit matching filters. | Covered by `python3 -m unittest tests.test_policy` with passing matching-scope tests. |
| 4. authorizer claims map `scope` to `scopes` list | `scope` is parsed as space-separated values. | Covered by `python3 -m unittest tests.test_policy` with passing scope-mapping tests. |
| 5. authorizer claims map `cognito:groups` string or list | `cognito:groups` becomes a normalized `groups` list from either a comma-separated string or a list input. | Covered by `python3 -m unittest tests.test_policy` with passing group-mapping tests. |
| 6. missing project claim denies requested project | When `custom:project_ids` is missing or empty and a request asks for `projectId`, policy fails closed. | Covered by `python3 -m unittest tests.test_policy` with passing deny test. |
| 7. missing customer claim denies requested customer | When `custom:customer_ids` is missing or empty and a request asks for `customerId`, policy fails closed. | Covered by `python3 -m unittest tests.test_policy` with passing deny test. |
| 8. authorizer absent falls back to trusted headers | If `requestContext.authorizer.claims` is absent or not a dict, header-based resolution remains active. | Covered by `python3 -m unittest tests.test_policy` with passing fallback test. |
| 9. `run_rag_eval` still passes | Existing runtime behavior still holds after the resolver change. | `python3 scripts/run_rag_eval.py` completed with `RAG evaluation complete: 16/16 cases passed`. |

## Local Test Evidence

Compile check:

```bash
python3 -m compileall backend/lambda
```

Focused policy tests:

```bash
python3 -m unittest tests.test_policy
```

Repository-wide unittest discovery:

```bash
python3 -m unittest discover -s tests
```

Expected result for the unittest commands:

```text
OK
```

Observed local result for the focused policy tests after the Phase 8E change:

```text
......................
----------------------------------------------------------------------
Ran 22 tests in 0.003s

OK
```

Observed local result for repository-wide unittest discovery after the Phase 8E change:

```text
......................
----------------------------------------------------------------------
Ran 22 tests in 0.003s

OK
```

## Inline Smoke Test

Use the following inline Python test to inspect the mock authorizer-claims resolver directly.

```bash
python3 - <<'PY'
import sys
from pathlib import Path

repo_root = Path.cwd()
lambda_root = repo_root / "backend" / "lambda"
if str(lambda_root) not in sys.path:
    sys.path.insert(0, str(lambda_root))

from common.policy import resolve_access_context

event = {
    "requestContext": {
        "authorizer": {
            "claims": {
                "sub": "user-123",
                "preferred_username": "tuan",
                "custom:project_ids": "learning,demo",
                "custom:customer_ids": "internal",
                "scope": "rag:query agent:run",
                "cognito:groups": "engineers,approvers",
            }
        }
    }
}

access_context = resolve_access_context(event)

assert access_context.auth_source == "mock_authorizer_claims"
assert access_context.user_id == "tuan"
assert access_context.principal_id == "user-123"
assert access_context.allowed_project_ids == ["learning", "demo"]
assert access_context.allowed_customer_ids == ["internal"]
assert access_context.scopes == ["rag:query", "agent:run"]
assert access_context.groups == ["engineers", "approvers"]

print("authorizer claims smoke test passed")
PY
```

Expected values:

- `auth_source = mock_authorizer_claims`
- `user_id = tuan`
- `principal_id = user-123`
- `allowed_project_ids = ["learning", "demo"]`
- `allowed_customer_ids = ["internal"]`
- `scopes = ["rag:query", "agent:run"]`
- `groups = ["engineers", "approvers"]`

## Regression Evidence

Reproduction command:

```bash
python3 scripts/run_rag_eval.py
```

Expected result:

```text
RAG evaluation complete: 16/16 cases passed
```

Observed result in this workspace after the Phase 8E change:

```text
RAG evaluation complete: 16/16 cases passed.
JSON results: reports\rag-eval-results.json
Markdown report: reports\rag-eval-report.md
```

The current evaluation report in `reports/rag-eval-report.md` records `16/16` passed on `2026-05-28`.

## Non-Production Boundary Reminder

- `requestContext.authorizer.claims` are not cryptographically verified in Phase 8E.
- this is not real authentication.
- real authentication comes later with Cognito plus API Gateway authorizer integration or a Lambda authorizer.
- the backend policy gate is now ready to consume verified claims when that infrastructure is added.

## Known Observation

If multiple documents share the same metadata scope, retrieval can return both. This is expected and separate from the auth resolver behavior.

The current evaluation report already shows this pattern in allowed RAG cases where both `api-gateway-note-demo` and `api-gateway-note` appear under the same `projectId=learning` and `customerId=internal` scope.

## Acceptance Criteria

- compile passes
- unittest passes
- trusted headers still pass
- mock authorizer claims pass
- missing claims fail closed
- evaluation passes
- no Cognito, JWT, or authorizer infrastructure was added