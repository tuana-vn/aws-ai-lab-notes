ALLOWED_TOOLS = ["rag_query"]
READ_ONLY_AGENT_MODE = "read_only"
ANSWER_QUESTION_TASK = "answer_question"
READ_ONLY_PLAN = [
    "Validate request",
    "Check input guardrail",
    "Check retrieval policy",
    "Run rag_query tool",
    "Validate output",
    "Return grounded answer",
]


def build_tool_call(tool_name: str, status: str) -> dict:
    return {
        "toolName": tool_name,
        "status": status,
        "readOnly": True,
    }