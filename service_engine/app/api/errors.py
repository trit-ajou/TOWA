from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.api.schemas.common import ErrorBody, ErrorResponse
from app.modules.auth.service import AuthServiceError, InvalidSessionError, SessionExpiredError
from app.modules.billing.credits import (
    CreditServiceError,
    InsufficientCreditsError,
    InvalidCreditHoldStateError,
    MissingCreditAccountError,
)
from app.modules.billing.service import (
    IdempotencyPayloadMismatchError,
    UsageJobConflictError,
    UsageJobNotFoundError,
)
from app.modules.projects.service import (
    PageConflictError,
    PageNotFoundError,
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectStorageError,
    SnapshotValidationError,
)


@dataclass(slots=True)
class APIError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


def error_body(
    *,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> ErrorBody:
    return ErrorBody(
        code=code,
        message=message,
        retryable=retryable,
        details=details,
    )


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=error_body(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        ),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def openapi_error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    descriptions = {
        status.HTTP_401_UNAUTHORIZED: "Authentication failed.",
        status.HTTP_404_NOT_FOUND: "Requested resource was not found.",
        status.HTTP_409_CONFLICT: "Request conflicted with the current domain state.",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "Request validation failed.",
    }
    return {
        status_code: {
            "model": ErrorResponse,
            "description": descriptions.get(status_code, "Error response."),
        }
        for status_code in status_codes
    }


def _validation_details(exc: RequestValidationError) -> dict[str, Any]:
    fields = []
    for item in exc.errors():
        location = [str(part) for part in item.get("loc", ()) if part not in {"body", "query", "path"}]
        fields.append(
            {
                "field": ".".join(location) or "request",
                "message": item.get("msg", "Invalid value."),
                "type": item.get("type", "validation_error"),
            },
        )
    return {"fields": fields}


def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    )


def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Request validation failed.",
        details=_validation_details(exc),
    )


def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return error_response(
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=str(detail),
    )


def _default_error_code(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    }.get(status_code, "http_error")


def raise_auth_http_error(exc: Exception) -> None:
    if isinstance(exc, SessionExpiredError):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="session_expired",
            message=str(exc),
        ) from exc
    if isinstance(exc, InvalidSessionError):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="session_invalid",
            message=str(exc),
        ) from exc
    if isinstance(exc, ValueError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=str(exc),
        ) from exc
    if isinstance(exc, AuthServiceError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="auth_conflict",
            message=str(exc),
        ) from exc
    raise exc


def raise_usage_http_error(exc: Exception) -> None:
    if isinstance(exc, UsageJobNotFoundError):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="usage_job_not_found",
            message=str(exc),
        ) from exc
    if isinstance(exc, InsufficientCreditsError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="insufficient_credits",
            message=str(exc),
        ) from exc
    if isinstance(exc, MissingCreditAccountError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="missing_credit_account",
            message=str(exc),
        ) from exc
    if isinstance(exc, IdempotencyPayloadMismatchError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="usage_conflict",
            message=str(exc),
            details={"reason": "idempotency_payload_mismatch"},
        ) from exc
    if isinstance(exc, (InvalidCreditHoldStateError, UsageJobConflictError, CreditServiceError)):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="usage_conflict",
            message=str(exc),
        ) from exc
    if isinstance(exc, (StaleDataError, IntegrityError)):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="concurrent_update_conflict",
            message="Concurrent update conflict. Retry the request.",
            retryable=True,
        ) from exc
    if isinstance(exc, ValueError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=str(exc),
        ) from exc
    raise_auth_http_error(exc)


def raise_project_http_error(exc: Exception) -> None:
    if isinstance(exc, ProjectNotFoundError):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="project_not_found",
            message=str(exc),
        ) from exc
    if isinstance(exc, PageNotFoundError):
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="page_not_found",
            message=str(exc),
        ) from exc
    if isinstance(exc, SnapshotValidationError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=str(exc),
        ) from exc
    if isinstance(exc, ProjectConflictError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="project_conflict",
            message=str(exc),
            details={"reason": exc.reason} if exc.reason else None,
        ) from exc
    if isinstance(exc, PageConflictError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="page_conflict",
            message=str(exc),
            details={"reason": exc.reason} if exc.reason else None,
        ) from exc
    if isinstance(exc, (StaleDataError, IntegrityError)):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="concurrent_update_conflict",
            message="Concurrent update conflict. Retry the request.",
            retryable=True,
        ) from exc
    if isinstance(exc, ValueError):
        raise APIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=str(exc),
        ) from exc
    if isinstance(exc, ProjectStorageError):
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="project_conflict",
            message=str(exc),
        ) from exc
    raise_auth_http_error(exc)
