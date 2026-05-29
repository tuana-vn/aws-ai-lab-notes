# Deployment Rollback And Environment Strategy

## Purpose

This document defines a target deployment, rollback, and environment-separation strategy for the current `aws-ai-platform-poc` repository.

It does not claim that CI/CD, multiple deployed environments, or a production release process already exist. The current repository provides the infrastructure template and a default deploy shape, but the broader release operating model remains future work.

## Current Deployment Baseline

The current repository baseline includes:

- AWS SAM and CloudFormation for infrastructure deployment
- an `EnvironmentName` template parameter used to namespace resources
- a default SAM deploy configuration oriented around `dev`
- manual deployment guidance in the README using `sam build` and `sam deploy --guided`
- no documented CI/CD workflow in the repository

This is a practical PoC deployment shape, not a production release model.

## SAM / CloudFormation Rollback Behavior

CloudFormation can roll back failed stack updates, but that is not the same thing as having a complete release rollback strategy.

For this repository, rollback planning must cover both:

- infrastructure rollback behavior managed by CloudFormation
- release-level rollback decisions made by operators after deployment and smoke-test review

The current repo does not yet document when the team should roll back infrastructure, when it should forward-fix, or what evidence should be captured before that decision.

## Risks In Current Deployment Workflow

The main current risks are:

- deployment is documented primarily as a manual workflow
- no formal promotion path is documented beyond the default `dev` deploy shape
- no standard rollback checklist is documented
- no post-deploy smoke-test checklist is documented as a release gate
- no release evidence packet is defined for change review

## Environment Separation

The sections below describe a target strategy. They do not claim these environments already exist.

### Dev

Target purpose:

- fast iteration
- local or developer-driven validation
- lower-confidence experiments and document-ingestion tests

### Test / Staging

Target purpose:

- integration checks against a more stable environment
- smoke-test and regression execution before broader rollout
- controlled validation of approval, execution, and retrieval behavior

### Production-like

Target purpose:

- release-candidate validation against production-shaped configuration and evidence workflows
- rehearsal for rollback, smoke tests, and release review

### Production

Target purpose:

- highest-control environment
- strongest access, release, audit, and rollback discipline
- no experimental traffic or ad hoc validation behavior

## Configuration Separation

Target strategy:

- keep environment-specific configuration out of ad hoc manual edits
- make environment overrides explicit and reviewable
- separate model IDs, table names, API base URLs, and other environment-bound values cleanly

The current repository supports parameterized naming, but does not yet document a full configuration-governance model.

## Token / User Pool Separation

Target strategy:

- use separate Cognito resources and tokens per environment
- do not reuse user pools or client tokens across release stages
- keep test identities and production identities operationally distinct

The template supports environment-namespaced resources, but the broader multi-environment identity model is not yet documented.

## DynamoDB Table Separation

Target strategy:

- keep trace, document, approval, and incident-report tables separated by environment
- avoid sharing operational evidence tables across release stages
- treat production data and lower-environment test data as fully separate

The template already names tables by `EnvironmentName`, which supports this target strategy.

## Dashboard / Log Group Separation

Target strategy:

- keep CloudWatch dashboards, log groups, and operational queries environment-specific
- avoid mixing dev, test, and production-like signals in one operator view

The repository does not yet document a full multi-environment observability model, so this remains a target guideline.

## Rollback Checklist

Suggested rollback checklist:

1. confirm the failing change window and impacted routes
2. gather the deployment identifiers, stack events, and operator notes
3. run the post-deploy smoke tests against the affected environment
4. decide whether the issue is infrastructure rollback material or a faster forward-fix case
5. confirm whether any data writes need manual review before rollback
6. capture logs, traces, and dashboard evidence for the release record
7. execute rollback or forward-fix under named owner approval

## Pre-deploy Checklist

Suggested pre-deploy checklist:

1. confirm target environment and parameter values
2. confirm which docs and evidence describe the expected behavior of the release
3. review high-risk routes: `/documents`, `/rag/query`, `/agent/run`, approval decision, and approval execute
4. confirm the release does not rely on undocumented manual configuration
5. confirm smoke-test commands and test tokens are prepared for the target environment

## Post-deploy Smoke Tests

Suggested post-deploy smoke tests:

1. `GET /health`
2. protected route rejection without token on a protected endpoint
3. authenticated `/chat`
4. authenticated `/documents`
5. authenticated `/rag/query`
6. approval read, decision, and execute workflow in a controlled test case when appropriate
7. review logs and traces for expected request records after the smoke tests

## Release Evidence To Capture

For each release, capture:

- target environment name
- stack or deployment identifier
- changed files or release scope summary
- smoke-test results
- notable Logs Insights output or dashboard screenshots where relevant
- rollback or forward-fix decision record if issues are found

## Future CI / CD Direction

The repository does not currently include a documented CI/CD workflow.

Future direction should emphasize:

- repeatable build and deploy steps
- environment-specific promotion controls
- release evidence capture
- rollback ownership and approval
- smoke-test automation where it is safe and meaningful

## Acceptance Criteria

Phase 10E deployment planning is acceptable when:

- the document describes the current deployment baseline honestly
- it distinguishes current manual deployment from future promotion strategy
- it treats environment separation as a target model unless it is actually documented and deployed
- it provides practical pre-deploy, post-deploy, and rollback checklists
- it does not claim CI/CD, production rollout, or full multi-environment operation already exists

## Current Implementation Boundary

Current implementation means SAM and CloudFormation deployment, an `EnvironmentName` parameter, and a default `dev` deploy shape, without a documented production promotion model.

## Future Roadmap Boundary

Future roadmap means explicit environment promotion, configuration governance, release evidence, and rollback ownership.