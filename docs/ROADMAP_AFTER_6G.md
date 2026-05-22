# Roadmap After 6G

## Current Baseline

After Phase 6G, the PoC has a coherent backend baseline with the following capabilities:

- API Gateway plus Lambda entrypoints for health, echo, chat, documents, RAG, agent, approvals, and incident report lookup
- Bedrock-backed chat and grounded RAG answer generation
- document chunking plus embedding persistence in DynamoDB
- metadata filtering and a learning policy gate for RAG scope control
- input and output guardrail checks
- DynamoDB request tracing and CloudWatch runtime logs
- local evaluation and trace/log inspection scripts
- controlled agent orchestration with allowlisted read-only tools
- approval-bound action proposal flow
- approved internal executor that creates a DynamoDB incident report record only

This is already enough to explain a backend-architect view of controlled RAG and bounded agent behavior on AWS.

## Phase 7A Documentation Checkpoint

Phase 7A is a documentation checkpoint rather than a new runtime feature phase.

The purpose is to make the current implementation explainable before the next set of upgrades. That means documenting:

- current architecture
- current control boundaries
- current observability model
- current approval and executor flow
- explicit separation between today’s implementation and tomorrow’s roadmap

## Future Phase Groups

The items below are future direction only. They are not part of the current Phase 6G implementation.

### 1. Production-grade RAG upgrade

Target improvements:

- replace DynamoDB scan-based retrieval with indexed vector retrieval
- add better ranking and possibly reranking
- strengthen grounding validation
- define stronger chunking and document ingestion strategy
- add scale-aware retrieval performance controls

Why it matters:

The current retrieval flow is excellent for learning and debugging, but it is not the shape of a production retrieval subsystem.

### 2. Real authentication and authorization

Target improvements:

- replace header-based learning identity with real authentication
- validate claims at the API boundary
- bind retrieval and execution rights to verified identity
- separate reader, approver, and executor roles where needed

Why it matters:

The current header-based access model demonstrates where the policy gate belongs, but it should not be treated as a production auth system.

### 3. Managed agent service mapping

Target improvements:

- map the current controlled orchestration model to a managed agent or workflow service where appropriate
- preserve tool allowlists and approval boundaries during that transition
- keep execution deterministic and auditable even if orchestration becomes more capable

Why it matters:

The current agent shows the right control patterns. Future work can decide whether a managed orchestration layer adds value without weakening those boundaries.

### 4. Production operations

Target improvements:

- CloudWatch dashboards and alarms
- stronger trace and log schema discipline
- token and cost tracking
- idempotency and retry strategy for execution paths
- tighter IAM scoping and security reviews
- retention and archive strategy for trace and approval data

Why it matters:

The current PoC is observable enough for learning, but production support requires stronger operational controls.

### 5. Presentation package

Target improvements:

- architecture slides derived from the documented flows
- short demo script for RAG, agent investigation, approval, and internal execution
- stakeholder-friendly diagrams that map directly to the implemented handlers and tables
- concise talking points that distinguish current scope from future scope

Why it matters:

The PoC is now rich enough to be explained as a coherent platform story, not just a set of disconnected features.

## Roadmap Guardrails

As future phases are added, these rules should stay intact unless deliberately redesigned:

- do not blur proposal, approval, and execution into one opaque step
- do not give the agent uncontrolled tool access
- do not hide the trace and evaluation story behind abstractions that remove debuggability
- do not introduce external side effects without stronger identity, approval, and audit controls

## Suggested Next Working Order

If work continues after Phase 7A, a reasonable order is:

1. strengthen authentication and authorization
2. upgrade retrieval architecture
3. improve observability and operational controls
4. evaluate managed orchestration mapping
5. package the architecture and demo material for broader presentation