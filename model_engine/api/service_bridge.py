from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import error, request


@dataclass
class ServiceEngineHTTPError(Exception):
    status_code: int
    payload: dict[str, Any]

    def __str__(self) -> str:
        return f"service engine returned status={self.status_code}"


class ServiceEngineUnavailableError(RuntimeError):
    """Raised when the service engine cannot be reached or returns invalid data."""


class ServiceEngineBridgeClient:
    def __init__(self, *, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get(self, path: str, *, authorization: str | None = None) -> dict[str, Any]:
        return self._request("GET", path, authorization=authorization)

    def post(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        authorization: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(body or {})
        return self._request("POST", path, body=payload, authorization=authorization)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        authorization: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Accept": "application/json",
        }
        data = None
        if authorization:
            headers["Authorization"] = authorization
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        http_request = request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                payload = _read_json_payload(response.read())
        except error.HTTPError as exc:
            payload = _read_json_payload(exc.read(), fallback_status=exc.code)
            raise ServiceEngineHTTPError(exc.code, payload) from exc
        except error.URLError as exc:
            raise ServiceEngineUnavailableError(
                f"failed to reach service engine at {self._base_url}"
            ) from exc

        if not isinstance(payload, dict):
            raise ServiceEngineUnavailableError("service engine returned a non-object JSON payload")
        return payload


def _read_json_payload(raw: bytes, fallback_status: int = 502) -> dict[str, Any]:
    if not raw:
        return _fallback_error_payload(fallback_status, "empty response body")

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _fallback_error_payload(
            fallback_status,
            raw.decode("utf-8", errors="replace"),
        )

    if isinstance(decoded, dict):
        return decoded

    return _fallback_error_payload(fallback_status, "expected JSON object response")


def _fallback_error_payload(status_code: int, detail: str) -> dict[str, Any]:
    return {
        "error": {
            "code": "upstream_invalid_response",
            "message": f"service engine returned status={status_code}",
            "retryable": status_code >= 500,
            "details": detail,
        }
    }
