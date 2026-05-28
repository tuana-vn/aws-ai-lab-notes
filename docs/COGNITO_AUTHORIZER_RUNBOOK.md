# Cognito Authorizer Runbook

## Purpose

This runbook explains how to deploy the first Cognito-protected route, create a test user, set the required custom attributes, obtain an ID token, and call `POST /rag/query` with an `Authorization` header.

This runbook is for the first protected-route rollout only:

- `POST /rag/query`, `POST /documents`, `POST /agent/run`, and the approval routes are protected in this phase
- `GET /health` remains public
- `/echo`, `/chat`, and `/incident-reports/*` remain unchanged

This runbook does not claim production-ready authentication.

## Prerequisites

- AWS CLI configured for the target account and region
- AWS SAM CLI installed locally
- `jq` installed for token and output extraction
- stack deployed from `infra/cloudformation/template.yaml`

## 1. Deploy the Stack

Validate and build the template:

```bash
sam validate --template-file infra/cloudformation/template.yaml
sam build --template-file infra/cloudformation/template.yaml
```

Deploy the stack:

```bash
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name aws-ai-platform-poc-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides EnvironmentName=dev
```

## 2. Read Deployment Outputs

Capture the API base URL and Cognito outputs:

```bash
STACK_NAME="aws-ai-platform-poc-dev"

API_BASE_URL="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text)"

USER_POOL_ID="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
  --output text)"

USER_POOL_CLIENT_ID="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolClientId'].OutputValue" \
  --output text)"

echo "$API_BASE_URL"
echo "$USER_POOL_ID"
echo "$USER_POOL_CLIENT_ID"
```

## 3. Create or Confirm a Test User

The first test user should carry the minimum required custom claims:

- `custom:project_ids = learning`
- `custom:customer_ids = internal`

Create a test user if one does not already exist:

```bash
TEST_USERNAME="tuan"
TEST_EMAIL="tuan@example.com"

aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_USERNAME" \
  --user-attributes \
    Name=email,Value="$TEST_EMAIL" \
    Name=email_verified,Value=true \
    Name=preferred_username,Value="$TEST_USERNAME" \
  --message-action SUPPRESS
```

Set a permanent password:

```bash
TEST_PASSWORD='Phase8HPassword1'

aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_USERNAME" \
  --password "$TEST_PASSWORD" \
  --permanent
```

Set the required custom attributes:

```bash
aws cognito-idp admin-update-user-attributes \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_USERNAME" \
  --user-attributes \
    Name=custom:project_ids,Value=learning \
    Name=custom:customer_ids,Value=internal
```

Confirm the user attributes:

```bash
aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$TEST_USERNAME"
```

## 4. Get an ID Token

Obtain tokens using the user pool client:

```bash
AUTH_RESULT="$(aws cognito-idp initiate-auth \
  --client-id "$USER_POOL_CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="$TEST_USERNAME",PASSWORD="$TEST_PASSWORD")"
```

Extract the ID token and export it for local commands:

```bash
export AUTH_TOKEN="$(echo "$AUTH_RESULT" | jq -r '.AuthenticationResult.IdToken')"
echo "$AUTH_TOKEN" | cut -c1-32
```

The first protected-route rollout is expected to use the ID token for practical claim mapping of:

- `sub`
- `preferred_username` or `username`
- `custom:project_ids`
- `custom:customer_ids`

## 5. Test Unauthenticated /documents

This request should now fail at API Gateway before Lambda runs:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -d @test-data/requests/demo-document-request.json
```

Expected result:

- HTTP `401` or `403`
- rejection occurs at the API boundary

## 6. Test Authenticated Allowed /documents

Send the ID token in the `Authorization` header:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d @test-data/requests/demo-document-request.json
```

Expected result:

- HTTP `200`
- `status=indexed`

## 7. Test Unauthenticated /rag/query

This request should now fail at API Gateway before Lambda runs:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does API Gateway protect backend services?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }'
```

Expected result:

- HTTP `401` or `403`
- rejection occurs at the API boundary

## 8. Test Authenticated Allowed /rag/query

Send the ID token in the `Authorization` header:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "question": "How does API Gateway protect backend services?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }'
```

Expected result:

- HTTP `200`
- `status=completed` or another valid RAG response state such as `blocked` or `no_source`, depending on the request content
- request is authenticated at API Gateway and still filtered by the backend policy gate

## 9. Test Authenticated Mismatched Project /rag/query

Use the same authenticated user but ask for a project outside the user claim scope:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "question": "How does API Gateway protect backend services?",
    "filters": {
      "projectId": "other-project",
      "customerId": "internal"
    }
  }'
```

Expected result:

- HTTP `403`
- denial comes from the backend policy gate, not from missing authentication

## 10. Test Unauthenticated /agent/run

This request should now fail at API Gateway before Lambda runs:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "answer_question",
    "question": "What does API Gateway do?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }'
```

Expected result:

- HTTP `401` or `403`
- rejection occurs at the API boundary

## 11. Test Authenticated /agent/run answer_question

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "task": "answer_question",
    "question": "What does API Gateway do?",
    "filters": {
      "projectId": "learning",
      "customerId": "internal"
    }
  }'
```

Expected result:

- HTTP `200`
- `status=completed`

## 12. Test Authenticated /agent/run investigate_recent_blocks

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "task": "investigate_recent_blocks",
    "minutes": 120
  }'
```

Expected result:

- HTTP `200`
- `status=completed`

## 13. Test Authenticated /agent/run propose_incident_report

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "task": "propose_incident_report",
    "minutes": 120
  }'
```

Expected result:

- HTTP `200`
- `status=approval_required`

## 14. Test Protected Approval Routes

First create an approval with an authenticated `propose_incident_report` call and capture the returned `APPROVAL_ID`.

No-token approval lookup should fail at API Gateway:

```bash
curl -i -sS \
  -X GET "$API_BASE_URL/approvals/$APPROVAL_ID"
```

Expected result:

- HTTP `401` or `403`

No-token approval decision should fail at API Gateway:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "decidedBy": "tuan",
    "comment": "Approval route auth test"
  }'
```

Expected result:

- HTTP `401` or `403`

No-token approval execute should fail at API Gateway:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "executedBy": "tuan"
  }'
```

Expected result:

- HTTP `401` or `403`

Valid-token approval workflow should still work:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/agent/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "task": "propose_incident_report",
    "minutes": 120
  }'
```

Expected result:

- HTTP `200`
- `status=approval_required`

Approval GET with token:

```bash
curl -i -sS \
  -X GET "$API_BASE_URL/approvals/$APPROVAL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected result:

- HTTP `200`
- approval record shows `pending_approval`

Approval decision with token:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/decision" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "decision": "approved",
    "decidedBy": "tuan",
    "comment": "Approval route auth test"
  }'
```

Expected result:

- HTTP `200`
- approval result shows `approved` or `approved_not_executed`

Approval execute with token:

```bash
curl -i -sS \
  -X POST "$API_BASE_URL/approvals/$APPROVAL_ID/execute" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "executedBy": "tuan"
  }'
```

Expected result:

- HTTP `200`
- execution result shows `executed` and includes `reportId`

## 15. Run the Evaluation with a Token

The evaluation script supports token-based calls through `AUTH_TOKEN` or `AUTHORIZATION_HEADER`.

Run the eval with the exported ID token:

```bash
API_BASE_URL="$API_BASE_URL" AUTH_TOKEN="$AUTH_TOKEN" python3 scripts/run_rag_eval.py
```

Alternative explicit header form:

```bash
API_BASE_URL="$API_BASE_URL" AUTHORIZATION_HEADER="Bearer $AUTH_TOKEN" python3 scripts/run_rag_eval.py
```

Expected result:

- `RAG evaluation complete: 16/16 cases passed`

If token mode is active after `/rag/query` protection, the current expected summary is:

- `RAG evaluation complete: 15/15 cases passed`
- `Skipped cases: 1`

The skipped case is `Q006`, which is intentionally excluded in token mode because trusted-header spoofing is not the active auth source.

## 16. Notes on Scope and Compatibility

- `POST /rag/query`, `POST /documents`, `POST /agent/run`, `GET /approvals/{approvalId}`, `POST /approvals/{approvalId}/decision`, and `POST /approvals/{approvalId}/execute` are protected in this phase.
- The backend policy gate still validates `projectId` and `customerId` against the claims-backed `AccessContext`.
- Trusted headers remain available for local compatibility and for routes that are still intentionally unprotected.
- The mock authorizer-claims resolver path remains useful for local testing even after Cognito is added.
- Incident report lookup remains intentionally unchanged in this phase.
- Approval business logic still validates approval state and action type after authentication.

## 17. Troubleshooting

- If unauthenticated `/documents` still succeeds, verify the route is actually attached to the Cognito authorizer in the deployed template.
- If authenticated `/documents` fails, confirm the `Authorization` header is present and the token is still valid.
- If unauthenticated `/rag/query` still succeeds, verify the route is actually attached to the Cognito authorizer in the deployed template.
- If authenticated `/rag/query` returns `403`, confirm the token includes `custom:project_ids=learning` and `custom:customer_ids=internal`.
- If unauthenticated `/agent/run` still succeeds, verify the route is actually attached to the Cognito authorizer in the deployed template.
- If authenticated `/agent/run` fails, confirm the token is valid and the request body matches a supported task shape.
- If unauthenticated approval routes still succeed, verify the approval events are attached to the Cognito authorizer in the deployed template.
- If approval GET, decision, or execute fails with a valid token, confirm the approval was created first and that the workflow state is valid for the requested action.
- If custom attributes do not appear in the token, inspect the actual token claims and confirm the first token choice still matches the deployed Cognito configuration.
- If the evaluation script fails after route protection, confirm `AUTH_TOKEN` or `AUTHORIZATION_HEADER` is exported in the same shell used to run the script.