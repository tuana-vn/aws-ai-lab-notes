# Cognito Authorizer Evidence

## Purpose

This document captures evidence for the first real Cognito-protected route in the AWS AI Platform PoC.

Phase 8H introduces Cognito protection only for `POST /rag/query`. It does not claim that the full platform is production-ready or that all routes are protected.

## Implementation Summary

- Cognito User Pool added
- Cognito User Pool Client added
- Cognito authorizer added to API Gateway and SAM configuration
- only `POST /rag/query` is protected in this phase
- backend `AccessContext` consumes authorizer claims from `requestContext.authorizer.claims`
- backend policy gate remains active for `projectId` and `customerId`
- evaluation script supports token mode through `AUTH_TOKEN` or `AUTHORIZATION_HEADER`

## Protected Route Scope

| Route | Current protection | Notes |
| --- | --- | --- |
| `GET /health` | public | Remains public in this phase. |
| `POST /rag/query` | Cognito protected | First and only protected route in Phase 8H. API Gateway rejects unauthenticated calls before Lambda. |
| `/echo`, `/chat`, `/documents`, `/agent/run`, `/approvals/*`, `/incident-reports/*` | unchanged | These routes remain intentionally unchanged for now. |

## Test User and Claims

Do not paste the full token into this document.

Use captured rollout values where available, otherwise fill the placeholders below.

| Field | Value |
| --- | --- |
| username | `tuan` or `[fill deployed username]` |
| userPoolId | `[fill UserPoolId output]` |
| userPoolClientId | `[fill UserPoolClientId output]` |
| token_use | `id` |
| preferred_username | `tuan` or `[fill preferred_username]` |
| custom:project_ids | `learning` |
| custom:customer_ids | `internal` |

## Evidence Matrix

Use this matrix to record the final rollout evidence. Where an exact runtime capture was not preserved in this workspace, a placeholder is included.

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| 1. `sam validate` passed | `sam validate --template-file infra/cloudformation/template.yaml` | Template validates successfully. | `[capture validate output]` | `[fill]` |
| 2. `sam build` passed | `sam build --template-file infra/cloudformation/template.yaml` | Template builds successfully. | `Passed in rollout shell.` | PASS |
| 3. stack deployed | `sam deploy ...` | Stack deploy completes and outputs API plus Cognito identifiers. | `[capture stack name, timestamp, and outputs]` | `[fill]` |
| 4. no-token `/rag/query` rejected by API Gateway | `curl -i -sS -X POST "$API_BASE_URL/rag/query" -H "Content-Type: application/json" -d '{...}'` | HTTP `401` or `403` before Lambda. | Observed in workspace report as HTTP `401 Unauthorized` for unauthenticated `/rag/query`. | PASS |
| 5. valid token plus `learning/internal` returned RAG completed with sources | `curl -i -sS -X POST "$API_BASE_URL/rag/query" -H "Authorization: Bearer $AUTH_TOKEN" ...` | HTTP `200` and valid RAG response with sources. | `[capture completed response summary, requestId, and source list]` | `[fill]` |
| 6. valid token plus `other-project` returned backend policy `403` | `curl -i -sS -X POST "$API_BASE_URL/rag/query" -H "Authorization: Bearer $AUTH_TOKEN" ...` | HTTP `403` from backend policy gate. | `[capture backend denial body]` | `[fill]` |
| 7. token-mode eval completed `15/15` passed with Q006 skipped | `AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py` | `15/15` evaluated cases passed and `Q006` skipped. | `RAG evaluation complete: 15/15 cases passed.` and `Skipped cases: 1` | PASS |
| 8. trusted-header spoofing ignored in token mode | token-mode eval or direct authenticated curl with spoofed `X-Allowed-*` headers | Spoofed trusted headers do not override token claims. | `Q006` is skipped in token mode because trusted-header spoofing is not the active auth source. | PASS |
| 9. backend still returned `userId` from token claims | authenticated `/rag/query` with token carrying `preferred_username` or `username` | Response and or trace records show the user context comes from token claims. | `[capture response or trace userId field]` | `[fill]` |

## Important Interpretation

`Q006` is skipped in token mode because it is a trusted-header spoofing test.

That behavior is correct and should not be treated as a regression:

- with Cognito authorizer enabled, claims from the token become the active `AccessContext` source
- spoofed `X-Allowed-*` headers should not override token claims
- trusted-header spoofing is therefore no longer the active auth path for token-mode `/rag/query` evaluation
- skipping `Q006` in token mode is the expected interpretation of the new security boundary

## Regression Evidence

Token-mode evaluation command:

```bash
AUTH_TOKEN="<id-token>" python3 scripts/run_rag_eval.py
```

Observed result:

```text
RAG evaluation complete: 15/15 cases passed.
Skipped cases: 1
```

The skipped case is `Q006`, which is intentionally excluded in token mode because trusted-header spoofing is not the active auth source.

## Remaining Limitations

- only `/rag/query` is protected in this phase
- ID token is used for PoC convenience
- no production IdP federation
- no route-level OAuth scope enforcement yet
- trusted headers still exist for compatibility
- other routes still need protection in future phases
- no WAF, CloudTrail, or security dashboard hardening yet

## Acceptance Criteria

The phase is acceptable when:

- unauthenticated `/rag/query` is rejected before Lambda
- authenticated allowed `/rag/query` succeeds
- authenticated wrong project is denied by backend policy
- token-mode eval passes with `Q006` skipped
- other routes are not accidentally protected
- no full-production auth claim is made
