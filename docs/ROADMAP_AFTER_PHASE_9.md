# Roadmap After Phase 9

## Purpose

This document outlines the recommended roadmap after Phase 9 for the current `aws-ai-platform-poc` repository.

It is a planning document, not an implementation claim. Each phase below describes recommended work that can build on the current PoC baseline without pretending that the hardening work already exists.

## Current Implementation Boundary

The current repository already includes:

- authenticated non-health routes through Cognito
- backend policy enforcement on `/rag/query`
- metadata boundary controls for project and customer filters
- input and output guardrails in the RAG path
- a controlled agent with allowlisted tools and fixed tasks
- separated approval decision and approval execute permissions
- structured approval and execution audit events
- a basic CloudWatch dashboard and operator runbook

The roadmap below covers recommended next work beyond that current baseline.

## Phase 10A - Production Hardening Gap Review

### Objective

Create a practical production-readiness gap review for the current PoC.

### Why It Matters

The platform already demonstrates useful control boundaries and observability, but teams need a grounded view of what still separates the PoC from a more production-ready service.

### Scope

- review current gaps across identity, authorization, retrieval, governance, audit, reliability, deployment, and operations
- prioritize the gaps by practical risk and implementation urgency
- document concrete next actions rather than abstract maturity language

### Out Of Scope

- code changes
- infrastructure changes
- alarm implementation
- claims that the repository is production-ready

### Deliverables

- [docs/PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md](docs/PHASE_10A_PRODUCTION_HARDENING_GAP_REVIEW.md)
- [docs/PRODUCTION_READINESS_CHECKLIST.md](docs/PRODUCTION_READINESS_CHECKLIST.md)

### Acceptance Criteria

- the review stays grounded in the actual repository state
- the highest-risk gaps are clearly prioritized
- the checklist is practical enough to drive later hardening work
- current implementation is separated from future roadmap recommendations

## Phase 10B - Cost And Token Usage Observability

### Objective

Add a practical observability plan for Bedrock token usage and cost behavior.

### Why It Matters

The repository currently has useful application observability but no cost or token-usage view. That makes it harder to understand scaling impact, expensive prompt patterns, and cost drift.

### Scope

- define the minimum cost and token signals needed by operators and platform owners
- describe where those signals should come from and how they should be reviewed
- document a cost and token dashboard design or evidence workflow before any hardening implementation

### Out Of Scope

- claiming a production-grade cost dashboard already exists
- inventing token telemetry that the current runtime does not emit
- broader security hardening unrelated to cost visibility

### Deliverables

- a Phase 10B design document for cost and token observability
- a clear list of current gaps versus future implementation targets

### Acceptance Criteria

- the phase explains what cost and token visibility are missing today
- the design stays aligned with the current AWS and application architecture
- the document does not claim existing implementation where none exists

## Phase 10C - RAG Upgrade Path: Bedrock Knowledge Bases Or OpenSearch

### Objective

Evaluate and document the production-oriented retrieval path beyond the current DynamoDB scan and in-Lambda similarity model.

### Why It Matters

The current retrieval implementation is explicitly learning-focused. A production-oriented RAG path needs a more scalable retrieval architecture with clearer performance and operational tradeoffs.

### Scope

- compare Bedrock Knowledge Bases and OpenSearch-based retrieval as candidate upgrade paths
- map the tradeoffs in governance, retrieval quality, latency, operational complexity, and evidence visibility
- describe the migration implications for the current metadata-boundary and policy model

### Out Of Scope

- implementing a new vector store in this planning phase
- claiming either candidate is already integrated
- redesigning unrelated approval or agent behavior

### Deliverables

- a Phase 10C architecture decision or options review
- a migration path outline from the current retrieval baseline

### Acceptance Criteria

- the tradeoffs are concrete and backend-architect friendly
- the current learning-focused retrieval baseline is described honestly
- the result points to a practical next implementation slice

## Phase 10D - Security Hardening: WAF, CloudTrail, Alarms, Retention

### Objective

Define the next security-hardening layer around edge protection, control-plane audit visibility, alerting, and retention policy.

### Why It Matters

The repository now has useful application-level controls and audit visibility, but it still lacks several production-oriented hardening layers such as WAF posture, CloudTrail review workflows, CloudWatch alarms, and clearer retention expectations.

### Scope

- define WAF and edge-protection expectations
- define control-plane audit and CloudTrail review needs
- define an initial alarm set only after baseline behavior is understood
- define retention expectations for logs and evidence stores

### Out Of Scope

- claiming WAF, CloudTrail dashboards, or alarms are already implemented
- broad platform redesign unrelated to security hardening
- changing application code in this planning phase

### Deliverables

- a Phase 10D security-hardening plan
- alarm candidates and retention recommendations
- a clear separation between current controls and future controls

### Acceptance Criteria

- the plan identifies the highest-value missing security controls
- alarm recommendations are tied to concrete signals rather than vague aspirations
- the phase does not overclaim current implementation

## Phase 10E - Reliability Hardening: Retry, DLQ, Idempotency, Rollback

### Objective

Review and define the reliability hardening needed for safer operation under failure, retries, and deployment change.

### Why It Matters

The PoC demonstrates functional correctness, but production services need more explicit handling for replay safety, failure recovery, rollback, and environment hygiene.

### Scope

- define idempotency expectations for critical write paths
- review failure recovery and retry behavior for Lambda-backed flows
- define DLQ or equivalent failure-handling expectations where appropriate
- document rollback and deployment recovery expectations

### Out Of Scope

- claiming reliability controls already exist when they are not yet documented or implemented
- changing runtime behavior in this planning phase
- expanding the functional scope of the application

### Deliverables

- a Phase 10E reliability-hardening review
- a prioritized list of failure-mode improvements and release-safety actions

### Acceptance Criteria

- the review covers both request-level and deployment-level reliability concerns
- the proposed hardening steps are concrete enough to implement incrementally
- the document stays honest about the current PoC baseline

## Phase 11 - Internal/Customer Presentation Package

### Objective

Convert the architecture, evidence, audit, and hardening story into a presentation package suitable for internal stakeholders and selected customer-facing conversations.

### Why It Matters

The repository now contains strong technical documentation, but audiences outside the immediate implementation loop still need a concise and accurate way to understand the platform, its control boundaries, and its roadmap.

### Scope

- create a concise presentation narrative for architecture, boundaries, auditability, and roadmap
- build audience-appropriate material for backend engineers, architects, managers, and security-minded reviewers
- reuse the evidence pack, demo script, and hardening review as supporting material

### Out Of Scope

- claiming customer-ready product maturity
- changing platform behavior
- replacing the detailed technical docs with marketing-style material

### Deliverables

- a Phase 11 presentation outline or package
- supporting screenshots, diagrams, and evidence references suitable for internal or customer discussion

### Acceptance Criteria

- the presentation remains technically accurate
- the material separates current implementation from future roadmap clearly
- the package is concise enough to support real stakeholder review

## Roadmap Principles

Use these principles across the post-Phase-9 roadmap:

- prefer practical hardening work over abstract maturity language
- separate current implementation from future recommendations
- avoid claiming that future AWS services or controls already exist
- keep the roadmap grounded in concrete backend, security, reliability, and operational outcomes