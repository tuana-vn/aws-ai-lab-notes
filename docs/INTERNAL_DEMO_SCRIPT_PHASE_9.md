# Internal Demo Script: Phase 9

## Purpose

This is a 5 to 7 minute internal demo script for the current Phase 9 implementation.

The script is designed for:

- backend engineers
- architects
- managers
- security-minded reviewers

The focus is practical system behavior, not chatbot theatrics.

## Demo Preparation

Have these items ready before presenting:

- `API_BASE_URL`
- `AUTH_TOKEN`
- `APPROVER_TOKEN`
- `OPERATOR_TOKEN`
- `AWS_REGION`
- `RAG_QUERY_LOG_GROUP`
- `AGENT_RUN_LOG_GROUP`
- `APPROVALS_LOG_GROUP`
- `DASHBOARD_NAME`
- a terminal with `curl`, AWS CLI, and the helper scripts available
- one browser tab open to the CloudWatch dashboard

Do not display raw JWTs, passwords, or secrets on screen.

## Demo Script

| Time | Segment | Speaker Notes | Suggested Screen Actions |
| --- | --- | --- | --- |
| 0:00-0:30 | Opening | This is not a chatbot demo. It is a backend control-boundary and observability demo. The goal is to show what the system allows, what it denies, how grounded answers behave, how internal actions require approval, and what operators can now audit in CloudWatch. | Start on the README or architecture diagram, not on a chat UI. |
| 0:30-1:00 | Architecture Recap | The current PoC is API Gateway, Cognito, Lambda, DynamoDB, CloudWatch Logs, and Bedrock. `GET /health` is public. All other routes are Cognito protected. The interesting parts are the backend policy gate on `/rag/query`, the controlled agent on `/agent/run`, and the separate approval and execution endpoints. | Show the architecture section in the README, then switch to a terminal. |
| 1:00-1:30 | Security Boundary Demo | First show the public route, then show that a protected route without a token is rejected. That proves we do not rely on polite clients. The first boundary is enforced before application logic is allowed to proceed. | Run `curl "$API_BASE_URL/health"`, then run a tokenless `POST /rag/query` and highlight the rejection status. |
| 1:30-2:10 | RAG Grounding Demo | Now show a valid authenticated RAG request. Call out that authentication is necessary but not sufficient. The request still needs to stay within allowed metadata scope and produce grounded evidence. Emphasize the answer, source list, and request ID. | Run an authenticated `POST /rag/query` with allowed filters. Pause on the response body and point to `requestId` and sources. |
| 2:10-2:40 | Guardrail Demo | Next show that unsafe requests can be blocked before retrieval and generation. This is important because the demo is about controlled behavior, not just successful responses. If you already have a prepared blocked example, use that to save time. | Run or show a prepared blocked `/rag/query` call, then switch to `scripts/query_logs.py --preset blocked` for the RAG log group. |
| 2:40-3:20 | Controlled Agent Demo | The agent is not free-running. It has fixed tasks and allowlisted tools. For the demo, use `propose_incident_report`, because it creates a proposal instead of executing anything. The important result is an `approvalId`, not magic automation. | Run `POST /agent/run` with `{"task":"propose_incident_report","minutes":120}` and keep the response visible. |
| 3:20-4:00 | Human Approval Demo | Now switch roles. An approver can decide, but that does not execute the action. This is where the separation between approval and execution becomes visible in both the API behavior and the audit trail. | Run `POST /approvals/{approvalId}/decision` with the approver token and show the `approved_not_executed` state in the response. |
| 4:00-4:30 | Execution Audit Demo | Then show that the approver still cannot execute. Use the same approval ID and call the execute endpoint with the approver token to demonstrate the permission boundary. After that, call execute with the operator token. Point out that successful execution only creates an internal DynamoDB incident report record. | First run the denied execute call with the approver token. Then run the successful execute call with the operator token and capture the returned `reportId`. |
| 4:30-5:20 | Dashboard And Runbook Demo | Move to operator evidence. Show the query workflow for `approval_created`, `approval_decided`, `approval_execute_denied`, `approval_executed`, and `incident_report_created`. Then switch to the CloudWatch dashboard and show that it is a basic operational view, not a production SOC dashboard. | Run `scripts/query_logs.py` against the agent and approvals log groups, then open the CloudWatch dashboard and point to the key widgets. |
| 5:20-5:50 | Current Limitations | Be explicit about what is not here. This is not production-ready. There are no alarms yet. There is no WAF, CloudTrail dashboard, X-Ray, OpenTelemetry, OpenSearch retrieval, or Bedrock Knowledge Base implementation in this PoC. The dashboard is useful, but intentionally basic. | Leave the dashboard or docs visible while you summarize the limitations. |
| 5:50-6:20 | Next Roadmap | The next work is straightforward to explain: production hardening review, cost and token observability, retrieval-platform options, and broader security hardening such as alarms, retention, WAF, and CloudTrail where justified. Keep this separate from current implementation so nobody leaves with the wrong impression. | Switch to the final summary doc and highlight the recommended next phases section. |

## Speaker Notes By Topic

### Opening

Say this clearly:

"This is not a chatbot demo. It is a control-boundary, auditability, and operator-visibility demo for the current backend PoC."

### Security Boundary

Stress these points:

- `GET /health` is public by design
- all non-health routes are Cognito protected
- protected access does not bypass backend policy checks

### RAG Grounding

Stress these points:

- `/rag/query` is the controlled path, not `/chat`
- metadata filters and policy checks still apply after authentication
- the system can return `no_source` instead of pretending to know

### Controlled Agent

Stress these points:

- the agent has fixed tasks and allowlisted tools
- `propose_incident_report` creates a proposal only
- proposal creation emits `approval_created`

### Human Approval And Execution

Stress these points:

- approval and execution are intentionally separate
- `approvals:decide` and `approvals:execute` are different permissions
- execution remains restricted to `create_incident_report`
- successful execution creates an internal incident report record only

### Dashboard And Runbook

Stress these points:

- operators can use the runbook queries today
- the CloudWatch dashboard now exists after Phase 9C deployment
- it is a basic PoC operational view, not a production-grade monitoring system

## Current Implementation

When summarizing the demo, stay inside the current implementation boundary:

- deployed basic CloudWatch dashboard
- practical Logs Insights workflow
- normalized approval and execution audit events
- current permission split between approver and operator roles

## Next Roadmap

Discuss the roadmap only in this section:

1. Phase 10A - Production Hardening Gap Review
2. Phase 10B - Cost and Token Usage Observability
3. Phase 10C - RAG Upgrade Path: Bedrock Knowledge Bases or OpenSearch
4. Phase 10D - Security Hardening: WAF, CloudTrail, alarms, retention
5. Phase 11 - Internal and Customer Presentation Package
