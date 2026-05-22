# RAG Evaluation Report

- API base URL: https://dj4qxxa454.execute-api.ap-southeast-1.amazonaws.com/v1
- timestamp: 2026-05-22T07:27:58.742435+00:00
- total cases: 6
- passed cases: 5
- failed cases: 1

| Case ID | Type | HTTP | Status | Question | Filters | Sources | Min Similarity | Pass/Fail | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q001 | in_source | 200 | completed | What does API Gateway do? | projectId=learning, customerId=internal | api-gateway-note (0.7829) | 0.25 | PASS | OK |
| Q002 | semantic | 200 | completed | How can API Gateway limit excessive traffic? | projectId=learning, customerId=internal | api-gateway-note (0.6338) | 0.25 | PASS | OK |
| Q003 | semantic | 200 | completed | How does API Gateway protect backend services? | projectId=learning, customerId=internal | api-gateway-note (0.7247) | 0.25 | PASS | OK |
| Q004 | out_of_source | 200 | no_source | What is the capital city of France? | projectId=learning, customerId=internal | - | 0.25 | PASS | OK |
| Q005 | metadata_boundary | 403 | - | What does API Gateway do? | - | - | - | FAIL | expected HTTP 200 but got 403; response did not refuse the out-of-source question; expected status 'no_source' but got 'None'; HTTP 403 |
| Q006 | policy_denied | 403 | - | What does API Gateway do? | - | - | - | PASS | OK |

## Answer Snippets

### Q001

HTTP Status: 200

Question: What does API Gateway do?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.7829)

Min Similarity Score: 0.25

Answer: Amazon API Gateway helps developers create, publish, maintain, monitor, and secure APIs. It can act as the front door for applications to access backend services such as Lambda functions or container-based services. API Gateway can handl...

### Q002

HTTP Status: 200

Question: How can API Gateway limit excessive traffic?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.6338)

Min Similarity Score: 0.25

Answer: API Gateway can limit excessive traffic through throttling. Throttling allows you to control the number of requests per second (RPS) for your APIs. [Source: documentId=api-gateway-note, chunkId=chunk-0001]

### Q003

HTTP Status: 200

Question: How does API Gateway protect backend services?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.7247)

Min Similarity Score: 0.25

Answer: API Gateway protects backend services through features such as routing, throttling, authorization, and request validation. It can also integrate with AWS services for enhanced security. [Source: documentId=api-gateway-note, chunkId=chunk...

### Q004

HTTP Status: 200

Question: What is the capital city of France?

Status: no_source

Filters: projectId=learning, customerId=internal

Sources: -

Min Similarity Score: 0.25

Answer: I do not know based on the available documents.

### Q005

HTTP Status: 403

Question: What does API Gateway do?

Status: -

Filters: -

Sources: -

Min Similarity Score: -

Answer: -

### Q006

HTTP Status: 403

Question: What does API Gateway do?

Status: -

Filters: -

Sources: -

Min Similarity Score: -

Answer: -
