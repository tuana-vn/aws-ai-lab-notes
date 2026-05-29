# CloudTrail Audit And Retention Plan

## Purpose

This document defines a practical plan for adding AWS control-plane audit review and evidence-retention guidance around the current `aws-ai-platform-poc` baseline.

It does not claim that a CloudTrail dashboard or CloudTrail review workflow is already implemented.

## Current Audit Posture

The current repository already has useful application-level audit and observability for runtime behavior. It does not yet document the control-plane audit layer for AWS configuration and privileged changes.

Current strengths:

- structured application logs
- request traces in DynamoDB
- approval and execution lifecycle audit events
- a basic operational dashboard and runbook
- Bedrock generation token-usage visibility where available

Current gap:

- no documented CloudTrail-focused review workflow
- no documented control-plane dashboard
- no documented retention policy for application evidence and screenshots

## Difference Between Application Audit And AWS Control-plane Audit

Application audit answers questions such as:

- was a RAG request denied
- was a request blocked by the input guardrail
- did a query return `no_source`
- who created, approved, denied, requested execution for, or executed an approval-driven action

AWS control-plane audit answers different questions:

- who changed IAM permissions or roles
- who updated Lambda code or configuration
- who changed API Gateway settings
- who changed DynamoDB tables or indexes
- who changed Cognito configuration
- who changed CloudWatch dashboards or log settings

Both layers are necessary for a serious incident review.

## What Application Audit Already Covers

The current application audit story already covers these event types and outcomes:

- RAG denial
- guardrail block
- `no_source`
- `approval_created`
- `approval_decided`
- `approval_execute_requested`
- `approval_execute_denied`
- `approval_executed`
- `incident_report_created`

This is one of the strongest current evidence areas in the repository.

## What CloudTrail Would Cover

CloudTrail planning should focus on review of:

- IAM changes
- Lambda updates
- API Gateway changes
- DynamoDB table changes
- Cognito changes
- CloudWatch dashboard and log changes
- Bedrock permission or related configuration changes where applicable

The purpose is not to replace application audit. The purpose is to explain how operators would review AWS-side changes when investigating an incident or unexpected platform behavior.

## Minimum CloudTrail Review Workflow

The minimum review workflow should be:

1. identify the incident window and affected service area
2. review application logs and traces for the request-level story
3. review approval and execution events if the incident touched agent or approval flows
4. review CloudTrail for privileged or configuration changes in the same time window
5. preserve the relevant queries, screenshots, and identifiers in an incident evidence packet

This workflow is intentionally small. It is better to start with a workable operator path than with a large but unused audit process.

## Retention Recommendations

### CloudWatch Logs

Recommendation:

- define an explicit retention window for Lambda logs instead of leaving retention unspecified
- treat security and audit-heavy logs as evidence sources, not just debugging output

### DynamoDB Trace Records

Recommendation:

- define how long trace records remain queryable for security and post-incident review
- decide whether older trace records should expire, archive, or be preserved for named evidence cases

### Approval Records

Recommendation:

- preserve approval records longer than short-lived debugging traces because they capture decision history and execution intent

### Incident Report Records

Recommendation:

- preserve incident report records according to incident-handling and internal review expectations, not just runtime-debug expectations

### Dashboard / Evidence Screenshots

Recommendation:

- define where screenshots, Logs Insights output, and internal evidence captures are stored
- define minimum naming and timestamping expectations so those artifacts are usable later

## Evidence Preservation Model

The evidence-preservation model should keep three ideas separate:

- short-lived operational debugging data
- medium-lived security and audit review data
- long-lived incident evidence and approval history

The exact retention periods are future implementation decisions. Phase 10D defines the model and the preservation categories, not the final durations.

## Risks And Open Questions

The main risks and open questions are:

- how long should logs remain queryable before cost and noise become a problem
- should trace retention differ from approval retention
- which team owns the control-plane review process
- how should evidence screenshots and exported query results be preserved consistently
- how should Bedrock-related configuration or permission changes be reviewed when incidents affect AI behavior

## Out Of Scope

This document does not:

- create or configure CloudTrail
- create a CloudTrail dashboard
- define final retention durations
- add export jobs or archival infrastructure
- claim that control-plane audit review is already operational

## Current Implementation Boundary

Current implementation means the repository already has application audit, traces, logs, approvals, and incident-report evidence, but not CloudTrail workflow documentation.

## Future Roadmap Boundary

Future roadmap means introducing CloudTrail review process, explicit retention settings, and evidence-preservation procedures.