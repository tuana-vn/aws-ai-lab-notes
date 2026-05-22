import argparse
import json
import subprocess
from decimal import Decimal
from typing import Any


DEFAULT_TABLE_NAME = "ai-platform-request-trace-dev"


def dynamodb_json_to_python(value):
    if not isinstance(value, dict) or len(value) != 1:
        return value

    dynamodb_type, dynamodb_value = next(iter(value.items()))

    if dynamodb_type == "S":
        return dynamodb_value
    if dynamodb_type == "N":
        return Decimal(dynamodb_value)
    if dynamodb_type == "BOOL":
        return bool(dynamodb_value)
    if dynamodb_type == "NULL":
        return None
    if dynamodb_type == "M":
        return {key: dynamodb_json_to_python(item) for key, item in dynamodb_value.items()}
    if dynamodb_type == "L":
        return [dynamodb_json_to_python(item) for item in dynamodb_value]

    return dynamodb_value


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return str(value)


def _display(value):
    if value is None or value == "" or value == [] or value == {}:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=_json_default)
    return str(value)


def fetch_trace_record(request_id: str, table_name: str = DEFAULT_TABLE_NAME) -> dict[str, Any] | None:
    command = [
        "aws",
        "dynamodb",
        "get-item",
        "--table-name",
        table_name,
        "--key",
        json.dumps({"request_id": {"S": request_id}}),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        stderr = result.stderr.strip() or "Unknown AWS CLI error."
        raise RuntimeError(f"AWS CLI get-item failed: {stderr}")

    payload = json.loads(result.stdout or "{}")
    item = payload.get("Item")
    if not item:
        return None

    return {key: dynamodb_json_to_python(value) for key, value in item.items()}


def format_trace_summary(trace_record: dict[str, Any]) -> str:
    lines = [
        "# Trace Summary",
        "",
        f"- request_id: {_display(trace_record.get('request_id'))}",
        f"- timestamp: {_display(trace_record.get('timestamp'))}",
        f"- path: {_display(trace_record.get('path'))}",
        f"- user_id: {_display(trace_record.get('user_id'))}",
        f"- status: {_display(trace_record.get('status'))}",
        f"- latency_ms: {_display(trace_record.get('latency_ms'))}",
        "",
        "# Request",
        "",
        f"- question: {_display(trace_record.get('question'))}",
        f"- message: {_display(trace_record.get('message'))}",
        f"- filters: {_display(trace_record.get('filters'))}",
        "",
        "# Guardrails",
        "",
        f"- guardrail_action: {_display(trace_record.get('guardrail_action'))}",
        f"- guardrail_reason: {_display(trace_record.get('guardrail_reason'))}",
        f"- guardrail_matched_rule: {_display(trace_record.get('guardrail_matched_rule'))}",
        f"- output_guardrail_action: {_display(trace_record.get('output_guardrail_action'))}",
        f"- output_guardrail_reason: {_display(trace_record.get('output_guardrail_reason'))}",
        f"- output_guardrail_warnings: {_display(trace_record.get('output_guardrail_warnings'))}",
        "",
        "# Retrieval",
        "",
        f"- retrieval_mode: {_display(trace_record.get('retrieval_mode'))}",
        f"- min_similarity_score: {_display(trace_record.get('min_similarity_score'))}",
        f"- eligible_chunk_count: {_display(trace_record.get('eligible_chunk_count'))}",
        f"- source_count: {_display(trace_record.get('source_count'))}",
        f"- sources: {_display(trace_record.get('sources'))}",
        "",
        "# Answer Preview",
        "",
        f"- answer_preview: {_display(trace_record.get('answer_preview'))}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="View one trace record from DynamoDB by request_id.")
    parser.add_argument("--request-id", required=True, help="Trace request_id to fetch.")
    parser.add_argument(
        "--table-name",
        default=DEFAULT_TABLE_NAME,
        help=f"DynamoDB trace table name. Default: {DEFAULT_TABLE_NAME}",
    )
    args = parser.parse_args()

    trace_record = fetch_trace_record(args.request_id, args.table_name)
    if trace_record is None:
        print(f"No trace record found for request_id {args.request_id} in table {args.table_name}.")
        return

    print(format_trace_summary(trace_record))


if __name__ == "__main__":
    main()