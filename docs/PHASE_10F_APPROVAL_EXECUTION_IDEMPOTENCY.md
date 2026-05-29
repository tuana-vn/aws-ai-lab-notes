# Phase 10F Approval Execution Idempotency

## Purpose

This document explains the approval-execution idempotency behavior added in Phase 10F.

The scope is intentionally small: make repeated execute calls replay-safe when the approval is already marked executed with a stored incident report reference.

## Current Replay Risk From Phase 10E

Phase 10E identified `POST /approvals/{approvalId}/execute` as the highest-priority replay-safety gap.

Before Phase 10F:

1. the handler validated execute permission and approval state
2. it created a new incident report record
3. it marked the approval executed
4. it returned success

That meant a repeated execute call could create another incident report unless the approval state had already been updated to a non-executable state.

## Implemented Behavior

Phase 10F adds an idempotent replay branch in `POST /approvals/{approvalId}/execute`.

If the approval record already has:

- `execution_status = executed`
- and a stored report reference is available

then the handler now:

- keeps the existing permission check in place
- does not create a new incident report
- does not call `mark_executed` again
- returns HTTP 200
- returns the existing `reportId`
- returns `status=executed`
- returns `executionStatus=executed`

## Cases Handled

Phase 10F handles:

- repeat execute calls after a successful approval execution has already stored the incident report reference on the approval record
- repeat execute calls from an authorized operator who should receive the existing execution result instead of creating a duplicate report

## Cases Intentionally Not Solved Yet

Phase 10F does not fully solve the narrower partial-failure case where:

1. incident report creation succeeds
2. `mark_executed` fails before the report reference is stored on the approval record

In that narrower case, the approval may still look executable on retry, and the handler may still create a duplicate incident report.

That deeper case likely needs one of the following in a future phase:

- a transaction
- deterministic report ID generation
- a conditional write strategy

## Audit Event Added

Phase 10F adds:

- `approval_execute_idempotent_replay`

This event is emitted when the execute route detects an already-executed approval with a stored report reference and returns the existing report instead of creating a new one.

## Manual Verification Commands

The following verification flow is practical for a deployed environment:

1. create an approval through the agent proposal path
2. approve it with an approver token
3. execute it with an operator token
4. store the first `reportId`
5. execute the same approval again with an operator token
6. confirm the second response returns the same `reportId`
7. run the `executions` preset and confirm `approval_execute_idempotent_replay` appears
8. confirm only one incident report exists for that approval if direct record inspection is available

Example execute call shape:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/approvals/<approval-id>/execute" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPERATOR_AUTH_TOKEN" \
  -d '{"executedBy":"operator-user"}'
```

Example log query helper:

```bash
python scripts/query_logs.py \
  --log-group /aws/lambda/<approvals-function-log-group> \
  --preset executions \
  --start-minutes-ago 60
```

Do not paste raw JWTs, passwords, or other secrets into commands or saved evidence.

## Acceptance Criteria

Phase 10F is acceptable when:

- repeated execute calls on an already-executed approval return the existing `reportId`
- the handler does not create a second incident report in that already-executed replay case
- the handler keeps the `approvals:execute` permission check before returning replay results
- a structured audit event is emitted for the idempotent replay case
- the remaining narrower partial-failure risk remains documented honestly