from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import utcnow
from app.core.settings import get_settings
from app.db.enums import CreditHoldStatus, UsageJobStatus, UsageOperationKind
from app.modules.auth import service as auth_service
from app.modules.billing.credits import capture_credit_hold, release_credit_hold, reserve_credit_for_job
from app.modules.billing.models import CreditHold, UsageJob


class UsageServiceError(RuntimeError):
    pass


class UsageJobNotFoundError(UsageServiceError):
    pass


class UsageJobConflictError(UsageServiceError):
    pass


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _hold_expires_at():
    return utcnow() + timedelta(minutes=get_settings().billing_hold_ttl_minutes)


def _load_usage_job(session: Session, *, user_id: UUID, job_id: UUID) -> UsageJob:
    job = session.scalar(
        select(UsageJob)
        .options(selectinload(UsageJob.credit_hold))
        .where(
            UsageJob.id == job_id,
            UsageJob.user_id == user_id,
        ),
    )
    if job is None:
        raise UsageJobNotFoundError(f"Usage job {job_id} was not found.")
    return job


def _present_create(job: UsageJob) -> dict[str, object]:
    hold = job.credit_hold
    if hold is None:
        raise UsageJobConflictError(f"Usage job {job.id} is missing its credit hold.")
    return {
        "job_id": job.id,
        "status": job.status,
        "reserved_units": hold.estimated_units,
        "hold_expires_at": hold.expires_at,
    }


def _present_job(job: UsageJob) -> dict[str, object]:
    hold = job.credit_hold
    if hold is None:
        raise UsageJobConflictError(f"Usage job {job.id} is missing its credit hold.")
    return {
        "id": job.id,
        "operation_kind": job.operation_kind,
        "request_ref": job.request_ref,
        "estimated_units": job.estimated_units,
        "status": job.status,
        "reserved_units": hold.estimated_units,
        "hold_status": hold.status,
        "hold_expires_at": hold.expires_at,
        "error_code": job.error_code,
        "error_detail": job.error_detail,
        "requested_at": job.requested_at,
        "finished_at": job.finished_at,
    }


def expire_stale_holds(session: Session) -> int:
    now = utcnow()
    stale_holds = session.scalars(
        select(CreditHold)
        .options(selectinload(CreditHold.usage_job))
        .where(
            CreditHold.status == CreditHoldStatus.HELD,
            CreditHold.expires_at <= now,
        ),
    ).all()
    for hold in stale_holds:
        release_credit_hold(
            session,
            hold_id=hold.id,
            error_code="credit_hold_expired",
            error_detail="Credit hold expired before completion.",
        )
    return len(stale_holds)


def create_usage_job(
    session: Session,
    *,
    session_token: str,
    idempotency_key: str,
    operation_kind: UsageOperationKind,
    request_ref: str,
    estimated_units: int,
) -> dict[str, object]:
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        expire_stale_holds(session)
        normalized_idempotency_key = _normalize_required_text(idempotency_key, field_name="idempotency_key")
        existing_job = session.scalar(
            select(UsageJob)
            .options(selectinload(UsageJob.credit_hold))
            .where(
                UsageJob.user_id == context.user.id,
                UsageJob.idempotency_key == normalized_idempotency_key,
            ),
        )
        if existing_job is not None:
            return _present_create(existing_job)

        job = reserve_credit_for_job(
            session,
            user_id=context.user.id,
            operation_kind=operation_kind,
            estimated_units=estimated_units,
            idempotency_key=normalized_idempotency_key,
            request_ref=_normalize_required_text(request_ref, field_name="request_ref"),
            hold_expires_at=_hold_expires_at(),
        )
        return _present_create(job)


def capture_usage_job(
    session: Session,
    *,
    session_token: str,
    job_id: UUID,
) -> dict[str, object]:
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        expire_stale_holds(session)
        job = _load_usage_job(session, user_id=context.user.id, job_id=job_id)
        if job.status is UsageJobStatus.SUCCEEDED:
            return _present_job(job)
        if job.status is UsageJobStatus.FAILED:
            raise UsageJobConflictError(f"Usage job {job.id} is already failed.")

        hold = job.credit_hold
        if hold is None:
            raise UsageJobConflictError(f"Usage job {job.id} is missing its credit hold.")

        capture_credit_hold(session, hold_id=hold.id)
        session.flush()
        return _present_job(job)


def release_usage_job(
    session: Session,
    *,
    session_token: str,
    job_id: UUID,
    error_code: str | None,
    reason: str | None,
) -> dict[str, object]:
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        expire_stale_holds(session)
        job = _load_usage_job(session, user_id=context.user.id, job_id=job_id)
        if job.status is UsageJobStatus.FAILED:
            return _present_job(job)
        if job.status is UsageJobStatus.SUCCEEDED:
            raise UsageJobConflictError(f"Usage job {job.id} is already succeeded.")

        hold = job.credit_hold
        if hold is None:
            raise UsageJobConflictError(f"Usage job {job.id} is missing its credit hold.")

        normalized_error_code = _normalize_optional_text(error_code)
        normalized_reason = _normalize_optional_text(reason)
        release_credit_hold(
            session,
            hold_id=hold.id,
            error_code=normalized_error_code or "job_released",
            error_detail=normalized_reason,
        )
        session.flush()
        return _present_job(job)


def get_usage_job(
    session: Session,
    *,
    session_token: str,
    job_id: UUID,
) -> dict[str, object]:
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        expire_stale_holds(session)
        job = _load_usage_job(session, user_id=context.user.id, job_id=job_id)
        return _present_job(job)

