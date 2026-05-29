# Alarm And Retention Candidates

## Purpose

This document identifies the first alarm and retention candidates for the current `aws-ai-platform-poc` baseline.

It does not create alarms. It defines which signals are worth watching first, why they matter, and what must be observed before thresholds become real.

## Current Baseline

The current repository already has:

- structured CloudWatch logs
- request traces in DynamoDB
- structured approval and execution audit events
- a basic dashboard and Logs Insights workflow
- Bedrock generation token-usage visibility where available

The current repository does not yet have:

- CloudWatch alarms
- final thresholds
- documented production retention settings

## Why Alarms Are Not Added Immediately

Adding alarms too early creates predictable problems:

- thresholds are guessed instead of based on baseline noise
- operators receive false positives and stop trusting alerts
- the team mixes security alarms, quality alarms, and cost alarms without a review model

The first step should be baseline observation using existing logs, traces, and query workflows.

## Baseline-first Alarm Strategy

The recommended strategy is:

1. identify signals that already exist in structured logs or traces
2. observe their normal frequency and burst patterns
3. choose a small P0 alarm set first
4. keep the first thresholds conservative until real traffic is observed
5. expand only after the initial alarm set proves useful

## Candidate Alarms

### API / Runtime Health

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| API error spike | elevated 5xx responses or handler failures | API Gateway metrics and Lambda error logs | indicates service instability or deployment regressions | sustained error rate above recent baseline for multiple minutes | medium during deployments or tests | P0 | first alarm slice |
| Lambda latency drift | rising end-to-end request latency on core routes | API Gateway metrics, Lambda duration, structured logs | can reveal retrieval, Bedrock, or downstream slowdowns | sustained latency materially above recent baseline | medium if traffic mix changes | P1 | after baseline review |
| Request timeout risk | rising near-timeout Lambda durations | Lambda duration metrics and logs | helps catch runtime saturation before full failure | repeated durations close to timeout window | low to medium | P1 | after baseline review |

### RAG Quality And Grounding

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `no_source` spike | increased `no_source` outcomes | structured logs, traces | may indicate ingestion gaps, retrieval drift, or malformed filters | sustained `no_source` rate well above normal for comparable traffic | medium because content mix matters | P1 | after baseline review |
| Output guardrail warning spike | increased warning-oriented output guardrail events | structured logs and traces | may indicate weaker grounding or prompt drift | sustained warning rate above recent baseline | medium | P1 | after baseline review |
| Retrieval denial drift | increased denied RAG requests | structured logs | may indicate auth-boundary issues, misuse, or configuration drift | denial rate above expected operator baseline | medium because tests may trigger it intentionally | P0 | first alarm slice if traffic exists |

### Security And Policy Denial

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Access denied burst | surge in policy-denied requests | structured logs | may indicate probing, broken client configuration, or permission drift | short-window spike compared with normal denied volume | medium | P0 | first alarm slice |
| Unauthorized route access pattern | repeated auth failures across protected routes | API Gateway auth metrics and logs where available | may indicate misconfigured clients or hostile probing | repeated failures across multiple requests in a short window | medium | P1 | after auth-baseline review |

### Guardrail Abuse Signals

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Guardrail block spike | increased blocked prompts | structured logs and traces | may indicate prompt-injection attempts or abuse | sustained blocked rate above recent baseline | medium because testing may generate blocks | P0 | first alarm slice |
| Repeated blocked actor pattern | repeated blocked requests from same actor or context | logs with user or request context where available | useful for identifying concentrated abuse patterns | repeated blocks tied to same user or caller context in a short window | medium | P1 | after baseline review |

### Approval And Execution Safety

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Execution denial spike | rising `approval_execute_denied` events | audit logs | may indicate misuse, broken approval flow, or permission drift | more than baseline execution denials within a short window | low to medium | P0 | first alarm slice |
| Approval backlog growth | large count of pending approvals | approval records and dashboard views | may indicate stalled human workflow or incomplete operations handoff | backlog materially above normal operational queue | medium because workload can vary | P1 | after workflow baseline review |
| Unexpected execution activity | `approval_executed` outside expected review windows | audit logs | may indicate change in operator pattern or unsafe execution timing | any execution outside defined operational norms | high if no norm exists yet | P2 | only after operational norms exist |

### Bedrock / Token Usage And Cost Risk

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Token usage spike | unusually high input or total tokens on generation paths | structured logs and traces from Phase 10B | may indicate prompt bloat, context inflation, or costly traffic patterns | repeated requests materially above recent median token counts | medium because content size varies | P1 | after cost baseline review |
| Bedrock latency spike | rising `bedrockLatencyMs` | structured logs and traces | can indicate downstream model latency issues affecting user experience | sustained Bedrock latency above baseline | medium | P1 | after baseline review |

### DynamoDB / Write Failures

| Candidate | Signal | Source | Why it matters | Suggested initial threshold idea | Risk of false positives | Priority | Implementation phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Trace write failure | failed trace persistence | Lambda error logs | weakens investigation and audit quality | any repeated failures within a short window | low | P0 | first alarm slice |
| Approval write failure | failed approval record persistence | Lambda error logs and audit gaps | can break approval workflow integrity | any repeated failures within a short window | low | P0 | first alarm slice |
| Incident report write failure | failed incident-report persistence after approved execution | Lambda error logs and workflow verification | can break the only current execution action | any repeated failure | low | P0 | first alarm slice |

## Retention Candidates

### CloudWatch Log Groups

Candidate retention focus:

- preserve enough log history to investigate denial spikes, guardrail abuse, execution issues, and latency drift
- distinguish normal debugging needs from security-review needs

### DynamoDB Trace Table

Candidate retention focus:

- preserve enough request history to reconstruct RAG behavior and operator investigations
- define whether old traces should expire or be archived after the main investigation window

### Action Approvals Table

Candidate retention focus:

- preserve approval history longer than short-lived request traces because it carries governance and decision evidence

### Incident Reports Table

Candidate retention focus:

- preserve incident records according to internal review and evidence needs rather than only runtime troubleshooting needs

### Generated Reports / Evidence Artifacts

Candidate retention focus:

- keep reports, screenshots, query exports, and internal evidence packs with clear naming and timestamping so they remain usable during later review

## Acceptance Criteria Before Implementing Alarms

Before actual alarms are implemented:

- the signal must already exist in logs, traces, or platform metrics
- the team must observe baseline noise long enough to avoid guessed thresholds
- the alarm must have an owner and a response expectation
- the threshold must be treated as initial, not final
- the first alarm slice must stay narrow and high-value

## Current Implementation Boundary

Current implementation means logs, traces, queries, and dashboards exist, but alarms and production retention settings do not.

## Future Roadmap Boundary

Future roadmap means introducing a small first alarm set and explicit retention settings after baseline observation.