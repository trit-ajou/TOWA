from __future__ import annotations

from typing import Any, Mapping

from ..api.service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)
from .errors import ServiceEngineTransportError, service_engine_error_from_payload
from .models import (
    CurrentUserPayload,
    UsageJobCreatePayload,
    UsageJobPayload,
    parse_current_user_payload,
    parse_usage_job_create_payload,
    parse_usage_job_payload,
)


class ServiceEngineClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        bridge_client: ServiceEngineBridgeClient | None = None,
    ) -> None:
        self._bridge_client = bridge_client or ServiceEngineBridgeClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    def get_auth_me(self, session_key: str) -> CurrentUserPayload:
        payload = self._get("/auth/me", session_key=session_key)
        return self._parse(payload, parse_current_user_payload)

    def create_usage_job(
        self,
        session_key: str,
        *,
        idempotency_key: str,
        operation_kind: str,
        request_ref: str,
        estimated_units: int,
    ) -> UsageJobCreatePayload:
        payload = self._post(
            "/usage/jobs",
            session_key=session_key,
            body={
                "idempotency_key": idempotency_key,
                "operation_kind": operation_kind,
                "request_ref": request_ref,
                "estimated_units": estimated_units,
            },
        )
        return self._parse(payload, parse_usage_job_create_payload)

    def capture_usage_job(self, session_key: str, *, job_id: str) -> UsageJobPayload:
        payload = self._post(
            f"/usage/jobs/{job_id}/capture",
            session_key=session_key,
            body={},
        )
        return self._parse(payload, parse_usage_job_payload)

    def release_usage_job(
        self,
        session_key: str,
        *,
        job_id: str,
        error_code: str | None = None,
        reason: str | None = None,
    ) -> UsageJobPayload:
        payload = self._post(
            f"/usage/jobs/{job_id}/release",
            session_key=session_key,
            body={
                "error_code": error_code,
                "reason": reason,
            },
        )
        return self._parse(payload, parse_usage_job_payload)

    def get_usage_job(self, session_key: str, *, job_id: str) -> UsageJobPayload:
        payload = self._get(f"/usage/jobs/{job_id}", session_key=session_key)
        return self._parse(payload, parse_usage_job_payload)

    def _get(self, path: str, *, session_key: str) -> dict[str, Any]:
        try:
            return self._bridge_client.get(path, authorization=_bearer_token(session_key))
        except ServiceEngineHTTPError as exc:
            raise service_engine_error_from_payload(
                status_code=exc.status_code,
                payload=exc.payload,
            ) from exc
        except ServiceEngineUnavailableError as exc:
            raise ServiceEngineTransportError(
                status_code=502,
                code="service_engine_unreachable",
                message=str(exc),
                retryable=True,
            ) from exc

    def _post(
        self,
        path: str,
        *,
        session_key: str,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            return self._bridge_client.post(
                path,
                body=body,
                authorization=_bearer_token(session_key),
            )
        except ServiceEngineHTTPError as exc:
            raise service_engine_error_from_payload(
                status_code=exc.status_code,
                payload=exc.payload,
            ) from exc
        except ServiceEngineUnavailableError as exc:
            raise ServiceEngineTransportError(
                status_code=502,
                code="service_engine_unreachable",
                message=str(exc),
                retryable=True,
            ) from exc

    def _parse(
        self,
        payload: Mapping[str, Any],
        parser: Any,
    ) -> Any:
        try:
            return parser(payload)
        except Exception as exc:  # noqa: BLE001
            raise ServiceEngineTransportError(
                status_code=502,
                code="upstream_invalid_response",
                message="service engine returned an unexpected payload shape",
                retryable=False,
                details=dict(payload),
            ) from exc


def _bearer_token(session_key: str) -> str:
    normalized = session_key.strip()
    if not normalized:
        raise ValueError("session_key is required")
    return f"Bearer {normalized}"
