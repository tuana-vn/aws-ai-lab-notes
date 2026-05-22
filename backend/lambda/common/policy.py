from __future__ import annotations


DEFAULT_ALLOWED_SCOPE = ["default"]


class AccessDeniedError(Exception):
    pass


def _get_header_value(headers: dict[str, object], header_name: str) -> str | None:
    target_name = header_name.casefold()
    for key, value in headers.items():
        if isinstance(key, str) and key.casefold() == target_name and isinstance(value, str):
            return value

    return None


def _parse_allowed_values(raw_value: str | None) -> list[str]:
    if not isinstance(raw_value, str):
        return list(DEFAULT_ALLOWED_SCOPE)

    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not values:
        return list(DEFAULT_ALLOWED_SCOPE)

    return values


def resolve_access_context(event) -> dict:
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}

    user_id = _get_header_value(headers, "X-User-Id") or "anonymous"
    allowed_project_ids = _parse_allowed_values(
        _get_header_value(headers, "X-Allowed-Project-Ids")
    )
    allowed_customer_ids = _parse_allowed_values(
        _get_header_value(headers, "X-Allowed-Customer-Ids")
    )

    return {
        "user_id": user_id,
        "allowed_project_ids": allowed_project_ids,
        "allowed_customer_ids": allowed_customer_ids,
    }


def assert_filters_allowed(filters: dict, access_context: dict) -> None:
    project_id = filters.get("projectId")
    customer_id = filters.get("customerId")

    if project_id is not None and project_id not in access_context["allowed_project_ids"]:
        raise AccessDeniedError("Access denied for requested retrieval scope.")

    if customer_id is not None and customer_id not in access_context["allowed_customer_ids"]:
        raise AccessDeniedError("Access denied for requested retrieval scope.")