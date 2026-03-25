from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.core.clock import utcnow
from app.db.enums import UsageOperationKind, UsageJobStatus, UserStatus
from app.modules.auth.models import User
from app.modules.billing.credits import capture_credit_hold, release_credit_hold, reserve_credit_for_job
from app.modules.billing.models import CreditAccount


def _create_user_with_account(session_factory: sessionmaker, *, balance_units: int = 1000):
    with session_factory() as session:
        user = User(
            email="user@example.com",
            nickname="tester",
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        session.flush()

        account = CreditAccount(user_id=user.id, balance_units=balance_units, reserved_units=0)
        session.add(account)
        session.commit()
        return user.id


def test_reserve_and_capture_credit_flow(sqlite_session_factory: sessionmaker) -> None:
    user_id = _create_user_with_account(sqlite_session_factory, balance_units=500)

    with sqlite_session_factory() as session:
        job = reserve_credit_for_job(
            session,
            user_id=user_id,
            operation_kind=UsageOperationKind.TRANSLATE,
            estimated_units=120,
            idempotency_key="job-1",
            request_ref="page-1",
            hold_expires_at=utcnow() + timedelta(minutes=10),
        )
        hold = job.credit_hold
        assert hold is not None
        ledger_entry = capture_credit_hold(session, hold_id=hold.id)
        session.commit()

        session.refresh(job)
        session.refresh(hold)
        account = session.query(CreditAccount).filter_by(user_id=user_id).one()

        assert job.status is UsageJobStatus.SUCCEEDED
        assert hold.status.value == "captured"
        assert ledger_entry.delta_units == -120
        assert account.balance_units == 380
        assert account.reserved_units == 0


def test_release_credit_flow(sqlite_session_factory: sessionmaker) -> None:
    user_id = _create_user_with_account(sqlite_session_factory, balance_units=500)

    with sqlite_session_factory() as session:
        job = reserve_credit_for_job(
            session,
            user_id=user_id,
            operation_kind=UsageOperationKind.MASK,
            estimated_units=75,
            idempotency_key="job-2",
            request_ref="page-2",
            hold_expires_at=utcnow() + timedelta(minutes=10),
        )
        hold = job.credit_hold
        assert hold is not None
        release_credit_hold(
            session,
            hold_id=hold.id,
            error_code="upstream_error",
            error_detail="temporary failure",
        )
        session.commit()

        account = session.query(CreditAccount).filter_by(user_id=user_id).one()
        assert account.balance_units == 500
        assert account.reserved_units == 0


def test_credit_account_optimistic_lock(sqlite_session_factory: sessionmaker) -> None:
    user_id = _create_user_with_account(sqlite_session_factory, balance_units=100)

    session_a = sqlite_session_factory()
    session_b = sqlite_session_factory()
    try:
        account_a = session_a.query(CreditAccount).filter_by(user_id=user_id).one()
        account_b = session_b.query(CreditAccount).filter_by(user_id=user_id).one()

        account_a.balance_units += 10
        session_a.commit()

        account_b.reserved_units += 5
        with pytest.raises(StaleDataError):
            session_b.commit()
    finally:
        session_a.close()
        session_b.close()

