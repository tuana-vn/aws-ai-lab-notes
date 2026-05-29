# Phase 10A Production Hardening Gap Review

## Purpose

This document reviews the gap between the current `aws-ai-platform-poc` implementation and a more production-ready backend platform.

The intent is practical prioritization, not a theoretical maturity model. The review stays grounded in the current repository state and identifies the highest-value hardening actions without claiming that those actions are already implemented.

This phase is documentation only.

## Current PoC Baseline

The current repository baseline includes:

- API Gateway, Lambda, DynamoDB, CloudWatch Logs, Cognito, Bedrock Runtime, and SAM / CloudFormation
- a basic CloudWatch dashboard from Phase 9C
- `GET /health` remaining public by design
- Cognito protection on all non-health routes
- `AccessContext` resolved from Cognito claims on protected routes
- trusted-header fallback still present for local or unprotected compatibility
- `/rag/query` with metadata filtering, backend policy enforcement, input guardrail, output guardrail, and trace records
- `/agent/run` with controlled tasks and allowlisted tools
- approval decision requiring `approvals:decide`
- approval execute requiring `approvals:execute`
- execution restricted to the allowlisted internal action `create_incident_report`
- successful execution limited to internal DynamoDB incident-report creation
- structured approval and execution audit events added in Phase 9B
- practical Logs Insights queries, a runbook, and a basic dashboard added in Phase 9C

This baseline is useful for learning, internal review, and backend design discussion, but it is not production-ready.

## Review Method

This review uses a practical gap-analysis method:

1. identify the current implemented state in the repository
2. compare it against common production-readiness expectations for backend, security, reliability, and operations
3. describe the main gap and the corresponding operational or security risk
4. recommend the next concrete hardening action
5. assign a relative priority:
   - `P0`: highest-value hardening gap that should be addressed early before broader rollout
   - `P1`: important but can follow the first hardening slice
   - `P2`: useful improvement, but not the first blocking step

Suggested next phases are guidance only. They are not implemented by this document.

## Gap Review By Area

### Identity And Authentication

**Current state**

- Cognito protects all non-health routes.
- Protected routes resolve identity from Cognito claims.
- The current PoC uses an ID token for convenience.
- No production IdP federation is implemented.

**Gap**

- The authentication model is still PoC-oriented and does not yet describe a production identity integration pattern, token strategy, or session lifecycle approach.

**Risk**

- Identity assumptions may not hold when integrating with a real enterprise IdP, stronger token governance, or multi-environment access controls.

**Recommended action**

- Define the target production identity model, including token type expectations, issuer trust boundary, environment separation, and administrator/operator onboarding flow.

**Priority**

- P0

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Authorization And Route Permissions

**Current state**

- All non-health routes are authenticated.
- Explicit route-level permission checks currently exist for approval decision and approval execute.
- Other protected routes are authenticated but not separately permission-scoped.

**Gap**

- Authentication is broader than authorization. Most routes do not yet enforce route-specific permissions or least-privilege role design.

**Risk**

- Authenticated users may gain broader functional access than intended as the platform grows.

**Recommended action**

- Define a route-to-permission matrix for the remaining protected routes and implement least-privilege permission boundaries incrementally.

**Priority**

- P0

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Tenant/Project/Customer Data Boundary

**Current state**

- `/rag/query` enforces project and customer scope after authentication.
- Metadata filters remain part of the active boundary.
- Traces and query evidence can show denied requests.

**Gap**

- The data-boundary model is strongest in the RAG path, but equivalent tenant or project boundary assumptions are not described across every route and future data flow.

**Risk**

- Future feature growth could create uneven boundary enforcement if route-by-route data access rules are not made explicit.

**Recommended action**

- Document the authoritative tenant, project, and customer boundary model and map it to each data-reading and data-writing route.

**Priority**

- P0

**Suggested next phase**

- Phase 10A follow-on authorization hardening slice

### Trusted Header Fallback

**Current state**

- Trusted-header fallback still exists for local or unprotected compatibility.
- Cognito claims are the active authority on protected routes.

**Gap**

- A compatibility path still exists that is useful for development but weakens the production boundary story.

**Risk**

- Future misuse, confusion, or accidental deployment reliance could undermine trust in the identity boundary.

**Recommended action**

- Define a deprecation plan for trusted-header fallback in production environments and isolate any local-development compatibility path clearly.

**Priority**

- P0

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### RAG Retrieval Scalability

**Current state**

- Retrieval uses DynamoDB scan plus in-Lambda cosine similarity.
- The repository intentionally treats this as learning-focused, not production-scale retrieval.

**Gap**

- The current retrieval path will not scale well for larger corpora, higher query volume, or stricter latency targets.

**Risk**

- Latency, cost, and operational predictability degrade as dataset size grows.

**Recommended action**

- Evaluate and choose a production retrieval path, such as Bedrock Knowledge Bases or a dedicated vector index, based on latency, governance, and operating-model needs.

**Priority**

- P0

**Suggested next phase**

- Phase 10C - RAG Upgrade Path: Bedrock Knowledge Bases or OpenSearch

### Guardrails And Prompt-Injection Controls

**Current state**

- `/rag/query` includes input guardrails and output guardrail warnings.
- Guardrail outcomes are visible in logs and evidence flows.

**Gap**

- The current guardrail implementation is useful but still narrow. There is no broader adversarial-test program, formal rule-tuning process, or production alerting around guardrail activity.

**Risk**

- Unsafe patterns may drift over time without structured review, alerting, or regression coverage.

**Recommended action**

- Define a regular guardrail test set, review process, and escalation path for blocked patterns and warning-heavy outputs.

**Priority**

- P1

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Agent Tool Governance

**Current state**

- `/agent/run` is constrained to fixed tasks and allowlisted tools.
- The proposal-oriented path creates approvals instead of executing external actions.

**Gap**

- Governance is implemented in code, but there is no formal operator policy, lifecycle review, or change-management process for expanding tasks and tools.

**Risk**

- Agent scope could grow informally without matching governance, review, or risk ownership.

**Recommended action**

- Define a change-control process for new tools, new tasks, and any future action-capable behavior.

**Priority**

- P1

**Suggested next phase**

- Phase 10A follow-on operations hardening slice

### Human Approval And Execution Boundary

**Current state**

- Approval decision and execution are separated.
- `approvals:decide` and `approvals:execute` are enforced.
- Successful execution remains limited to internal incident-report creation.

**Gap**

- The boundary is strong for the current single action type, but expansion to additional actions would require a more explicit approval policy model, richer audit evidence, and stronger operational safeguards.

**Risk**

- Future action growth could outpace governance and create unsafe execution pathways.

**Recommended action**

- Preserve the current separation and define explicit approval criteria, action taxonomy, and execution controls before adding any new executable action types.

**Priority**

- P0

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Audit Logs And Evidence Retention

**Current state**

- Phase 9 added structured approval and execution audit events.
- CloudWatch Logs, trace records, approvals, and incident reports provide useful evidence.
- The current docs do not establish a production retention, export, or evidence-governance policy.

**Gap**

- Observability exists, but retention and evidence-management expectations are not yet formalized.

**Risk**

- Evidence may be incomplete, inconsistently retained, or harder to use during incidents or audits.

**Recommended action**

- Define retention expectations, export boundaries, and operator procedures for audit evidence preservation.

**Priority**

- P1

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### CloudWatch Dashboard And Alarms

**Current state**

- A basic CloudWatch dashboard now exists.
- Practical query presets and a runbook exist.
- No CloudWatch alarms have been added yet.

**Gap**

- The observability experience is useful for manual review, but not yet sufficient for production alerting, on-call response, or service-level monitoring.

**Risk**

- Important failures, denial spikes, or abnormal guardrail rates may require manual discovery instead of timely alerting.

**Recommended action**

- Define a first alarm set only after normal baselines are understood, starting with denial spikes, execution failures, and key availability indicators.

**Priority**

- P1

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### CloudTrail And AWS Control-Plane Audit

**Current state**

- No CloudTrail-focused operational dashboard or review workflow is implemented in this repository.

**Gap**

- The current platform review is strong on application behavior but light on AWS control-plane auditability and change tracking.

**Risk**

- Infrastructure or IAM changes may be harder to investigate through the current app-level observability workflow alone.

**Recommended action**

- Define the minimum CloudTrail and control-plane audit posture needed for environment changes, deployment actions, and privileged access review.

**Priority**

- P1

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Network And Edge Protection

**Current state**

- No WAF hardening is implemented.
- The current docs do not describe production edge controls, rate limiting strategy, or network-isolation posture.

**Gap**

- Internet-facing protection and request-shaping controls are not yet part of the deployed PoC design.

**Risk**

- Abuse, noisy traffic, or hostile request patterns may rely too heavily on downstream app logic instead of layered edge controls.

**Recommended action**

- Review edge protection needs, starting with WAF posture, request filtering strategy, and rate-limiting expectations for public entry points.

**Priority**

- P1

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Secrets And Configuration

**Current state**

- The application relies on environment variables and current AWS service configuration.
- The repository docs caution against exposing tokens and secrets in commands or screenshots.

**Gap**

- There is no production-ready configuration-management story documented for secret rotation, environment-specific overrides, or operational access boundaries.

**Risk**

- Operational drift or ad hoc secret handling can create avoidable security and deployment risk.

**Recommended action**

- Define the production secret-management and configuration-separation model, including rotation expectations and environment ownership.

**Priority**

- P0

**Suggested next phase**

- Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention

### Data Protection And Encryption

**Current state**

- The platform uses managed AWS services that provide baseline encryption capabilities, but this repository does not document a production data-classification or encryption-control review.

**Gap**

- Encryption and data-protection posture are not yet described at the level expected for a production review.

**Risk**

- Teams may over-assume the protection model without aligning on data sensitivity, encryption expectations, and access boundaries.

**Recommended action**

- Document the target data-classification model and verify encryption, access, and retention decisions for each stored evidence type.

**Priority**

- P1

**Suggested next phase**

- Phase 10A follow-on data protection review

### Cost And Token Observability

**Current state**

- No production-grade cost dashboard exists.
- No token-usage observability is currently documented as part of the runtime or dashboard.

**Gap**

- The platform has no current mechanism for tracking Bedrock token consumption, high-cost request patterns, or cost drift.

**Risk**

- Cost surprises and inefficient usage patterns may go unnoticed until after growth or incident review.

**Recommended action**

- Define the minimum cost and token-observability dataset needed before wider usage.

**Priority**

- P1

**Suggested next phase**

- Phase 10B - Cost and Token Usage Observability

### Reliability, Retry, DLQ, And Idempotency

**Current state**

- The current repository demonstrates functional flows, but it does not document a production reliability pattern covering retries, dead-letter handling, or idempotent write protection.

**Gap**

- Reliability hardening has not yet been formalized for failure recovery or repeated request handling.

**Risk**

- Transient failures, duplicate execution attempts, or downstream write issues may be harder to recover from safely.

**Recommended action**

- Review failure modes for Lambda invocations, approval execution, and persistence writes, then define idempotency and recovery expectations before wider rollout.

**Priority**

- P0

**Suggested next phase**

- Phase 10A follow-on reliability hardening slice

### Deployment, Rollback, And Environment Separation

**Current state**

- SAM / CloudFormation are used for infrastructure deployment.
- The repository does not yet describe a production deployment workflow with rollback strategy, promotion controls, or strong environment separation.

**Gap**

- Deployment hygiene is not yet described at the level expected for production operations.

**Risk**

- Rollback, environment drift, and release-control failures may be harder to manage under change pressure.

**Recommended action**

- Define environment separation, deployment promotion flow, rollback expectations, and release ownership before broader adoption.

**Priority**

- P0

**Suggested next phase**

- Phase 10A follow-on release engineering review

### Testing And Evaluation

**Current state**

- The repository includes unit tests, RAG evaluation scripts, and practical evidence workflows.
- The current testing shape is useful for PoC validation but does not yet represent a full production test strategy.

**Gap**

- Broader production expectations such as failure-mode testing, permission-matrix coverage, recovery tests, and sustained regression ownership are not yet documented.

**Risk**

- Important regressions may escape if testing remains centered on happy-path and targeted behavior checks only.

**Recommended action**

- Define a production test matrix covering auth boundaries, permission boundaries, guardrails, retrieval quality, approval execution safety, and operational failure cases.

**Priority**

- P1

**Suggested next phase**

- Phase 10E - Reliability Hardening: Retry, DLQ, Idempotency, Rollback

### Documentation And Operational Ownership

**Current state**

- The repository now has strong architecture, auth, audit, runbook, evidence-pack, and summary documentation.
- The docs are strong for design walkthroughs and internal demos.

**Gap**

- Ownership, on-call responsibilities, service expectations, and operational decision rights are not yet formalized.

**Risk**

- Teams may understand the system technically but still lack clear accountability during incidents, hardening work, or release decisions.

**Recommended action**

- Define who owns runtime behavior, access policy changes, dashboard/alarm tuning, approval-policy changes, and deployment decisions.

**Priority**

- P1

**Suggested next phase**

- Phase 10A follow-on operations hardening slice

## Priority Summary

The strongest current production-hardening gaps are:

- `P0`: identity model, route-level authorization coverage, trusted-header deprecation, RAG retrieval scalability, approval and execution expansion controls, secrets/configuration, reliability hardening, deployment and rollback hygiene
- `P1`: guardrail review process, audit evidence retention, alarms, CloudTrail/control-plane audit, WAF and edge protection, data protection review, cost observability, broader test strategy, operational ownership
- `P2`: lower-urgency polish after the higher-risk gaps are addressed

## Current Implementation Boundary

Current implementation means the repository already demonstrates:

- authenticated non-health routes
- backend RAG scope enforcement
- guardrails and traceability
- a controlled agent with bounded tools
- separated approval and execution permissions
- structured approval and execution audit visibility
- a basic manual-operator dashboard workflow

## Future Roadmap Boundary

Future production hardening means work that is recommended by this review but not implemented here, including:

- broader permission scoping
- removal or isolation of trusted-header fallback
- production retrieval architecture
- alarms and stronger audit retention
- CloudTrail and WAF posture
- cost and token observability
- stronger deployment, rollback, and ownership controls