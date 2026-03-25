from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_usage_http_error
from app.api.schemas.usage import (
    UsageJobCaptureRequest,
    UsageJobCreateRequest,
    UsageJobCreateResponse,
    UsageJobReleaseRequest,
    UsageJobResponse,
)
from app.db import get_db_session
from app.modules.billing import service as billing_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post(
    "/jobs",
    response_model=UsageJobCreateResponse,
    responses=openapi_error_responses(401, 409, 422),
)
def create_usage_job(
    payload: UsageJobCreateRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> UsageJobCreateResponse:
    try:
        result = billing_service.create_usage_job(
            session,
            session_token=session_token,
            idempotency_key=payload.idempotency_key,
            operation_kind=payload.operation_kind,
            request_ref=payload.request_ref,
            estimated_units=payload.estimated_units,
        )
    except Exception as exc:  # noqa: BLE001
        raise_usage_http_error(exc)
    return UsageJobCreateResponse.model_validate(result)


@router.post(
    "/jobs/{job_id}/capture",
    response_model=UsageJobResponse,
    responses=openapi_error_responses(401, 404, 409, 422),
)
def capture_usage_job(
    job_id: UUID,
    _payload: UsageJobCaptureRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> UsageJobResponse:
    try:
        result = billing_service.capture_usage_job(
            session,
            session_token=session_token,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_usage_http_error(exc)
    return UsageJobResponse.model_validate(result)


@router.post(
    "/jobs/{job_id}/release",
    response_model=UsageJobResponse,
    responses=openapi_error_responses(401, 404, 409, 422),
)
def release_usage_job(
    job_id: UUID,
    payload: UsageJobReleaseRequest,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> UsageJobResponse:
    try:
        result = billing_service.release_usage_job(
            session,
            session_token=session_token,
            job_id=job_id,
            error_code=payload.error_code,
            reason=payload.reason,
        )
    except Exception as exc:  # noqa: BLE001
        raise_usage_http_error(exc)
    return UsageJobResponse.model_validate(result)


@router.get(
    "/jobs/{job_id}",
    response_model=UsageJobResponse,
    responses=openapi_error_responses(401, 404, 409),
)
def get_usage_job(
    job_id: UUID,
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> UsageJobResponse:
    try:
        result = billing_service.get_usage_job(
            session,
            session_token=session_token,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise_usage_http_error(exc)
    return UsageJobResponse.model_validate(result)

