import argparse
import json
from pathlib import Path

from view_trace import DEFAULT_TABLE_NAME, fetch_trace_record, format_trace_summary


DEFAULT_RESULTS_FILE = Path("reports/rag-eval-results.json")


def _load_results(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _find_case(results_payload: dict, case_id: str) -> dict | None:
    for result in results_payload.get("results", []):
        if result.get("caseId") == case_id:
            return result

    return None


def _display(value):
    if value is None or value == "" or value == [] or value == {}:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return str(value)


def main():
    parser = argparse.ArgumentParser(description="View DynamoDB trace for one evaluation case.")
    parser.add_argument("--case-id", required=True, help="Evaluation caseId to inspect.")
    parser.add_argument(
        "--results-file",
        default=str(DEFAULT_RESULTS_FILE),
        help=f"Path to rag evaluation results JSON. Default: {DEFAULT_RESULTS_FILE}",
    )
    parser.add_argument(
        "--table-name",
        default=DEFAULT_TABLE_NAME,
        help=f"DynamoDB trace table name. Default: {DEFAULT_TABLE_NAME}",
    )
    args = parser.parse_args()

    results_path = Path(args.results_file)
    results_payload = _load_results(results_path)
    case_result = _find_case(results_payload, args.case_id)

    if case_result is None:
        raise SystemExit(f"Case {args.case_id} was not found in {results_path}.")

    response_body = case_result.get("response", {}).get("body", {})
    request_id = response_body.get("requestId")

    print("# Evaluation Case")
    print()
    print(f"- caseId: {_display(case_result.get('caseId'))}")
    print(f"- type: {_display(case_result.get('type'))}")
    print(f"- pass: {_display(case_result.get('pass'))}")
    print(f"- notes: {_display(case_result.get('notes'))}")
    print(f"- question: {_display(case_result.get('question'))}")
    print()

    if not request_id:
        print(
            f"No requestId found for case {args.case_id}. This may be expected for policy-denied cases."
        )
        return

    trace_record = fetch_trace_record(request_id, args.table_name)
    if trace_record is None:
        print(f"No trace record found for request_id {request_id} in table {args.table_name}.")
        return

    print(format_trace_summary(trace_record))


if __name__ == "__main__":
    main()