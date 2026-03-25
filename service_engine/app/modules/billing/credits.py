from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.enums import CreditHoldStatus, CreditLedgerEntryType, UsageJobStatus, UsageOperationKind
from app.modules.billing.models import CreditAccount, CreditHold, CreditLedger, UsageJob


class CreditServiceError(RuntimeError):
    pass


class MissingCreditAccountError(CreditServiceError):
    pass


class InsufficientCreditsError(CreditServiceError):
    pass


class InvalidCreditHoldStateError(CreditServiceError):
    pass


def load_credit_account(session: Session, *, user_id: UUID, for_update: bool = False) -> CreditAccount:
    statement = select(CreditAccount).where(CreditAccount.user_id == user_id)
    if for_update:
        statement = statement.with_for_update()
    account = session.scalar(statement)
    if account is None:
        raise MissingCreditAccountError(f"Missing credit account for user {user_id}.")
    return account


def reserve_credit_for_job(
    session: Session,
    *,
    user_id: UUID,
    operation_kind: UsageOperationKind,
    estimated_units: int,
    idempotency_key: str,
    request_ref: str,
    hold_expires_at: datetime,
) -> UsageJob:
    if estimated_units <= 0:
        raise ValueError("estimated_units must be positive.")

    account = load_credit_account(session, user_id=user_id, for_update=True)
    available_units = account.balance_units - account.reserved_units
    if available_units < estimated_units:
        raise InsufficientCreditsError("Not enough available credits to reserve.")

    now = utcnow()
    job = UsageJob(
        user_id=user_id,
        operation_kind=operation_kind,
        status=UsageJobStatus.AUTHORIZED,
        estimated_units=estimated_units,
        idempotency_key=idempotency_key,
        request_ref=request_ref,
        requested_at=now,
    )
    hold = CreditHold(
        user_id=user_id,
        usage_job=job,
        estimated_units=estimated_units,
        expires_at=hold_expires_at,
    )
    account.reserved_units += estimated_units
    session.add_all([job, hold])
    session.flush()
    return job


def capture_credit_hold(session: Session, *, hold_id: UUID) -> CreditLedger:
    hold = session.get(CreditHold, hold_id)
    if hold is None:
        raise InvalidCreditHoldStateError(f"Missing hold {hold_id}.")
    if hold.status is not CreditHoldStatus.HELD:
        raise InvalidCreditHoldStateError(f"Credit hold {hold_id} is not capturable.")

    account = load_credit_account(session, user_id=hold.user_id, for_update=True)
    actual_units = hold.estimated_units
    if account.balance_units < actual_units:
        raise InsufficientCreditsError("Not enough credits to capture usage.")

    now = utcnow()
    job = hold.usage_job
    account.balance_units -= actual_units
    account.reserved_units -= hold.estimated_units
    hold.status = CreditHoldStatus.CAPTURED
    hold.resolved_at = now
    job.status = UsageJobStatus.SUCCEEDED
    job.finished_at = now

    ledger_entry = CreditLedger(
        user_id=hold.user_id,
        entry_type=CreditLedgerEntryType.USAGE,
        delta_units=-actual_units,
        idempotency_key=f"usage-capture:{job.id}",
        usage_job=job,
        credit_hold=hold,
        metadata_={"request_ref": job.request_ref},
    )
    session.add(ledger_entry)
    session.flush()
    return ledger_entry


def release_credit_hold(
    session: Session,
    *,
    hold_id: UUID,
    error_code: str | None,
    error_detail: str | None,
) -> CreditHold:
    hold = session.get(CreditHold, hold_id)
    if hold is None:
        raise InvalidCreditHoldStateError(f"Missing hold {hold_id}.")
    if hold.status is not CreditHoldStatus.HELD:
        raise InvalidCreditHoldStateError(f"Credit hold {hold_id} is not releasable.")

    account = load_credit_account(session, user_id=hold.user_id, for_update=True)
    now = utcnow()
    account.reserved_units -= hold.estimated_units
    hold.status = CreditHoldStatus.RELEASED
    hold.resolved_at = now
    hold.usage_job.status = UsageJobStatus.FAILED
    hold.usage_job.error_code = error_code
    hold.usage_job.error_detail = error_detail
    hold.usage_job.finished_at = now
    session.flush()
    return hold

