import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


DOCUMENT_PATH = Path("test-data/rag-evaluation/documents/api-gateway-note.json")
QUESTIONS_PATH = Path("test-data/rag-evaluation/questions.json")
REPORTS_DIR = Path("reports")
RAW_RESULTS_PATH = REPORTS_DIR / "rag-eval-results.json"
MARKDOWN_REPORT_PATH = REPORTS_DIR / "rag-eval-report.md"
NO_ANSWER_TEXT = "I do not know based on the available documents"
DEFAULT_REQUEST_HEADERS = {
    "X-User-Id": "user-learning",
    "X-Allowed-Project-Ids": "learning",
    "X-Allowed-Customer-Ids": "internal",
}


def _require_api_base_url():
    api_base_url = os.environ.get("API_BASE_URL", "").strip()
    if not api_base_url:
        raise SystemExit("API_BASE_URL environment variable is required.")

    return api_base_url.rstrip("/")


def _load_json(path):
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _post_json(url, payload, headers=None):
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if isinstance(headers, dict):
        request_headers.update(headers)

    http_request = request.Request(
        url,
        data=body,
        headers=request_headers,
        method="POST",
    )

    try:
        with request.urlopen(http_request) as http_response:
            response_text = http_response.read().decode("utf-8")
            response_body = json.loads(response_text) if response_text else {}
            return {
                "httpStatusCode": http_response.getcode(),
                "body": response_body,
            }
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8")
        try:
            response_body = json.loads(response_text) if response_text else {}
        except json.JSONDecodeError:
            response_body = {"rawBody": response_text}

        return {
            "httpStatusCode": exc.code,
            "body": response_body,
        }


def _normalize_text(value):
    if not isinstance(value, str):
        return ""

    return value.casefold()


def _extract_source_document_ids(response_body):
    source_document_ids = []
    for source in response_body.get("sources", []):
        if isinstance(source, dict):
            document_id = source.get("documentId")
            if isinstance(document_id, str):
                source_document_ids.append(document_id)

    return source_document_ids


def _format_source_summaries(response_body):
    source_summaries = []
    for source in response_body.get("sources", []):
        if not isinstance(source, dict):
            continue

        document_id = source.get("documentId", "-")
        similarity = source.get("similarity")
        if similarity is None:
            source_summaries.append(str(document_id))
            continue

        source_summaries.append(f"{document_id} ({similarity})")

    return source_summaries


def _format_filters_for_markdown(response_body):
    filters = response_body.get("filters", {})
    if not isinstance(filters, dict) or not filters:
        return "-"

    return ", ".join(f"{key}={value}" for key, value in filters.items())


def _answer_contains_any_keyword(answer, keywords):
    normalized_answer = _normalize_text(answer)
    for keyword in keywords:
        if _normalize_text(keyword) in normalized_answer:
            return True

    return False


def _evaluate_case(case_definition, response):
    response_body = response.get("body", {})
    response_status = response_body.get("status")
    answer = response_body.get("answer", "")
    source_document_ids = _extract_source_document_ids(response_body)
    notes = []
    case_type = case_definition.get("type")
    expected_http_status_code = case_definition.get("expectedHttpStatusCode", 200)

    if response.get("httpStatusCode") != expected_http_status_code:
        notes.append(
            f"expected HTTP {expected_http_status_code} but got {response.get('httpStatusCode')}"
        )

    if case_type in {"in_source", "semantic"}:
        expected_status = case_definition.get("expectedStatus")
        expected_document_id = case_definition.get("expectedDocumentId")
        expected_keywords = case_definition.get("expectedAnswerKeywords", [])

        status_matches = response_status == expected_status
        has_expected_source = expected_document_id in source_document_ids
        has_expected_keyword = _answer_contains_any_keyword(answer, expected_keywords)

        if not status_matches:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if not has_expected_source:
            notes.append(f"expected source '{expected_document_id}' not found")
        if not has_expected_keyword:
            notes.append("answer did not contain any expected keyword")

        passed = status_matches and has_expected_source and has_expected_keyword
    elif case_type in {"out_of_source", "metadata_boundary"}:
        normalized_answer = _normalize_text(answer)
        no_answer_detected = NO_ANSWER_TEXT.casefold() in normalized_answer
        expected_status = case_definition.get("expectedStatus", "no_source")
        no_source_status = response_status == expected_status
        no_sources_returned = not source_document_ids
        expected_sources_empty = case_definition.get("expectedSourcesEmpty", True)

        if not no_answer_detected:
            notes.append("response did not refuse the out-of-source question")
        if not no_source_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if expected_sources_empty and not no_sources_returned:
            notes.append("expected sources to be empty for no-source case")

        passed = no_answer_detected and no_source_status and (
            no_sources_returned if expected_sources_empty else True
        )
    elif case_type == "policy_denied":
        expected_error_message = case_definition.get("expectedErrorMessage", "")
        actual_message = response_body.get("message", "")
        has_expected_error = _normalize_text(expected_error_message) in _normalize_text(actual_message)
        answer_generated = "answer" in response_body and bool(response_body.get("answer"))

        if not has_expected_error:
            notes.append("response did not contain the expected access denied message")
        if answer_generated:
            notes.append("expected no answer to be generated for denied request")

        passed = has_expected_error and not answer_generated
    elif case_type == "guardrail_blocked":
        expected_status = case_definition.get("expectedStatus", "blocked")
        expected_guardrail_action = case_definition.get("expectedGuardrailAction", "block")
        expected_keywords = case_definition.get("expectedAnswerKeywords", [])
        guardrail = response_body.get("guardrail", {})
        guardrail_action = guardrail.get("action")
        has_expected_keyword = _answer_contains_any_keyword(answer, expected_keywords)
        sources_empty = not source_document_ids

        if response_status != expected_status:
            notes.append(f"expected status '{expected_status}' but got '{response_status}'")
        if guardrail_action != expected_guardrail_action:
            notes.append(
                f"expected guardrail action '{expected_guardrail_action}' but got '{guardrail_action}'"
            )
        if not has_expected_keyword:
            notes.append("blocked answer did not contain any expected keyword")
        if not sources_empty:
            notes.append("expected sources to be empty for blocked request")

        passed = (
            response_status == expected_status
            and guardrail_action == expected_guardrail_action
            and has_expected_keyword
            and sources_empty
        )
    else:
        notes.append(f"unsupported case type '{case_type}'")
        passed = False

    if response.get("httpStatusCode", 0) >= 400 and case_type != "policy_denied":
        notes.append(f"HTTP {response['httpStatusCode']}")
        passed = False

    if response.get("httpStatusCode") != expected_http_status_code:
        passed = False

    return {
        "caseId": case_definition.get("caseId"),
        "type": case_type,
        "question": case_definition.get("question"),
        "expected": case_definition,
        "response": response,
        "pass": passed,
        "notes": "; ".join(notes) if notes else "OK",
    }


def _format_sources_for_markdown(response_body):
    source_summaries = _format_source_summaries(response_body)
    if not source_summaries:
        return "-"

    return ", ".join(source_summaries)


def _answer_snippet(answer, limit=240):
    compact_answer = " ".join(str(answer).split())
    if len(compact_answer) <= limit:
        return compact_answer

    return compact_answer[: limit - 3] + "..."


def _write_json_report(results_payload):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_RESULTS_PATH.open("w", encoding="utf-8") as file_handle:
        json.dump(results_payload, file_handle, indent=2)


def _write_markdown_report(api_base_url, started_at, results):
    total_cases = len(results)
    passed_cases = sum(1 for result in results if result["pass"])
    failed_cases = total_cases - passed_cases

    lines = [
        "# RAG Evaluation Report",
        "",
        f"- API base URL: {api_base_url}",
        f"- timestamp: {started_at}",
        f"- total cases: {total_cases}",
        f"- passed cases: {passed_cases}",
        f"- failed cases: {failed_cases}",
        "",
        "| Case ID | Type | HTTP | Status | Question | Filters | Sources | Min Similarity | Pass/Fail | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for result in results:
        response_body = result["response"].get("body", {})
        http_status_code = result["response"].get("httpStatusCode", "-")
        status = response_body.get("status", "-")
        filters = _format_filters_for_markdown(response_body)
        sources = _format_sources_for_markdown(response_body)
        min_similarity_score = response_body.get("minSimilarityScore", "-")
        pass_fail = "PASS" if result["pass"] else "FAIL"
        question = str(result["question"]).replace("|", "\\|")
        notes = str(result["notes"]).replace("|", "\\|")
        lines.append(
            f"| {result['caseId']} | {result['type']} | {http_status_code} | {status} | {question} | {filters} | {sources} | {min_similarity_score} | {pass_fail} | {notes} |"
        )

    lines.extend(["", "## Answer Snippets", ""])

    for result in results:
        response_body = result["response"].get("body", {})
        answer = response_body.get("answer", "")
        filters = _format_filters_for_markdown(response_body)
        sources = _format_sources_for_markdown(response_body)
        min_similarity_score = response_body.get("minSimilarityScore", "-")
        lines.extend(
            [
                f"### {result['caseId']}",
                "",
                f"HTTP Status: {result['response'].get('httpStatusCode', '-')}",
                "",
                f"Question: {result['question']}",
                "",
                f"Status: {response_body.get('status', '-')}",
                "",
            f"Filters: {filters}",
            "",
                f"Sources: {sources}",
                "",
                f"Min Similarity Score: {min_similarity_score}",
                "",
                f"Answer: {_answer_snippet(answer) or '-'}",
                "",
            ]
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with MARKDOWN_REPORT_PATH.open("w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines))


def main():
    api_base_url = _require_api_base_url()
    started_at = datetime.now(timezone.utc).isoformat()

    script_directory = Path(__file__).resolve().parent
    repository_root = script_directory.parent
    document = _load_json(repository_root / DOCUMENT_PATH)
    questions = _load_json(repository_root / QUESTIONS_PATH)

    document_response = _post_json(f"{api_base_url}/documents", document)
    if document_response["httpStatusCode"] >= 400:
        raise SystemExit(
            "Document indexing failed: "
            + json.dumps(document_response, indent=2)
        )

    results = []
    for case_definition in questions:
        request_payload = {"question": case_definition.get("question", "")}
        if isinstance(case_definition.get("filters"), dict):
            request_payload["filters"] = case_definition["filters"]

        request_headers = dict(DEFAULT_REQUEST_HEADERS)
        if isinstance(case_definition.get("headers"), dict):
            request_headers.update(case_definition["headers"])

        response = _post_json(
            f"{api_base_url}/rag/query",
            request_payload,
            headers=request_headers,
        )
        results.append(_evaluate_case(case_definition, response))

    results_payload = {
        "apiBaseUrl": api_base_url,
        "timestamp": started_at,
        "documentResponse": document_response,
        "results": results,
    }
    _write_json_report(results_payload)
    _write_markdown_report(api_base_url, started_at, results)

    total_cases = len(results)
    passed_cases = sum(1 for result in results if result["pass"])
    print(f"RAG evaluation complete: {passed_cases}/{total_cases} cases passed.")
    print(f"JSON results: {RAW_RESULTS_PATH}")
    print(f"Markdown report: {MARKDOWN_REPORT_PATH}")


if __name__ == "__main__":
    main()