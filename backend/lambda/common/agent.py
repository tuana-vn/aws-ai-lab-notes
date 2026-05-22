ALLOWED_TOOLS = ["rag_query", "trace_lookup", "log_search"]
READ_ONLY_AGENT_MODE = "read_only"
ANSWER_QUESTION_TASK = "answer_question"
INSPECT_TRACE_TASK = "inspect_trace"
SEARCH_LOGS_TASK = "search_logs"
INVESTIGATE_RECENT_BLOCKS_TASK = "investigate_recent_blocks"


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

    if task == SEARCH_LOGS_TASK:
        return [
            "Validate request",
            "Check tool allowlist",
            "Run log_search tool",
            "Summarize log result",
            "Return log inspection result",
        ]

    if task == INVESTIGATE_RECENT_BLOCKS_TASK:
        return [
            "Validate request",
            "Run log_search tool with preset blocked",
            "Extract candidate request IDs",
            "Run trace_lookup tool for candidate request IDs",
            "Summarize blocked request reasons",
            "Return investigation result",
        ]

    return ["Validate request"]


def build_tool_call(tool_name: str, status: str) -> dict:
    return {
        "toolName": tool_name,
        "status": status,
        "readOnly": True,
    }