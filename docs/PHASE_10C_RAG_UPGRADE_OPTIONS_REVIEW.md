# Phase 10C RAG Upgrade Options Review

## Purpose

This document reviews practical architecture options for evolving the current learning-focused mini RAG implementation into a more production-oriented retrieval architecture.

It does not implement Bedrock Knowledge Bases or OpenSearch, and it does not claim either option is already integrated. The goal is to compare realistic upgrade paths against the current repository behavior so later implementation work starts from clear tradeoffs rather than generic platform language.

## Current Mini RAG Baseline

The current mini RAG path is implemented around the following runtime shape:

- `/documents` chunks documents, creates embeddings, and stores chunk records plus embeddings in DynamoDB
- `/rag/query` resolves `AccessContext`, applies an input guardrail, applies the backend policy gate, applies metadata filtering, embeds the question, scans chunk records, ranks eligible chunks in Lambda with cosine similarity, enforces a similarity threshold, calls Bedrock Converse only when grounded chunks exist, applies the output guardrail, writes traces, and emits structured logs
- `/agent/run` reuses the same shared RAG pipeline only for `task: answer_question`
- Phase 9 added observability, audit, and a basic operator dashboard
- Phase 10B added generation token usage observability where Bedrock returns usage fields

This remains a useful mini RAG baseline for learning and regression comparison, but it is not the production-scale retrieval path.

## Why The Current Approach Is Useful For Learning

The current implementation is still valuable because it makes the core control points explicit and inspectable.

Useful properties of the current mini RAG:

- retrieval behavior is easy to read in application code
- metadata filtering and the policy gate are visible in the same runtime path
- blocked and `no_source` behavior are easy to reason about
- traces and logs provide a practical evidence trail
- evaluation can compare retrieval and answer behavior against a known baseline

This is particularly useful when the team wants to understand why a request was blocked, denied, or returned `no_source` without introducing a more opaque retrieval platform too early.

## Why The Current Approach Is Not Production-scale

The current approach is not production-scale for several concrete reasons:

- retrieval depends on DynamoDB scan plus in-Lambda ranking
- latency and cost become harder to predict as the corpus grows
- ranking logic remains tightly coupled to one Lambda runtime path
- retrieval performance and corpus size are constrained by the current application-managed shape
- the design is strong for learning but weak for larger-scale retrieval operations, operational tuning, and long-term retrieval maintenance

The current approach is therefore best treated as a learning baseline and regression reference, not the long-term retrieval target.

## Production RAG Requirements

A more production-oriented retrieval path should satisfy at least these requirements:

- keep the backend policy gate before retrieval
- keep metadata filtering aligned with `projectId`, `customerId`, and `documentType`
- preserve grounded behavior and `no_source` behavior
- preserve or improve evidence quality for sources and citations
- support practical observability and evaluation comparison
- improve scalability and operational predictability compared with full-table scans and in-Lambda ranking
- keep migration risk controlled through side-by-side validation rather than immediate replacement

One rule must remain explicit across all options:

Metadata filtering is not a replacement for backend authorization. The policy gate must remain before retrieval.

## Option A: Bedrock Knowledge Bases

### Summary

Bedrock Knowledge Bases is a strong AWS-native candidate when the goal is to move from a learning-focused custom retrieval path toward a more managed retrieval architecture.

### Fit With This Repository

This option fits well when the team wants:

- a stronger AWS-native managed retrieval path
- less custom retrieval plumbing in application code
- a clearer path for enterprise discussion without immediately designing every retrieval subsystem from scratch

### Strengths

- strong AWS-native fit for teams already centered on Bedrock and SAM-based workloads
- can reduce some of the custom retrieval burden currently carried by the Lambda runtime
- likely easier to explain in a PoC-to-enterprise progression than a fully custom retrieval stack

### Constraints

- retrieval behavior is more managed, which can reduce low-level control compared with a custom ranking path
- the team still has to preserve the current policy gate and metadata-boundary story at the application layer
- migration should validate how source evidence, retrieval transparency, and observability compare with the current mini RAG

### 10C Position

This is a strong first production-oriented candidate for an AWS-native upgrade discussion, but not an automatic final decision.

## Option B: OpenSearch Vector Index / Custom Retrieval

### Summary

OpenSearch vector search or another custom retrieval path is a strong candidate when the team wants deeper control over indexing, retrieval tuning, ranking behavior, and retrieval-side observability.

### Fit With This Repository

This option fits well when the team wants:

- tighter control over retrieval logic and ranking behavior
- more freedom to tune search behavior than a more managed path may offer
- a retrieval architecture that can be designed with explicit application-level control points

### Strengths

- stronger retrieval control and tuning flexibility
- better fit when the team expects custom ranking, filtering, or retrieval orchestration to matter materially
- potentially stronger portability story than a more Bedrock-centered retrieval path

### Constraints

- greater operational complexity than the current mini RAG or a more managed Bedrock-centered path
- more infrastructure and operating-model decisions to make
- more migration surface to validate for security boundary, evidence behavior, and evaluation comparability

### 10C Position

This remains a valid option when deeper retrieval control is more important than an AWS-native managed retrieval path.

## Option C: Keep Mini RAG For Learning/Demo Only

### Summary

The current mini RAG can remain in the repository as a learning baseline, regression reference, and demo implementation.

### Fit With This Repository

This option fits well when the team wants:

- an inspectable learning path for architecture and control-boundary discussions
- a baseline for comparing new retrieval options against the current behavior
- a stable reference implementation that remains easy to explain and test

### Strengths

- lowest immediate change risk
- best transparency for code-level learning and regression comparison
- keeps the current control flow easy to inspect

### Constraints

- not the production-scale retrieval path
- does not address the main scalability and operational limitations already identified in Phase 10A

### 10C Position

Keep it, but do not treat it as the long-term production retrieval architecture.

## Comparison Table

| Criterion | Current mini RAG | Bedrock Knowledge Bases | OpenSearch vector index / custom retrieval |
| --- | --- | --- | --- |
| Implementation effort | Already implemented | Moderate migration effort, likely lower than a fully custom retrieval rebuild | Moderate to high migration effort depending on design depth |
| AWS-native fit | Medium | High | Medium |
| Retrieval control | High in application code | Lower to medium compared with custom retrieval | High |
| Metadata filtering | Already implemented in application code | Must still be validated carefully against the current metadata contract | Can be designed explicitly, but must be implemented carefully |
| Policy gate compatibility | Strong today because it is in the application path | Must remain before retrieval and must not be delegated away implicitly | Must remain before retrieval and can stay explicit in the application path |
| Citation/evidence behavior | Known current baseline | Must be validated against current grounded-source expectations | Must be designed and validated explicitly |
| Evaluation compatibility | Strong baseline already exists | Should be compared side-by-side with current evaluation cases | Should be compared side-by-side with current evaluation cases |
| Observability compatibility | Strong current baseline for traces/logs | Needs validation so operator visibility does not regress | Needs explicit design, but offers high control |
| Token/cost visibility | Current generation visibility exists in the app path | Must be re-validated depending on integration shape | Must be designed explicitly in the integration path |
| Operational complexity | Low to medium today, but poor scaling fit | Medium | High |
| Scalability | Low for production-scale retrieval | Better candidate than the current mini RAG | Better candidate than the current mini RAG |
| Lock-in / portability | Low to medium | Higher AWS dependency | Lower than a Bedrock-centered managed retrieval path |
| Migration risk | None if unchanged | Medium | Medium to high |

## Recommendation By Scenario

### Scenario 1: AWS-native PoC-to-enterprise progression

Proposed direction:

- start with Bedrock Knowledge Bases as the first production-oriented candidate

Why:

- it aligns well with the current AWS-centered stack
- it gives a practical next-step story beyond the mini RAG baseline
- it may reduce custom retrieval plumbing earlier than a full custom retrieval stack

### Scenario 2: Need deeper retrieval control and ranking flexibility

Proposed direction:

- evaluate OpenSearch vector retrieval or a custom retrieval path

Why:

- deeper retrieval behavior and ranking control may matter more than a more managed path
- application teams may want finer control over how retrieval, filtering, and ranking evolve

### Scenario 3: Learning, demos, and regression reference remain important

Proposed direction:

- keep the current mini RAG in the repository as the baseline and comparison reference

Why:

- it preserves the most inspectable learning path
- it provides a stable reference for future migration validation

## Risks And Tradeoffs

The main Phase 10C risks are:

- weakening the policy gate by treating metadata filtering as the security boundary
- losing current `no_source` behavior discipline during migration
- reducing source or citation clarity compared with the current grounded baseline
- making evaluation comparisons harder by replacing the current path too early
- increasing operational complexity without a clear retrieval benefit

The main tradeoff is simple:

- Bedrock Knowledge Bases likely offers a cleaner AWS-native upgrade path
- OpenSearch or custom retrieval likely offers deeper control
- the current mini RAG remains the clearest learning and regression baseline

## Suggested Next Implementation Slice

The safest next slice is:

1. preserve the current mini RAG unchanged as the baseline
2. define the metadata and source-document contract explicitly
3. prototype one experimental retrieval path behind a separate route or feature flag
4. preserve the backend policy gate before retrieval
5. compare evidence quality, latency, token usage, `no_source` rate, and evaluation outcomes before any cutover decision

This keeps migration risk lower than a direct replacement of `/rag/query`.

## Acceptance Criteria

Phase 10C is acceptable when:

- the review explains the current mini RAG baseline accurately
- the review explains why the current path is useful for learning but not for production scale
- the comparison keeps backend authorization separate from metadata filtering
- Bedrock Knowledge Bases and OpenSearch are discussed as options, not as deployed facts
- the recommendation remains cautious and scenario-based rather than overstated
- the next implementation slice is practical and low-risk

## Current Implementation Boundary

Current implementation means the repository still uses:

- document chunks and embeddings stored in DynamoDB
- metadata filtering and the backend policy gate in application code
- in-Lambda ranking over the current chunk set
- Bedrock Converse only when grounded chunks exist
- `no_source` behavior when grounded chunks do not qualify

## Future Roadmap Boundary

Future roadmap means:

- experimental Bedrock Knowledge Bases integration
- experimental OpenSearch or custom retrieval integration
- side-by-side comparison and migration evidence
- eventual cutover or long-term side-by-side operation if justified

These are roadmap items only. They are not implemented by this document.