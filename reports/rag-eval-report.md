# RAG Evaluation Report

- API base URL: https://dj4qxxa454.execute-api.ap-southeast-1.amazonaws.com/v1
- timestamp: 2026-05-22T06:54:19.492683+00:00
- total cases: 4
- passed cases: 4
- failed cases: 0

| Case ID | Type | Question | Status | Sources | Min Similarity | Pass/Fail | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q001 | in_source | What does API Gateway do? | completed | api-gateway-note (0.7829) | 0.25 | PASS | OK |
| Q002 | semantic | How can API Gateway limit excessive traffic? | completed | api-gateway-note (0.6338) | 0.25 | PASS | OK |
| Q003 | semantic | How does API Gateway protect backend services? | completed | api-gateway-note (0.7247) | 0.25 | PASS | OK |
| Q004 | out_of_source | What is the capital city of France? | no_source | - | 0.25 | PASS | OK |

## Answer Snippets

### Q001

Question: What does API Gateway do?

Status: completed

Sources: api-gateway-note (0.7829)

Min Similarity Score: 0.25

Answer: Amazon API Gateway helps developers create, publish, maintain, monitor, and secure APIs. It can act as the front door for applications to access backend services such as Lambda functions or container-based services. API Gateway can handl...

### Q002

Question: How can API Gateway limit excessive traffic?

Status: completed

Sources: api-gateway-note (0.6338)

Min Similarity Score: 0.25

Answer: API Gateway can limit excessive traffic through throttling. This feature allows you to control the rate at which clients can make API requests. [Source: documentId=api-gateway-note, chunkId=chunk-0001]

### Q003

Question: How does API Gateway protect backend services?

Status: completed

Sources: api-gateway-note (0.7247)

Min Similarity Score: 0.25

Answer: API Gateway protects backend services through features such as routing, throttling, authorization, and request validation. It can also integrate with AWS services for additional security measures. Sources: - documentId=api-gateway-note, ...

### Q004

Question: What is the capital city of France?

Status: no_source

Sources: -

Min Similarity Score: 0.25

Answer: I do not know based on the available documents.
