# Production Readiness Checklist

This checklist tracks production-hardening work for the current `aws-ai-platform-poc` repository.

It is intentionally honest about current status. A checked item should mean the repository and its operating model actually satisfy that expectation, not that it sounds desirable.

## Already Demonstrated In The PoC

- Cognito protects non-health routes.
- `/rag/query` enforces project and customer policy after authentication.
- Metadata filtering, input guardrails, output guardrail warnings, and trace records exist.
- The controlled agent uses fixed tasks and allowlisted tools.
- Approval decision and approval execution are permission-separated.
- Execution remains limited to internal incident-report creation.
- Phase 9 added structured approval and execution audit events.
- Phase 9C added a basic CloudWatch dashboard and operational runbook.

## Security

- [ ] Define the production identity and token model
  - Current status: Cognito protects non-health routes, but the PoC still uses an ID token for convenience and does not yet define a production identity model.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: document the production identity boundary, token expectations, and enterprise IdP integration plan.

- [ ] Remove or isolate trusted-header fallback from production environments
  - Current status: trusted-header fallback remains for local or unprotected compatibility.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define the deprecation or isolation approach for production deployments.

- [ ] Review edge protection and WAF posture
  - Current status: no WAF hardening is implemented.
  - Evidence: [PHASE_9_FINAL_SUMMARY.md](PHASE_9_FINAL_SUMMARY.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define internet-facing protection, request filtering, and rate-control expectations.

- [ ] Define a control-plane audit posture
  - Current status: there is no CloudTrail-focused operational dashboard or documented control-plane review workflow in the repository.
  - Evidence: [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define the minimum CloudTrail and privileged-access review model.

## Authorization

- [ ] Expand route-level permission coverage beyond approval endpoints
  - Current status: only approval decision and approval execute currently enforce explicit route-level permissions.
  - Evidence: [README.md](../README.md), [PHASE_8_FINAL_AUTHORIZATION_EVIDENCE.md](PHASE_8_FINAL_AUTHORIZATION_EVIDENCE.md)
  - Next action: create a route-to-permission matrix for the remaining protected routes.

- [ ] Document the tenant, project, and customer access model across all data-reading routes
  - Current status: `/rag/query` has the clearest project and customer boundary; broader route mapping is not yet formalized.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: document the authoritative boundary model and map it across routes and data flows.

## RAG Quality

- [ ] Replace learning-focused retrieval with a production retrieval architecture
  - Current status: retrieval uses DynamoDB scan plus in-Lambda cosine similarity for learning purposes.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: evaluate Bedrock Knowledge Bases or a dedicated vector index path.

- [ ] Define a guardrail review and regression process
  - Current status: input and output guardrails exist, but there is no formal ongoing review or alerting model.
  - Evidence: [PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md](PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define regular adversarial tests, review ownership, and escalation criteria.

## Agent Governance

- [ ] Formalize change control for agent tasks and tools
  - Current status: the agent is bounded in code, but change-control expectations for expanding scope are not yet formalized.
  - Evidence: [AGENT_WORKFLOW_AND_APPROVAL_BOUNDARY.md](AGENT_WORKFLOW_AND_APPROVAL_BOUNDARY.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define the approval process for adding new tasks, tools, or action types.

## Approval And Execution

- [ ] Preserve separation between approval and execution as action scope grows
  - Current status: approval and execution are separated, and execution is limited to `create_incident_report`.
  - Evidence: [PHASE_9B_APPROVAL_EXECUTION_AUDIT_EVENTS.md](PHASE_9B_APPROVAL_EXECUTION_AUDIT_EVENTS.md), [AGENT_WORKFLOW_AND_APPROVAL_BOUNDARY.md](AGENT_WORKFLOW_AND_APPROVAL_BOUNDARY.md)
  - Next action: define action taxonomy, approval criteria, and preconditions before adding any new executable action.

- [ ] Add idempotency and replay-safety review for execution paths
  - Current status: the current docs do not yet define execution idempotency and replay-handling expectations.
  - Evidence: [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: review failure and retry modes for approval execution and incident-report creation.

## Observability And Audit

- [ ] Define production retention and evidence-preservation expectations
  - Current status: logs, traces, approval records, and incident reports exist, but production retention policy is not documented.
  - Evidence: [PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md](PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define retention, export, and evidence-handling requirements.

- [ ] Add a first production alarm set after baselines are understood
  - Current status: a basic dashboard and Logs Insights workflow exist, but there are no CloudWatch alarms yet.
  - Evidence: [PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md](PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md), [PHASE_9_FINAL_SUMMARY.md](PHASE_9_FINAL_SUMMARY.md)
  - Next action: identify baseline thresholds for denial spikes, execution failures, and availability indicators.

## Reliability

- [ ] Define retry, DLQ, and failure-recovery expectations
  - Current status: the repository demonstrates functional flows but does not yet document production reliability controls such as DLQ posture and recovery handling.
  - Evidence: [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: review Lambda failure modes, write failures, and recovery behavior for critical paths.

- [ ] Define rollback and environment-promotion controls
  - Current status: SAM / CloudFormation are used, but production deployment workflow, rollback policy, and environment separation are not yet documented.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define release promotion flow, rollback ownership, and environment boundaries.

## Cost

- [ ] Add token and cost observability
  - Current status: there is no production-grade cost dashboard and no token-usage observability in the current repository.
  - Evidence: [PHASE_9_FINAL_SUMMARY.md](PHASE_9_FINAL_SUMMARY.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define the minimum dataset for Bedrock token and cost tracking.

## Deployment

- [ ] Define production configuration and secret-management ownership
  - Current status: the repository uses configuration and environment variables, but a production configuration-management model is not yet documented.
  - Evidence: [README.md](../README.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define secret rotation, environment-specific configuration ownership, and operational access boundaries.

## Operations

- [ ] Define service ownership and operational decision rights
  - Current status: the repository has strong design and runbook docs, but operational ownership is not yet formalized.
  - Evidence: [PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md](PHASE_9C_CLOUDWATCH_DASHBOARD_RUNBOOK.md), [PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
  - Next action: define runtime ownership, access-policy ownership, observability ownership, and release-decision ownership.

- [ ] Expand the production test matrix and regression ownership
  - Current status: unit tests, RAG evaluation, and evidence workflows exist, but a broader production test strategy is not yet documented.
  - Evidence: [README.md](../README.md), [PHASE_9D_OBSERVABILITY_EVIDENCE_PACK.md](PHASE_9D_OBSERVABILITY_EVIDENCE_PACK.md)
  - Next action: define sustained test ownership for auth boundaries, permission boundaries, guardrails, retrieval quality, and failure cases.