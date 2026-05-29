# WAF And Edge Protection Review

## Purpose

This document reviews whether AWS WAF and related edge protections would be useful for the current `aws-ai-platform-poc` baseline.

It does not claim that WAF is already deployed. It defines what WAF could reasonably do for this platform and where its limits are.

## Current Edge Posture

The current internet-facing posture is:

- API Gateway is the primary public edge
- `GET /health` is public by design
- all non-health routes are Cognito protected
- the backend still performs request validation, application authorization, guardrail checks, and approval checks where applicable
- no WAF layer is currently documented or deployed
- no route-specific edge filter policy is documented yet

This means the platform already has useful backend security controls, but only limited edge-specific filtering.

## Why WAF May Be Useful

WAF may be useful because it can reduce obvious unwanted traffic before it becomes an application or identity-layer concern.

Practical value for this PoC:

- filter common malformed or abusive request patterns at the edge
- add a rate-based backstop for traffic spikes that should never reach normal application volume
- narrow the exposure of public internet traffic before requests reach API Gateway and Lambda

## What WAF Would Protect

WAF could help protect against:

- common internet noise and generic web attack patterns
- basic request abuse on public-facing paths
- request floods that exceed reasonable expected rates
- oversized or malformed request patterns when rules are configured for that purpose

## What WAF Would Not Protect

WAF would not replace:

- Cognito authentication
- backend authorization and route permission checks
- `AccessContext` and policy enforcement in `/rag/query`
- input or output guardrails
- approval decision and approval execute controls
- application-level `no_source` or grounding behavior

WAF should be treated as an outer defensive layer, not the main trust boundary.

## Candidate Protections

### AWS Managed Common Rule Set

This is a practical first candidate because it gives broad edge coverage without starting from a fully custom ruleset.

Usefulness:

- good first-pass coverage for common internet request patterns
- lower design effort than building a large custom rule set immediately

### Known Bad Inputs

The team may later choose a narrow set of known-bad input patterns at the edge, but this should be limited and evidence-driven.

Why narrow:

- application logic already owns semantic validation
- overly aggressive WAF patterns can block legitimate requests and make debugging harder

### IP Reputation If Justified

IP reputation controls may be useful if the platform is exposed more broadly and sees clear hostile traffic patterns.

Why not first:

- the current PoC has no evidence yet that IP reputation rules are the highest-value first step
- IP-based blocking can create operational noise if added too early

### Rate-based Rules

Rate-based rules are one of the strongest first WAF candidates for this platform.

Why:

- they address a realistic internet-facing risk without needing deep request semantics
- they can protect public exposure more safely than complex content-matching rules introduced too early

### Request-size Limits

Request-size controls are reasonable to review for:

- `/chat`
- `/rag/query`
- `/agent/run`

Oversized payload limits can reduce waste and limit obviously abnormal request patterns.

### Path-specific Protections

The edge posture should not treat every path the same.

Examples of where path-specific thinking matters:

- `GET /health` is public by design and likely needs the simplest edge treatment
- `/chat`, `/rag/query`, and `/agent/run` are higher-value targets for abuse or cost amplification
- approval and execution routes have stronger backend permission controls but can still benefit from rate awareness

## API Gateway Throttling Vs WAF

API Gateway throttling and WAF solve different problems.

API Gateway throttling is the right place for:

- route-level request-budget control
- platform usage shaping
- protecting backend capacity against normal or semi-normal request surges

WAF is the right place for:

- generic internet request filtering
- rate-based protection against obviously abusive traffic
- outer-edge filtering before application logic runs

The platform will likely need both concepts eventually, but they should not be confused.

## Risks Of Enabling WAF Too Early

The main risks of enabling WAF too early are:

- false positives on legitimate requests
- poor visibility into why normal traffic is being blocked
- edge rules that duplicate or conflict with backend behavior
- premature complexity before traffic patterns are understood

This is especially relevant for an AI-facing API where request content may look unusual compared with standard web forms.

## Recommended First WAF Slice

The first WAF slice should stay narrow:

1. start with AWS managed common protections
2. add one rate-based rule for clearly abusive spikes
3. review request-size posture for the Bedrock-facing routes
4. avoid complex content-matching rules until real traffic patterns justify them

That gives useful edge protection without pretending WAF can solve application-layer security.

## Evidence To Collect Before Implementation

Before implementing WAF, collect:

- current request volume and burst assumptions by route
- logs showing whether abuse is more likely on `GET /health`, `/chat`, `/rag/query`, or `/agent/run`
- examples of oversized or malformed requests if they exist
- operator review workflow for handling false positives
- expected API Gateway throttling posture so WAF and throttling are designed together

## Out Of Scope

This review does not:

- deploy WAF
- define final rule thresholds
- replace Cognito or backend authorization
- redesign guardrails or approval workflow
- claim production edge protection already exists

## Current Implementation Boundary

Current implementation means the platform relies on API Gateway, Cognito, and backend controls, without WAF.

## Future Roadmap Boundary

Future roadmap means a staged WAF rollout after baseline traffic and route-risk evidence are reviewed.