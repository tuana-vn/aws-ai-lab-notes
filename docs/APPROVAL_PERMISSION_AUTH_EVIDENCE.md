# Approval Permission Auth Evidence

## Purpose

This document captures the expected evidence for the first route-level permission checks added after the Cognito authentication rollout.

Phase 8R implements permission checks only for:

- `POST /approvals/{approvalId}/decision` requiring `approvals:decide`
- `POST /approvals/{approvalId}/execute` requiring `approvals:execute`

This phase does not add permission checks to other routes yet.

## Group and Permission Model Used

Direct scopes in `AccessContext.scopes` grant matching permissions.

Group mapping used in this phase:

| Group | Granted permissions |
| --- | --- |
| `ai-approver` | `approvals:read`, `approvals:decide` |
| `ai-operator` | `approvals:read`, `approvals:execute`, `incident-reports:read` |
| `ai-admin` | all current route permissions |

## Test User Notes

- do not hard-code a single username for evidence collection
- the Cognito test user used for approval decision evidence should be in `ai-approver`
- the Cognito test user used for approval execute evidence should be in `ai-operator`
- do not rely on `ai-admin` as the main evidence user because it can hide permission bugs
- after group membership changes, obtain a fresh token before testing

## Expected Evidence

| Evidence item | Command | Expected result | Observed result | Status |
| --- | --- | --- | --- | --- |
| user without `ai-approver` cannot decide | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH_TOKEN" -d '{"decision":"approved","decidedBy":"tester"}'` | HTTP `403` with permission-denied message | `[fill after deployment]` | `[fill]` |
| user with `ai-approver` can decide | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" -H "Content-Type: application/json" -H "Authorization: Bearer $APPROVER_TOKEN" -d '{"decision":"approved","decidedBy":"tester"}'` | HTTP `200` and approval transitions to `approved` or `approved_not_executed` | `[fill after deployment]` | `[fill]` |
| user with `ai-approver` cannot execute | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" -H "Content-Type: application/json" -H "Authorization: Bearer $APPROVER_TOKEN" -d '{"executedBy":"tester"}'` | HTTP `403` with permission-denied message | `[fill after deployment]` | `[fill]` |
| user with `ai-operator` can execute after approval | `curl -i -sS -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" -H "Content-Type: application/json" -H "Authorization: Bearer $OPERATOR_TOKEN" -d '{"executedBy":"tester"}'` | HTTP `200`, `status=executed`, and response includes `reportId` | `[fill after deployment]` | `[fill]` |
| execute still fails if approval is not ready | `curl -i -sS -X POST "$API_BASE_URL/approvals/$PENDING_APPROVAL_ID/execute" -H "Content-Type: application/json" -H "Authorization: Bearer $OPERATOR_TOKEN" -d '{"executedBy":"tester"}'` | HTTP `409` because workflow-state validation still applies even with `approvals:execute` | `[fill after deployment]` | `[fill]` |

## Notes

- no-token requests should still be rejected by API Gateway before backend permission checks run
- permission checks do not replace approval state validation
- permission checks do not replace executor action-type validation
- broader route-level scope and role authorization remains a later phase