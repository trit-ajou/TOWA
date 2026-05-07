from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class ServiceEngineError(RuntimeError):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: Any = None

    def __str__(self) -> str:
        return self.message


class ServiceEngineAuthError(ServiceEngineError):
    """Raised when the session key is missing, invalid, or expired."""


class ServiceEngineCreditError(ServiceEngineError):
    """Raised when the caller cannot reserve credits for the request."""


class ServiceEngineConflictError(ServiceEngineError):
    """Raised when the usage job is in an incompatible state."""


class ServiceEngineNotFoundError(ServiceEngineError):
    """Raised when the requested usage job does not exist."""


class ServiceEngineTransportError(ServiceEngineError):
    """Raised when the service engine cannot be reached safely."""


def service_engine_error_from_payload(
    *,
    status_code: int,
    payload: Mapping[str, Any],
) -> ServiceEngineError:
    error_payload = payload.get("error")
    if not isinstance(error_payload, Mapping):
        return ServiceEngineTransportError(
            status_code=status_code,
            code="upstream_invalid_response",
            message=f"service engine returned status={status_code}",
            retryable=status_code >= 500,
            details=dict(payload),
        )

    code = str(error_payload.get("code", "service_engine_error"))
    message = str(error_payload.get("message", f"service engine returned status={status_code}"))
    retryable = bool(error_payload.get("retryable", status_code >= 500))
    details = error_payload.get("details")

    error_type: type[ServiceEngineError]
    if code in {"session_key_required", "session_invalid", "session_expired"}:
        error_type = ServiceEngineAuthError
    elif code in {"insufficient_credits", "missing_credit_account"}:
        error_type = ServiceEngineCreditError
    elif code == "usage_job_not_found":
        error_type = ServiceEngineNotFoundError
    elif code in {"usage_conflict", "concurrent_update_conflict"}:
        error_type = ServiceEngineConflictError
    else:
        error_type = ServiceEngineError

    return error_type(
        status_code=status_code,
        code=code,
        message=message,
        retryable=retryable,
        details=details,
    )
