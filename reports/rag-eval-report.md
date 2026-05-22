# RAG Evaluation Report

- API base URL: https://dj4qxxa454.execute-api.ap-southeast-1.amazonaws.com/v1
- timestamp: 2026-05-22T07:09:42.259661+00:00
- total cases: 5
- passed cases: 5
- failed cases: 0

| Case ID | Type | Question | Status | Filters | Sources | Min Similarity | Pass/Fail | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q001 | in_source | What does API Gateway do? | completed | projectId=learning, customerId=internal | api-gateway-note (0.7829) | 0.25 | PASS | OK |
| Q002 | semantic | How can API Gateway limit excessive traffic? | completed | projectId=learning, customerId=internal | api-gateway-note (0.6338) | 0.25 | PASS | OK |
| Q003 | semantic | How does API Gateway protect backend services? | completed | projectId=learning, customerId=internal | api-gateway-note (0.7247) | 0.25 | PASS | OK |
| Q004 | out_of_source | What is the capital city of France? | no_source | projectId=learning, customerId=internal | - | 0.25 | PASS | OK |
| Q005 | metadata_boundary | What does API Gateway do? | no_source | projectId=other-project | - | 0.25 | PASS | OK |

## Answer Snippets

### Q001

Question: What does API Gateway do?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.7829)

Min Similarity Score: 0.25

Answer: API Gateway helps developers create, publish, maintain, monitor, and secure APIs. It can handle routing, throttling, authorization, request validation, and integration with AWS services. (Source: documentId=api-gateway-note, chunkId=chun...

### Q002

Question: How can API Gateway limit excessive traffic?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.6338)

Min Similarity Score: 0.25

Answer: API Gateway can limit excessive traffic through throttling. [Source: documentId=api-gateway-note, chunkId=chunk-0001]

### Q003

Question: How does API Gateway protect backend services?

Status: completed

Filters: projectId=learning, customerId=internal

Sources: api-gateway-note (0.7247)

Min Similarity Score: 0.25

Answer: API Gateway protects backend services through features such as routing, throttling, authorization, and request validation (documentId=api-gateway-note, chunkId=chunk-0001).

### Q004

Question: What is the capital city of France?

Status: no_source

Filters: projectId=learning, customerId=internal

Sources: -

Min Similarity Score: 0.25

Answer: I do not know based on the available documents.

### Q005

Question: What does API Gateway do?

Status: no_source

Filters: projectId=other-project

Sources: -

Min Similarity Score: 0.25

Answer: I do not know based on the available documents.
