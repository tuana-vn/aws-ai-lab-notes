def build_incident_report_proposal(
    minutes: int,
    log_summary: dict,
    inspected_traces: list[dict],
    investigation_answer: str,
) -> dict:
    matched_events = int(log_summary.get("matchedEvents", 0) or 0)
    severity = "medium" if matched_events >= 10 else "low"
    inspected_trace_count = len(inspected_traces)

    return {
        "actionType": "create_incident_report",
        "requiresApproval": True,
        "title": "Recent blocked AI requests detected",
        "summary": (
            f"Blocked-request investigation for the last {minutes} minutes found {matched_events} matching log event(s) "
            f"and inspected {inspected_trace_count} trace record(s). {investigation_answer}"
        ),
        "severity": severity,
        "recommendedNextSteps": [
            "Review blocked request patterns.",
            "Review prompt injection and unsafe data access attempts.",
            "Tune guardrail rules if repeated false positives are found.",
            "Consider adding CloudWatch alarms for blocked request spikes.",
        ],
        "executionStatus": "not_executed",
    }