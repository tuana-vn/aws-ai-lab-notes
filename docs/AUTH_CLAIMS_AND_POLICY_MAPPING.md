# Auth Claims and Policy Mapping

## Purpose

This document explains how the current learning headers map to future verified identity claims.

It is a target design reference for future phases. It does not claim that verified JWT claims, Cognito, or an authorizer are implemented in the current repository.

## Current Header-Based Context

The current backend policy context is built from three caller-provided headers:

- `X-User-Id`
- `X-Allowed-Project-Ids`
- `X-Allowed-Customer-Ids`

Current behavior in the repository:

- `X-User-Id` becomes the current `user_id`
- `X-Allowed-Project-Ids` becomes `allowed_project_ids`
- `X-Allowed-Customer-Ids` becomes `allowed_customer_ids`
- requested `projectId` and `customerId` filters are checked against that allowed scope

This is useful for learning where policy fits in the flow, but these headers are user-controlled and therefore not a real trust boundary.

## Target AccessContext Model

Future phases should normalize verified identity information into a conceptual `AccessContext` object.

Conceptual model:

```text
AccessContext {
  userId
  principalId
  authSource
  issuer
  audience
  scopes
  groups
  allowedProjectIds
  allowedCustomerIds
  tenantId
}
```

Intent of the model:

- `userId`: stable application-facing user identifier
- `principalId`: authorizer or identity principal identifier
- `authSource`: where authentication came from, for example Cognito or custom authorizer
- `issuer`: token issuer
- `audience`: intended API audience
- `scopes`: coarse-grained permissions
- `groups`: role or group membership
- `allowedProjectIds`: project scope authorized for this caller
- `allowedCustomerIds`: customer scope authorized for this caller
- `tenantId`: optional tenant boundary if the future model becomes tenant-aware

Design rule:

- after verified claims are introduced, caller-provided `X-Allowed-*` headers must no longer be used as a trusted scope source

## Claim Mapping Table

| Current Header | Future Claim Candidate | Source | Used For | Notes |
| --- | --- | --- | --- | --- |
| `X-User-Id` | `sub` | verified JWT | stable user identity | Strong default candidate for canonical user identity. |
| `X-User-Id` | `username` or `preferred_username` | verified JWT | human-readable user identity | Useful for display and operator-facing trace output, but usually not the canonical principal key. |
| `X-User-Id` | `email` | verified JWT | operator-facing audit context | Good for trace readability, but email can change and should not be the only principal key. |
| `X-Allowed-Project-Ids` | `custom:project_ids` | verified JWT custom claim or trusted policy lookup | allowed project scope | Direct mapping candidate if project scopes are small enough for claims. |
| `X-Allowed-Customer-Ids` | `custom:customer_ids` | verified JWT custom claim or trusted policy lookup | allowed customer scope | Direct mapping candidate if customer scopes are claim-backed. |
| none today | `cognito:groups` | verified JWT | role/group-based authorization context | Useful for route authorization and possibly for deriving allowed scope indirectly. |
| none today | `scope` | verified JWT | coarse-grained API permission checks | Useful for route-level authorization, not sufficient alone for fine-grained data scope. |
| none today | `tenant_id` if applicable | verified JWT custom claim or trusted policy lookup | tenant isolation boundary | Optional future boundary if the platform adopts tenant-aware authorization. |

## Candidate Permission Scope Names

These are target route-level permission names for future phases.

- `rag:query`
- `documents:write`
- `agent:run`
- `approvals:read`
- `approvals:decide`
- `approvals:execute`
- `incident-reports:read`

Design note:

Not every allowed scope should necessarily live directly inside the token. Future phases may choose a mixed model where identity comes from verified claims and the allowed resource scope comes from a trusted backend policy lookup.

## Policy Evaluation Examples

### 1. Allowed project and customer request

Example context:

- verified `userId=sub-123`
- `allowedProjectIds=[learning]`
- `allowedCustomerIds=[internal]`
- requested filters: `projectId=learning`, `customerId=internal`

Expected result:

- authentication succeeds
- `AccessContext` is built from verified claims
- policy gate allows the requested scope
- metadata filter constrains eligible chunks
- retrieval may proceed

### 2. Denied project request

Example context:

- verified `allowedProjectIds=[learning]`
- requested filters: `projectId=other-project`

Expected result:

- authentication succeeds
- policy gate denies scope before retrieval
- request returns an authorization denial
- no Bedrock-backed answer generation occurs

### 3. Denied customer request

Example context:

- verified `allowedCustomerIds=[internal]`
- requested filters: `customerId=external-customer`

Expected result:

- authentication succeeds
- policy gate denies scope before retrieval
- no retrieval or Bedrock answer generation occurs

### 4. Missing claim

Example context:

- token is valid enough to identify a caller
- required project or customer scope claim is missing

Expected result:

- fail closed by default unless a trusted backend policy lookup supplies the missing scope
- no fallback to caller-provided `X-Allowed-*` headers once verified claims are introduced

### 5. Expired or invalid token

Example context:

- JWT is expired, signature-invalid, issuer-invalid, or audience-invalid

Expected result:

- request is rejected at the authentication boundary
- application policy logic does not run
- retrieval and Bedrock do not run

### 6. `no_source` after allowed auth

Example context:

- authentication succeeds
- policy gate allows requested filters
- metadata filter allows a set of chunks
- similarity threshold yields no grounded evidence

Expected result:

- request is authorized
- retrieval still ends in `no_source`
- this is not an auth failure; it is a grounded-answer failure due to insufficient eligible evidence

## Separation of Concerns

- authorizer validates token
- `AccessContext` resolver normalizes identity and scope
- policy gate compares requested filters against allowed scope
- metadata filter constrains eligible chunks
- retrieval similarity ranks only eligible chunks

Important:

- authorizer validates identity
- backend policy still validates requested `projectId` and `customerId` filters

Why this separation matters:

- authentication proves who the caller is
- authorization defines what scope the caller is allowed to request
- metadata filtering limits what data is even eligible for retrieval
- similarity ranking decides which eligible content is most relevant

These are related controls, but they are not the same control.

## Risks and Mitigations

- claim spoofing -> validate JWT signature plus issuer and audience
- overbroad claims -> least privilege group and scope assignment
- stale access -> token TTL and revocation strategy
- missing claims -> fail closed
- header injection -> ignore caller-provided `X-Allowed-*` headers after verified claims are introduced
- audit gaps -> trace auth decision