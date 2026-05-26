from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class AuthenticatedUserPayload:
    id: str
    email: str
    nickname: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class CurrentUserPayload:
    user: AuthenticatedUserPayload
    credit_balance: int
    reserved_units: int


@dataclass(frozen=True)
class UsageJobCreatePayload:
    job_id: str
    status: str
    reserved_units: int
    hold_expires_at: datetime


@dataclass(frozen=True)
class UsageJobPayload:
    id: str
    operation_kind: str
    request_ref: str
    estimated_units: int
    status: str
    reserved_units: int
    hold_status: str
    hold_expires_at: datetime
    error_code: str | None = None
    error_detail: str | None = None
    requested_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class ServiceEngineErrorEnvelope:
    code: str
    message: str
    retryable: bool
    details: Any = None


def parse_current_user_payload(payload: Mapping[str, Any]) -> CurrentUserPayload:
    user_payload = _require_mapping(payload, "user")
    return CurrentUserPayload(
        user=AuthenticatedUserPayload(
            id=str(user_payload["id"]),
            email=str(user_payload["email"]),
            nickname=str(user_payload["nickname"]),
            status=str(user_payload["status"]),
            created_at=_parse_datetime(user_payload["created_at"]),
        ),
        credit_balance=int(payload["credit_balance"]),
        reserved_units=int(payload["reserved_units"]),
    )


def parse_usage_job_create_payload(payload: Mapping[str, Any]) -> UsageJobCreatePayload:
    return UsageJobCreatePayload(
        job_id=str(payload["job_id"]),
        status=str(payload["status"]),
        reserved_units=int(payload["reserved_units"]),
        hold_expires_at=_parse_datetime(payload["hold_expires_at"]),
    )


def parse_usage_job_payload(payload: Mapping[str, Any]) -> UsageJobPayload:
    return UsageJobPayload(
        id=str(payload["id"]),
        operation_kind=str(payload["operation_kind"]),
        request_ref=str(payload["request_ref"]),
        estimated_units=int(payload["estimated_units"]),
        status=str(payload["status"]),
        reserved_units=int(payload["reserved_units"]),
        hold_status=str(payload["hold_status"]),
        hold_expires_at=_parse_datetime(payload["hold_expires_at"]),
        error_code=_optional_string(payload.get("error_code")),
        error_detail=_optional_string(payload.get("error_detail")),
        requested_at=_optional_datetime(payload.get("requested_at")),
        finished_at=_optional_datetime(payload.get("finished_at")),
    )


def parse_error_envelope(payload: Mapping[str, Any]) -> ServiceEngineErrorEnvelope:
    error_payload = _require_mapping(payload, "error")
    return ServiceEngineErrorEnvelope(
        code=str(error_payload["code"]),
        message=str(error_payload["message"]),
        retryable=bool(error_payload["retryable"]),
        details=error_payload.get("details"),
    )


def _require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"expected mapping payload for key={key}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value)


def _parse_datetime(value: Any) -> datetime:
    normalized = str(value)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)
