from __future__ import annotations


class GuardrailViolation(Exception):
    pass


PROMPT_INJECTION_RULES = {
    "ignore_previous_instructions": "ignore previous instructions",
    "ignore_all_previous_instructions": "ignore all previous instructions",
    "forget_previous_instructions": "forget previous instructions",
    "forget_all_instructions": "forget all instructions",
    "reveal_system_prompt": "reveal system prompt",
    "show_system_prompt": "show system prompt",
    "show_hidden_prompt": "show hidden prompt",
    "bypass_policy": "bypass policy",
    "bypass_guardrail": "bypass guardrail",
    "override_instructions": "override instructions",
}

UNSAFE_DATA_ACCESS_RULES = {
    "show_me_all_customer_secrets": "show me all customer secrets",
    "show_all_customer_secrets": "show all customer secrets",
    "reveal_customer_secrets": "reveal customer secrets",
    "show_confidential_data": "show confidential data",
    "dump_all_documents": "dump all documents",
    "dump_all_data": "dump all data",
    "show_all_documents": "show all documents",
}


def _blocked_result(reason: str, matched_rule: str) -> dict:
    return {
        "allowed": False,
        "action": "block",
        "reason": reason,
        "matchedRule": matched_rule,
    }


def evaluate_input_guardrail(text: str) -> dict:
    normalized_text = text.casefold()

    for rule_name, pattern in PROMPT_INJECTION_RULES.items():
        if pattern in normalized_text:
            return _blocked_result("prompt_injection", rule_name)

    for rule_name, pattern in UNSAFE_DATA_ACCESS_RULES.items():
        if pattern in normalized_text:
            return _blocked_result("unsafe_data_access", rule_name)

    return {
        "allowed": True,
        "action": "allow",
        "reason": "no_violation",
        "matchedRule": None,
    }