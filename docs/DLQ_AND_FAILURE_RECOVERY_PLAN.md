# DLQ And Failure Recovery Plan

## Purpose

This document defines a practical failure-recovery and DLQ review for the current `aws-ai-platform-poc` baseline.

The main point is simple: DLQ is not automatically useful for every failure in a synchronous API Gateway to Lambda platform. This phase clarifies where retry, operator review, or future asynchronous recovery patterns would matter.

## Current Invocation Model

The current platform is primarily synchronous:

- API Gateway invokes Lambda handlers directly
- handlers validate requests, call Bedrock or DynamoDB inline, and return a response immediately
- traces, approvals, and incident reports are written inline in those same request paths

The repository does not currently use queues, event buses, async worker flows, or DLQ-backed processing.

## When DLQ Is Useful And When It Is Not

DLQ is useful when:

- work is asynchronous or decoupled from the original caller
- a failed unit of work can be replayed safely later
- operator review benefits from a preserved failed event payload

DLQ is not automatically useful when:

- the route is synchronous and the caller is waiting for the result immediately
- the failure happens before a durable event is emitted anywhere
- replaying the failed request later would create duplicate side effects or confuse the client-visible outcome

For this platform, DLQ is a future design option for later asynchronous flows. It is not the default answer for the current synchronous API shape.

## API Gateway Synchronous Lambda Considerations

In the current design:

- the caller gets the success or failure directly from the Lambda path
- timeouts and ambiguous network failures can cause the client to retry manually
- some handlers perform side effects before the final response is returned

That means the first reliability priority is replay safety and clear retry rules, not immediate DLQ adoption.

## Candidate Failure Modes

### Bedrock Timeout / Failure

Current shape:

- `/chat` and `/rag/query` return `502` for Bedrock-related invocation failures
- no explicit retry strategy is documented

Risk:

- automatic retry can amplify latency and cost
- client retries can duplicate downstream model work

### DynamoDB Trace Write Failure

Current shape:

- trace writes happen inline in handlers and shared services
- some routes can fail even if the main answer or action was otherwise available

Risk:

- observability failure can become a user-facing failure

### DynamoDB Document Write Failure

Current shape:

- `/documents` deletes prior chunks and then writes replacement chunks

Risk:

- failure after delete can leave missing or partial state
- naive retries can hide the fact that a destructive partial failure already happened

### Approval Write Failure

Current shape:

- approval creation and decision updates happen inline on synchronous routes

Risk:

- retries can create duplicate proposal records or conflicting state updates if not governed carefully

### Incident Report Write Failure

Current shape:

- incident report creation happens before approval execution is marked complete

Risk:

- partial success can create a report without updating the approval state
- retries can create a second report

### CloudWatch Logging Delay Or Loss

Current shape:

- logs are useful evidence, but they are not the main transaction boundary

Risk:

- log timing or delivery issues can complicate investigation, but logs should not be treated as the only source of truth for critical state

### Partial Success After Client Timeout

Current shape:

- a client can time out or disconnect after Lambda has already started side effects

Risk:

- the client retries because it is uncertain whether the operation completed
- duplicate writes or duplicate execution can follow

## Recovery Strategy By Failure Type

### Bedrock Timeout / Failure

Recommended recovery:

- return failure clearly to the caller
- avoid blind automatic retries in the synchronous path
- rely on operator review when repeated failures become systemic

### DynamoDB Trace Write Failure

Recommended recovery:

- classify trace persistence as either hard-required or best-effort per route
- do not treat all trace failures as business-transaction failures by default

### DynamoDB Document Write Failure

Recommended recovery:

- require explicit operator review if replacement may have partially succeeded
- avoid automatic retries that assume the document state is still clean

### Approval Write Failure

Recommended recovery:

- require route-specific replay guidance
- avoid automatic retries that can create duplicate approvals or conflicting decisions

### Incident Report Write Failure

Recommended recovery:

- treat as a replay-sensitive operator-reviewed failure
- do not automatically retry unless execution idempotency is implemented first

### CloudWatch Logging Delay Or Loss

Recommended recovery:

- rely on DynamoDB-backed records and approval state as the stronger evidence source where available
- use operator review rather than retry logic for log-delivery ambiguity

### Partial Success After Client Timeout

Recommended recovery:

- favor read-back verification on the relevant record before reissuing the write
- for execution flows, confirm approval execution state and incident report result before retrying

## What Should Be Retried Automatically

For the current synchronous platform, automatic retries should stay narrow.

Reasonable future candidates:

- short-lived read-only lookup retries where no write side effects exist
- carefully bounded retries for clearly transient downstream reads, only after timeout budgets are defined

## What Should Not Be Retried Automatically

The following should not be retried automatically in the current design:

- approval execution
- approval decision updates
- document replacement writes
- proposal-creation flows that create approval records
- Bedrock generation calls without a clear timeout and cost policy

## What Requires Operator Review

Operator review is the safer current posture for:

- ambiguous execution outcomes
- partial document-ingestion failures
- repeated Bedrock failures across multiple requests
- trace or audit persistence failures that may affect evidence quality

## Future DLQ Or Event-driven Candidates

DLQ becomes more relevant if the platform later adds:

- asynchronous ingestion jobs
- deferred incident-report enrichment
- background evidence export or archival jobs
- non-interactive approval side effects executed through an event-driven worker model

Those are future candidates only. They are not part of the current synchronous request design.

## Acceptance Criteria Before Implementing DLQ / Retry Controls

Before adding DLQ or automatic retries:

- the failure mode must be classified as synchronous or asynchronous
- replay safety must be understood for that operation
- automatic retry must not create duplicate business records
- operators must know when to retry, when to read back state, and when to escalate
- DLQ must be justified by an actual queued or asynchronous work model rather than added by default

## Current Implementation Boundary

Current implementation means synchronous request paths, inline writes, and no DLQ-backed recovery model.

## Future Roadmap Boundary

Future roadmap means targeted retry rules, replay protection, and possible DLQ use only where asynchronous workflows later exist.