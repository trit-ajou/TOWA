from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import inspect, select

from app.cli import dev_admin
from app.core.clock import utcnow
from app.db.base import Base
from app.db.enums import UsageOperationKind
from app.db.session import make_engine, make_session_factory
from app.modules.auth.models import User
from app.modules.billing.credits import reserve_credit_for_job
from app.modules.billing.models import CreditAccount
from app.modules.devtools import service as devtools_service


def _parse_json_output(text: str) -> dict[str, object]:
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines
    return json.loads(lines[-1])


def test_dev_admin_migrate_creates_tables(monkeypatch, tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'cli-migrate.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    exit_code = dev_admin.main(["migrate"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = _parse_json_output(captured.out)
    assert payload == {"action": "migrate", "revision": "head", "status": "ok"}

    engine = make_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {"users", "auth_sessions", "credit_accounts", "usage_jobs", "credit_holds", "credit_ledger"}.issubset(
            set(inspector.get_table_names()),
        )
    finally:
        engine.dispose()


def test_dev_admin_seed_grant_and_reset_credit_workflow(monkeypatch, tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'cli-workflow.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert dev_admin.main(["migrate"]) == 0
    capsys.readouterr()

    assert dev_admin.main(
        [
            "seed-user",
            "--email",
            "user@example.com",
            "--nickname",
            "tester",
            "--initial-balance",
            "1500",
        ],
    ) == 0
    seed_payload = _parse_json_output(capsys.readouterr().out)
    assert seed_payload["created_user"] is True
    assert seed_payload["created_account"] is True
    assert seed_payload["balance_units"] == 1500

    assert dev_admin.main(["grant-credits", "--email", "user@example.com", "--units", "250"]) == 0
    grant_payload = _parse_json_output(capsys.readouterr().out)
    assert grant_payload["balance_units"] == 1750

    assert dev_admin.main(["reset-credits", "--email", "user@example.com", "--balance", "1000"]) == 0
    reset_payload = _parse_json_output(capsys.readouterr().out)
    assert reset_payload["balance_units"] == 1000
    assert reset_payload["reserved_units"] == 0

    engine = make_engine(database_url)
    session_factory = make_session_factory(engine)
    try:
        with session_factory() as session:
            account = session.scalar(select(CreditAccount))
            assert account is not None
            assert account.balance_units == 1000
            assert account.reserved_units == 0
    finally:
        engine.dispose()


def test_dev_admin_reset_credits_refuses_when_hold_exists(monkeypatch, tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'cli-held.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    try:
        with session_factory() as session:
            user = devtools_service.seed_user(
                session,
                email="user@example.com",
                nickname="tester",
                initial_balance=1000,
            )
        with session_factory() as session:
            user_model = session.scalar(select(User).where(User.email == "user@example.com"))
            assert user_model is not None
            reserve_credit_for_job(
                session,
                user_id=user_model.id,
                operation_kind=UsageOperationKind.TRANSLATE,
                estimated_units=20,
                idempotency_key="held-job",
                request_ref="page-1",
                hold_expires_at=utcnow(),
            )
            session.commit()

        exit_code = dev_admin.main(["reset-credits", "--email", "user@example.com", "--balance", "1000"])
        captured = capsys.readouterr()

        assert user.user_id
        assert exit_code == 1
        error_payload = _parse_json_output(captured.err)
        assert error_payload["error"] == "Cannot reset credits while held credit exists."
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
