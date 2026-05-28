from __future__ import annotations

from dataclasses import dataclass, field


class AccessDeniedError(Exception):
    pass


@dataclass(slots=True)
class AccessContext:
    user_id: str
    allowed_project_ids: list[str]
    allowed_customer_ids: list[str]
    auth_source: str = "trusted_headers"
    principal_id: str = ""
    scopes: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.principal_id:
            self.principal_id = self.user_id

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


def _get_header_value(headers: dict[str, object], header_name: str) -> str | None:
    target_name = header_name.casefold()
    for key, value in headers.items():
        if isinstance(key, str) and key.casefold() == target_name and isinstance(value, str):
            return value

    return None


def _parse_allowed_values(raw_value: str | None) -> list[str]:
    if not isinstance(raw_value, str):
        return []

    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values


def _parse_space_separated_values(raw_value: str | None) -> list[str]:
    if not isinstance(raw_value, str):
        return []

    values = [item.strip() for item in raw_value.split() if item.strip()]
    return values


def _parse_group_values(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        return [item.strip() for item in raw_value if isinstance(item, str) and item.strip()]

    if isinstance(raw_value, str):
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    return []


def _get_authorizer_claims(event: dict[str, object]) -> dict[str, object] | None:
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        return None

    authorizer = request_context.get("authorizer")
    if not isinstance(authorizer, dict):
        return None

    claims = authorizer.get("claims")
    if not isinstance(claims, dict):
        return None

    return claims


def _resolve_authorizer_claims_context(claims: dict[str, object]) -> AccessContext:
    preferred_username = claims.get("preferred_username")
    username = claims.get("username")
    subject = claims.get("sub")

    user_id = "anonymous"
    for candidate in (preferred_username, username, subject):
        if isinstance(candidate, str) and candidate.strip():
            user_id = candidate.strip()
            break

    principal_id = subject.strip() if isinstance(subject, str) and subject.strip() else user_id

    return AccessContext(
        user_id=user_id,
        principal_id=principal_id,
        allowed_project_ids=_parse_allowed_values(claims.get("custom:project_ids")),
        allowed_customer_ids=_parse_allowed_values(claims.get("custom:customer_ids")),
        scopes=_parse_space_separated_values(claims.get("scope")),
        groups=_parse_group_values(claims.get("cognito:groups")),
        auth_source="mock_authorizer_claims",
    )


def _resolve_trusted_header_context(event: dict[str, object]) -> AccessContext:
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

    return AccessContext(
        user_id=user_id,
        allowed_project_ids=allowed_project_ids,
        allowed_customer_ids=allowed_customer_ids,
        auth_source="trusted_headers",
        principal_id=user_id,
    )


def resolve_access_context(event) -> AccessContext:
    claims = _get_authorizer_claims(event)
    if claims is not None:
        return _resolve_authorizer_claims_context(claims)

    return _resolve_trusted_header_context(event)


def _get_scope_values(access_context, field_name: str) -> list[str]:
    if isinstance(access_context, AccessContext):
        return getattr(access_context, field_name)

    return access_context[field_name]


def assert_filters_allowed(filters: dict, access_context) -> None:
    project_id = filters.get("projectId")
    customer_id = filters.get("customerId")
    allowed_project_ids = _get_scope_values(access_context, "allowed_project_ids")
    allowed_customer_ids = _get_scope_values(access_context, "allowed_customer_ids")

    if project_id is not None and project_id not in allowed_project_ids:
        raise AccessDeniedError("Access denied for requested retrieval scope.")

    if customer_id is not None and customer_id not in allowed_customer_ids:
        raise AccessDeniedError("Access denied for requested retrieval scope.")