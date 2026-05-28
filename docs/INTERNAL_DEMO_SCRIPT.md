# Internal Demo Script

## Audience

Internal engineering managers, architects, delivery managers, or customer-facing technical reviewers.

## Duration

5–7 minutes.

## Opening Message

This is not a chatbot demo. It is a controlled AI application backend skeleton.

The point is to show how the backend controls retrieval, policy scope, tool use, approval, execution, and evidence, while the LLM stays inside those boundaries.

## Demo Story

1. Show health endpoint.
2. Show chat smoke test.
3. Index document.
4. Ask controlled RAG question.
5. Show guardrail blocked request.
6. Show `no_source` response.
7. Show policy denied response.
8. Show agent `answer_question` using `rag_query`.
9. Show trace lookup.
10. Show log search and investigation.
11. Show incident proposal.
12. Show human approval.
13. Show approved internal execution.
14. Show incident report lookup.
15. Show evaluation result.

## Talking Points Per Step

### 1. Show health endpoint

What to show:
Run `GET /health` and show the static service response.

What to say:
This confirms the deployed API surface is live before we touch any AI or stateful workflow behavior.

Why it matters:
It separates simple platform reachability from later AI-specific behavior.

### 2. Show chat smoke test

What to show:
Run `POST /chat` and show the response with `requestId`, `answer`, and `modelId`.

What to say:
This is a Bedrock smoke test only. It proves Bedrock connectivity, but it is not the controlled enterprise RAG path.

Why it matters:
It prevents the audience from confusing plain model invocation with the controlled application path.

### 3. Index document

What to show:
Run `POST /documents` using the demo-aligned document request file and show `status=indexed`.

What to say:
Here we index a known document into the PoC store with metadata and embeddings so later retrieval has a controlled evidence base.

Why it matters:
This shows that retrieval depends on indexed documents and metadata, not on hidden model memory.

### 4. Ask controlled RAG question

What to show:
Run `POST /rag/query` with the demo-aligned query file and show a completed response with sources.

What to say:
This is the real controlled path. The backend applies metadata eligibility, policy checks, similarity ranking, and only then generates a grounded answer.

Why it matters:
It demonstrates the difference between grounded application behavior and a generic chat answer.

### 5. Show guardrail blocked request

What to show:
Run the blocked prompt example and show `status=blocked` with guardrail details.

What to say:
The request is blocked before retrieval or grounded answer generation. The backend, not the model, decides that unsafe input does not proceed.

Why it matters:
It proves that safety controls exist before the LLM is allowed to influence output.

### 6. Show `no_source` response

What to show:
Run the unsupported question and show `status=no_source` with empty `sources`.

What to say:
When the platform cannot find grounded evidence, it refuses to present a grounded answer.

Why it matters:
This is the core anti-hallucination control in the current PoC.

### 7. Show policy denied response

What to show:
Run the disallowed filter example and show HTTP `403` with the denial message.

What to say:
Even if the document exists, the backend blocks retrieval when the caller requests a scope outside the allowed boundary.

Why it matters:
It shows that access scope is an application control, not an LLM choice.

### 8. Show agent `answer_question` using `rag_query`

What to show:
Run `POST /agent/run` with `task=answer_question` and highlight `toolCalls` including `rag_query`.

What to say:
The agent is not inventing a plan. It is using a fixed task path and an allowlisted read-only tool that goes through the same shared RAG service.

Why it matters:
It demonstrates that the agent is controlled orchestration, not a free-running agent runtime.

### 9. Show trace lookup

What to show:
Run agent `inspect_trace` or the trace viewer against a known prior `requestId`.

What to say:
Every important path leaves evidence behind. We can inspect blocked, successful, and no-source behavior after the request completes.

Why it matters:
Traceability is what makes the platform debuggable and reviewable.

### 10. Show log search and investigation

What to show:
Run `search_logs` and `investigate_recent_blocks`, or show the log helper output if you want a direct script-based view.

What to say:
The platform supports bounded operational investigation. It can search recent logs and correlate those events back to trace data.

Why it matters:
This is the operational bridge between runtime events and request-level evidence.

### 11. Show incident proposal

What to show:
Run `propose_incident_report` and show `status=approval_required`, `approvalId`, and `proposedAction`.

What to say:
This is the write boundary. The agent can propose an internal action, but it cannot execute it directly.

Why it matters:
It demonstrates separation between analysis and execution.

### 12. Show human approval

What to show:
Run `POST /approvals/{approvalId}/decision` and optionally fetch the approval record afterward.

What to say:
Approval changes state, but it still does not execute the action. Human review is an explicit checkpoint, not a cosmetic flag.

Why it matters:
It shows that approval and execution are separate controls.

### 13. Show approved internal execution

What to show:
Run `POST /approvals/{approvalId}/execute` and show `status=executed` plus `reportId`.

What to say:
The executor validates state and action type before it writes anything. It only supports one internal action in the current PoC.

Why it matters:
This proves the system does not equate approval with unconstrained execution.

### 14. Show incident report lookup

What to show:
Run `GET /incident-reports/{reportId}` and show the stored record.

What to say:
The execution produced a real internal artifact that can be retrieved and inspected.

Why it matters:
It closes the loop from proposal to approval to validated internal write.

### 15. Show evaluation result

What to show:
Show `scripts/run_rag_eval.py` results, especially the pass count and generated report files.

What to say:
The platform is not judged only by one live demo. It also has a small repeatable evaluation path covering selected RAG, agent, approval, and execution cases.

Why it matters:
Evaluation is the first step toward defensible confidence.

## Key Message To Repeat

- The LLM does not control the system.
- The backend controls data access, tool use, approval, and trace.
- The agent can propose; humans approve; executor validates.
- Evidence is available through traces, logs, and evaluation.

## Current Implementation Versus Future Roadmap

Current implementation:

- serverless backend foundation
- Bedrock chat smoke test
- embedding-based mini RAG
- metadata and header-based policy boundary
- input and output guardrails
- request traces and CloudWatch logs
- read-only agent tools and bounded investigation
- approval workflow plus one approved internal executor path

Future roadmap:

- real authentication and authorization
- identity-backed policy enforcement
- scalable vector retrieval
- stronger guardrails and operational controls
- production-grade incident workflow design

## Closing Message

The current PoC is not production-ready, and it does not claim to be. What it does show is the right control pattern: retrieval boundary first, policy boundary first, trace first, approval before execution, and evidence after the fact.

Recommended next step: move to Phase 8A and design a real authentication and authorization boundary so the current header-based learning model can be replaced with identity-backed claims and enforceable access rules.