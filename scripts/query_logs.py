import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone


PRESET_QUERIES = {
    "summary": """
fields @timestamp, @message
| filter ispresent(status)
| stats count(*) as count by status
| sort count desc
""".strip(),
    "policy-denied": """
fields @timestamp, request_id, requestId, path, user_id, userId, status, eventType, @message
| filter status = "denied"
    or eventType = "policy_denied"
    or @message like /denied|policy/
| sort @timestamp desc
| limit 20
""".strip(),
    "blocked": """
fields @timestamp, request_id, requestId, status, eventType, guardrail_action, guardrailAction, guardrail_reason, guardrailReason, guardrail_matched_rule, guardrailMatchedRule
| filter status = "blocked"
    or eventType = "input_guardrail_blocked"
    or guardrail_action = "block"
    or guardrailAction = "block"
| sort @timestamp desc
| limit 20
""".strip(),
    "no-source": """
fields @timestamp, request_id, requestId, status, eventType, question, source_count, sourceCount, eligible_chunk_count, eligibleChunkCount
| filter status = "no_source" or eventType = "rag_no_source"
| sort @timestamp desc
| limit 20
""".strip(),
    "errors": """
fields @timestamp, @message
| filter @message like /ERROR|error|failed/
| sort @timestamp desc
| limit 20
""".strip(),
    "latency": """
fields @timestamp, path, status, latency_ms, latencyMs
| filter ispresent(latency_ms) or ispresent(latencyMs)
| stats avg(latency_ms) as avg_latency_ms, avg(latencyMs) as avg_latencyMs, max(latency_ms) as max_latency_ms, max(latencyMs) as max_latencyMs, count(*) as count by path, status
| sort count desc
""".strip(),
    "guardrails": """
fields @timestamp, guardrail_action, guardrailAction, guardrail_reason, guardrailReason, guardrail_matched_rule, guardrailMatchedRule, eventType
| filter ispresent(guardrail_action) or ispresent(guardrailAction) or eventType = "input_guardrail_blocked"
| stats count(*) as count by guardrail_action, guardrailAction, guardrail_reason, guardrailReason, guardrail_matched_rule, guardrailMatchedRule
| sort count desc
""".strip(),
    "approval": """
fields @timestamp, approval_id, approvalId, decision, execution_status, executionStatus, user_id, userId, status, eventType, @message
| filter eventType = "approval_decided"
    or ispresent(approval_id)
    or ispresent(approvalId)
    or @message like /approval|decision|approved|rejected/
| sort @timestamp desc
| limit 20
""".strip(),
    "executions": """
fields @timestamp, approval_id, approvalId, report_id, reportId, execution_status, executionStatus, action_type, actionType, user_id, userId, status, eventType, @message
| filter eventType = "approval_execute_requested"
    or eventType = "approval_execute_denied"
    or eventType = "approval_executed"
    or ispresent(report_id)
    or ispresent(reportId)
    or @message like /execute|executed|reportId|report_id|incident report/
| sort @timestamp desc
| limit 20
""".strip(),
    "agent-tools": """
fields @timestamp, request_id, requestId, task, tool_calls, toolCalls, status, eventType, @message
| filter ispresent(tool_calls)
    or ispresent(toolCalls)
    or eventType = "agent_tool_called"
    or eventType = "agent_tool_failed"
    or @message like /tool_calls|toolCalls|trace_lookup|log_search|rag_query/
| sort @timestamp desc
| limit 20
""".strip(),
    "security-audit": """
fields @timestamp, request_id, requestId, path, status, eventType, guardrail_action, guardrailAction, guardrail_reason, guardrailReason, user_id, userId, approval_id, approvalId, report_id, reportId, @message
| filter status = "blocked"
    or status = "denied"
    or status = "failed"
    or status = "no_source"
    or eventType = "policy_denied"
    or eventType = "input_guardrail_blocked"
    or eventType = "rag_no_source"
    or eventType = "approval_decided"
    or eventType = "approval_execute_denied"
    or eventType = "approval_executed"
    or eventType = "incident_report_created"
    or eventType = "error"
    or ispresent(guardrail_action)
    or ispresent(guardrailAction)
    or @message like /guardrail|denied|approval|execute|incident report/
| sort @timestamp desc
| limit 50
""".strip(),
    "raw": """
fields @timestamp, @message
| sort @timestamp desc
| limit 20
""".strip(),
}


def _aws_command(base_args, region=None):
    command = ["aws", *base_args]
    if region:
        command.extend(["--region", region])
    return command


def _run_aws_cli(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown AWS CLI error."
        raise RuntimeError(f"AWS CLI command failed: {stderr}")
    return json.loads(result.stdout or "{}")


def _start_query(log_group, query_string, start_minutes_ago, region=None):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=start_minutes_ago)
    command = _aws_command(
        [
            "logs",
            "start-query",
            "--log-group-name",
            log_group,
            "--start-time",
            str(int(start_time.timestamp())),
            "--end-time",
            str(int(end_time.timestamp())),
            "--query-string",
            query_string,
        ],
        region=region,
    )
    payload = _run_aws_cli(command)
    query_id = payload.get("queryId")
    if not query_id:
        raise RuntimeError("AWS CLI start-query did not return a queryId.")
    return query_id


def _get_query_results(query_id, region=None):
    command = _aws_command(["logs", "get-query-results", "--query-id", query_id], region=region)
    return _run_aws_cli(command)


def _wait_for_query_completion(query_id, region=None, poll_interval_seconds=1, timeout_seconds=30):
    deadline = time.time() + timeout_seconds
    while True:
        payload = _get_query_results(query_id, region=region)
        status = payload.get("status")
        if status in {"Complete", "Failed", "Cancelled", "Timeout"}:
            return payload
        if time.time() >= deadline:
            raise RuntimeError(f"Logs Insights query {query_id} did not complete within {timeout_seconds} seconds.")
        time.sleep(poll_interval_seconds)


def _results_to_dicts(results):
    rows = []
    for row in results:
        row_dict = {}
        for field in row:
            field_name = field.get("field")
            if field_name == "@ptr":
                continue
            row_dict[field_name] = field.get("value", "")
        rows.append(row_dict)
    return rows


def _print_table(rows):
    if not rows:
        print("No results.")
        return

    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    widths = {}
    for column in columns:
        widths[column] = max(len(column), *(len(str(row.get(column, "-"))) for row in rows))

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in rows:
        print(" | ".join(str(row.get(column, "-")).ljust(widths[column]) for column in columns))


def main():
    parser = argparse.ArgumentParser(description="Run CloudWatch Logs Insights preset queries.")
    parser.add_argument("--log-group", required=True, help="CloudWatch Logs log group name.")
    parser.add_argument(
        "--preset",
        required=True,
        choices=sorted(PRESET_QUERIES.keys()),
        help="Named Logs Insights query preset.",
    )
    parser.add_argument(
        "--start-minutes-ago",
        type=int,
        default=60,
        help="How far back to query in minutes. Default: 60",
    )
    parser.add_argument("--region", help="AWS region override, for example ap-southeast-1.")
    args = parser.parse_args()

    query_string = PRESET_QUERIES[args.preset]
    query_id = _start_query(
        args.log_group,
        query_string,
        args.start_minutes_ago,
        region=args.region,
    )
    payload = _wait_for_query_completion(query_id, region=args.region)
    status = payload.get("status")

    print(f"Query status: {status}")
    print(f"Query id: {query_id}")
    print(f"Preset: {args.preset}")
    print()

    if status != "Complete":
        print(json.dumps(payload, indent=2))
        return

    rows = _results_to_dicts(payload.get("results", []))
    _print_table(rows)


if __name__ == "__main__":
    main()