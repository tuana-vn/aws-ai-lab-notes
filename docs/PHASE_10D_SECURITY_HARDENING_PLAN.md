# Phase 10D Security Hardening Plan

## Purpose

This document defines a practical security-hardening plan for the current `aws-ai-platform-poc` baseline.

The focus is the next layer of operational security around edge protection, control-plane audit, alarms, and evidence retention. This is a planning document only. It does not add WAF, CloudTrail dashboards, alarms, retention policies, or other AWS resources.

## Current Baseline

The current repository baseline already includes:

- API Gateway, Lambda, DynamoDB, CloudWatch Logs, Cognito, Bedrock Runtime, and SAM
- `GET /health` remaining public by design
- Cognito protection on all non-health routes
- `/rag/query` with `AccessContext`, input guardrail, backend policy gate, metadata filter, retrieval, `no_source` behavior, grounded Bedrock generation, output guardrail, traces, logs, and Bedrock token-usage visibility where Bedrock returns usage fields
- `/agent/run` constrained to controlled tasks and allowlisted tools
- separated approval decision and approval execute permissions
- execution limited to `create_incident_report`
- successful execution limited to an internal DynamoDB incident report record
- Phase 9 approval and execution audit events plus a basic CloudWatch dashboard and runbook

This is a useful PoC security baseline, but it is not a production security posture.

## What This Phase Does Not Implement

This phase does not implement:

- AWS WAF
- CloudTrail dashboards or security dashboards
- CloudWatch alarms
- production log-retention settings
- DynamoDB TTL or archival policy changes
- IAM policy changes
- API Gateway throttling changes
- application code changes
- infrastructure changes in `template.yaml`

## Security Hardening Goals

The Phase 10D goals are:

- make the internet-facing edge posture explicit
- separate application audit from AWS control-plane audit
- define the first alarm set only after baseline signal behavior is understood
- define what security and operational evidence should be retained and for how long
- preserve approval and execution audit quality as the platform evolves
- improve incident investigation readiness without pretending the controls are already deployed

## Hardening Areas

### Edge Protection And WAF

The current PoC does not have an edge-protection layer beyond API Gateway, Cognito on protected routes, application validation, and backend controls.

WAF should be treated as a future edge filter for:

- common malformed or abusive internet traffic
- rate-based protection for obvious spikes
- selected path-specific controls for public exposure

WAF must not be treated as a replacement for Cognito, backend authorization, RAG policy gates, guardrails, or approval boundaries.

### API Gateway Throttling Review

API Gateway throttling is a separate concern from WAF. Even with WAF, the platform still needs a clear rate and burst posture for:

- `/chat`
- `/rag/query`
- `/agent/run`
- approval and incident-report routes

The first task is not to set final limits immediately. The first task is to review current usage assumptions and decide which routes need the strictest request-budget controls.

### CloudTrail / Control-plane Audit

The current platform has useful application audit for request behavior, approval lifecycle, and execution behavior. It does not yet document the AWS control-plane audit story.

CloudTrail planning is needed so operators can review:

- IAM changes
- Lambda code or configuration changes
- API Gateway configuration changes
- DynamoDB table changes
- Cognito changes
- CloudWatch dashboard or log-group configuration changes
- Bedrock-related permission or configuration changes where applicable

### CloudWatch Alarms

The platform has a basic dashboard and query workflow, but no alarms.

The next step is not to create a large alarm set blindly. The next step is to define which signals are operationally important, which ones already have usable structured events, and which ones need baseline observation before thresholds can be trusted.

### Log And Audit Retention

Current observability depends on CloudWatch Logs plus evidence captured through runbooks and dashboard screenshots. The repository does not yet define the retention window that should be preserved for:

- Lambda logs
- audit event logs
- security review screenshots
- evaluation artifacts

The hardening task here is to define retention expectations before implementing retention settings.

### DynamoDB Evidence Retention

The platform stores evidence in DynamoDB through:

- trace records
- approval records
- incident-report records

Retention expectations are not yet documented. The main design question is how long to retain operational evidence versus how long to retain business or incident records.

### Approval / Execution Audit Preservation

Approval audit quality is one of the stronger current control stories in the repository. That evidence needs preservation planning so operators can still reconstruct:

- who proposed the action
- who approved or rejected it
- who requested execution
- why execution was denied or allowed
- what internal record was created after execution

### Bedrock / Token Usage Evidence Retention

Phase 10B added practical generation-usage visibility. That creates a new evidence-preservation question:

- how long should token-usage-related logs and traces remain available for review
- how should teams preserve cost-related evidence used in internal reviews
- how should teams distinguish operational token evidence from future billing-grade cost analysis

### Incident Investigation Workflow

The current repository has logs, traces, approvals, incident reports, and a runbook, but not a single documented security-investigation workflow.

The Phase 10D goal is to define the minimum workflow for incident review:

1. identify the signal or alert
2. inspect request logs and traces
3. inspect approval and execution records where relevant
4. inspect control-plane change history once CloudTrail review is available
5. preserve screenshots, query output, and key request identifiers for the incident packet

## Prioritized Recommendations

### P0

- document the minimum WAF and edge-protection posture before broader internet exposure
- define the minimum CloudTrail review workflow for privileged and configuration changes
- define baseline retention expectations for logs, traces, approvals, and incident reports
- define the first alarm candidates for denial spikes, execution failures, and runtime health

### P1

- review API Gateway throttling posture by route rather than applying one generic limit
- define how Bedrock token-usage evidence should be retained for operational review
- define the evidence packet expected for security incidents and post-incident review

### P2

- expand alarm coverage once baseline noise is understood
- refine path-specific edge protections after real traffic patterns are reviewed
- formalize archival/export expectations for long-lived evidence artifacts

## Suggested Future Implementation Order

1. define retention expectations for logs, traces, approvals, and incident reports
2. define the minimum CloudTrail review workflow and responsible operator path
3. review API Gateway throttling posture and identify the first high-risk routes
4. define the first WAF slice focused on rate-based and common edge protections
5. observe baseline signal noise and then implement the first narrow alarm set
6. expand alarms and retention policy only after real usage data is available

## Acceptance Criteria

Phase 10D is acceptable when:

- the document describes the current baseline honestly
- it separates current implementation from future hardening work
- it explains WAF, CloudTrail review, alarms, and retention as distinct concerns
- it prioritizes concrete actions instead of abstract maturity language
- it keeps approval, execution, and token-usage evidence in scope for retention planning
- it does not claim that WAF, CloudTrail dashboards, alarms, or production retention are already implemented

## Current Implementation Boundary

Current implementation means:

- Cognito protects non-health routes
- `/rag/query` enforces application-level guardrail, policy, grounding, and trace behavior
- approval and execution events are auditable at the application layer
- a basic CloudWatch dashboard and runbook exist
- Bedrock generation token-usage fields are visible in application logs and traces where available

## Future Roadmap Boundary

Future roadmap means:

- WAF and edge-rule rollout
- CloudTrail review workflow and related dashboards if later chosen
- alarm implementation after baseline observation
- explicit retention settings and evidence preservation policies

These controls are planned here, not implemented here.