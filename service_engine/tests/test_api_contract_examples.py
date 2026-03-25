from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import get_db_session
from app.main import create_app
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


def test_contract_example_login_and_me_flow(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)

    login_response = client.post(
        "/auth/dev/login",
        json={"email": "user@example.com", "nickname": "tester"},
    )

    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["expires_in"] == 86400

    me_response = client.get(
        "/auth/me",
        headers=_session_headers(login_payload["session_key"]),
    )

    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["user"]["email"] == "user@example.com"
    assert me_payload["credit_balance"] == 1000
    assert me_payload["reserved_units"] == 0


def test_contract_example_usage_hold_is_idempotent_per_user(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = client.post("/auth/dev/login", json={"email": "user@example.com"}).json()["session_key"]

    payload = {
        "idempotency_key": "page-1-translate",
        "operation_kind": "translate",
        "request_ref": "page-1",
        "estimated_units": 20,
    }

    first_response = client.post("/usage/jobs", json=payload, headers=_session_headers(session_key))
    second_response = client.post("/usage/jobs", json=payload, headers=_session_headers(session_key))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["job_id"] == second_response.json()["job_id"]
    assert first_response.json()["status"] == "authorized"
    assert first_response.json()["reserved_units"] == 20


def test_contract_example_insufficient_credit_returns_conflict(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = client.post("/auth/dev/login", json={"email": "user@example.com"}).json()["session_key"]

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        assert account is not None
        account.balance_units = 10
        session.commit()

    response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "too-expensive",
            "operation_kind": "inpaint",
            "request_ref": "page-9",
            "estimated_units": 30,
        },
        headers=_session_headers(session_key),
    )

    assert response.status_code == 409
    _assert_error(response.json(), code="insufficient_credits")


def test_contract_example_duplicate_capture_is_idempotent(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = client.post("/auth/dev/login", json={"email": "user@example.com"}).json()["session_key"]

    job_id = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "capture-example",
            "operation_kind": "translate",
            "request_ref": "page-2",
            "estimated_units": 20,
        },
        headers=_session_headers(session_key),
    ).json()["job_id"]

    first_capture = client.post(
        f"/usage/jobs/{job_id}/capture",
        json={},
        headers=_session_headers(session_key),
    )
    second_capture = client.post(
        f"/usage/jobs/{job_id}/capture",
        json={},
        headers=_session_headers(session_key),
    )

    assert first_capture.status_code == 200
    assert second_capture.status_code == 200
    assert first_capture.json()["status"] == "succeeded"
    assert second_capture.json()["status"] == "succeeded"
    assert first_capture.json()["hold_status"] == "captured"


def test_contract_example_duplicate_release_is_idempotent(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = client.post("/auth/dev/login", json={"email": "user@example.com"}).json()["session_key"]

    job_id = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "release-example",
            "operation_kind": "mask",
            "request_ref": "page-3",
            "estimated_units": 10,
        },
        headers=_session_headers(session_key),
    ).json()["job_id"]

    first_release = client.post(
        f"/usage/jobs/{job_id}/release",
        json={"error_code": "upstream_error", "reason": "timeout"},
        headers=_session_headers(session_key),
    )
    second_release = client.post(
        f"/usage/jobs/{job_id}/release",
        json={"error_code": "ignored", "reason": "ignored"},
        headers=_session_headers(session_key),
    )

    assert first_release.status_code == 200
    assert second_release.status_code == 200
    assert first_release.json()["status"] == "failed"
    assert first_release.json()["hold_status"] == "released"
    assert second_release.json()["status"] == "failed"

