ALLOWED_TOOLS = ["rag_query", "trace_lookup"]
READ_ONLY_AGENT_MODE = "read_only"
ANSWER_QUESTION_TASK = "answer_question"
INSPECT_TRACE_TASK = "inspect_trace"


def build_plan(task: str) -> list[str]:
    if task == ANSWER_QUESTION_TASK:
        return [
            "Validate request",
            "Check input guardrail",
            "Check retrieval policy",
            "Run rag_query tool",
            "Validate output",
            "Return grounded answer",
        ]

    if task == INSPECT_TRACE_TASK:
        return [
            "Validate request",
            "Check tool allowlist",
            "Run trace_lookup tool",
            "Summarize trace result",
            "Return trace inspection result",
        ]

    return ["Validate request"]


def build_tool_call(tool_name: str, status: str) -> dict:
    return {
        "toolName": tool_name,
        "status": status,
        "readOnly": True,
    }