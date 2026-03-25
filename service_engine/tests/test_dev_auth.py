from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.clock import utcnow
from app.core.tokens import hash_token
from app.db import get_db_session
from app.main import create_app
from app.modules.auth.models import AuthSession, User
from app.modules.billing.models import CreditAccount


def _build_test_client(sqlite_session_factory: sessionmaker) -> TestClient:
    app = create_app()

    def override_db_session():
        with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def _session_headers(session_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_key}"}


def _assert_error(payload: dict[str, object], *, code: str) -> None:
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == code


def test_dev_login_creates_user_session_and_initial_credits(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)

    response = client.post(
        "/auth/dev/login",
        json={
            "email": " User@example.com ",
            "nickname": " Tester ",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_key"]
    assert payload["expires_in"] == 24 * 60 * 60
    assert payload["user"]["email"] == "user@example.com"
    assert payload["user"]["nickname"] == "Tester"
    assert payload["credit_balance"] == 1000
    assert payload["reserved_units"] == 0

    with sqlite_session_factory() as session:
        user = session.scalar(select(User))
        account = session.scalar(select(CreditAccount))
        auth_sessions = session.scalars(select(AuthSession)).all()

        assert user is not None
        assert user.email == "user@example.com"
        assert account is not None
        assert account.balance_units == 1000
        assert len(auth_sessions) == 1
        assert auth_sessions[0].session_token_hash == hash_token(payload["session_key"])


def test_dev_login_reuses_existing_user_and_creates_new_session(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)

    first_response = client.post(
        "/auth/dev/login",
        json={"email": "user@example.com", "nickname": "first"},
    )
    second_response = client.post(
        "/auth/dev/login",
        json={"email": "user@example.com", "nickname": "second"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["session_key"] != second_response.json()["session_key"]
    assert second_response.json()["user"]["nickname"] == "second"

    with sqlite_session_factory() as session:
        users = session.scalars(select(User)).all()
        auth_sessions = session.scalars(select(AuthSession)).all()
        assert len(users) == 1
        assert len(auth_sessions) == 2


def test_auth_me_returns_current_user_summary(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    login_response = client.post("/auth/dev/login", json={"email": "user@example.com"})
    session_key = login_response.json()["session_key"]

    response = client.get("/auth/me", headers=_session_headers(session_key))

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "user@example.com"
    assert payload["credit_balance"] == 1000
    assert payload["reserved_units"] == 0


def test_auth_me_rejects_expired_session(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    login_response = client.post("/auth/dev/login", json={"email": "user@example.com"})
    session_key = login_response.json()["session_key"]

    with sqlite_session_factory() as session:
        auth_session = session.scalar(
            select(AuthSession).where(AuthSession.session_token_hash == hash_token(session_key)),
        )
        assert auth_session is not None
        auth_session.expires_at = utcnow() - timedelta(minutes=1)
        session.commit()

    response = client.get("/auth/me", headers=_session_headers(session_key))

    assert response.status_code == 401
    _assert_error(response.json(), code="session_expired")


def test_auth_me_rejects_revoked_session(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    login_response = client.post("/auth/dev/login", json={"email": "user@example.com"})
    session_key = login_response.json()["session_key"]

    with sqlite_session_factory() as session:
        auth_session = session.scalar(
            select(AuthSession).where(AuthSession.session_token_hash == hash_token(session_key)),
        )
        assert auth_session is not None
        auth_session.revoked_at = utcnow()
        session.commit()

    response = client.get("/auth/me", headers=_session_headers(session_key))

    assert response.status_code == 401
    _assert_error(response.json(), code="session_invalid")

