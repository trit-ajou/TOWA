from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import get_db_session
from app.main import create_app
from app.modules.auth.models import User
from app.modules.billing.models import CreditAccount, CreditHold, CreditLedger, UsageJob


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


def _login(client: TestClient, email: str) -> dict[str, object]:
    response = client.post("/auth/dev/login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def test_create_usage_job_reserves_credit_and_is_idempotent(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]
    payload = {
        "idempotency_key": "job-create-1",
        "operation_kind": "translate",
        "request_ref": "page-1",
        "estimated_units": 20,
    }

    first_response = client.post("/usage/jobs", json=payload, headers=_session_headers(session_key))
    second_response = client.post("/usage/jobs", json=payload, headers=_session_headers(session_key))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["job_id"] == second_response.json()["job_id"]
    assert first_response.json()["reserved_units"] == 20
    assert first_response.json()["status"] == "authorized"

    with sqlite_session_factory() as session:
        jobs = session.scalars(select(UsageJob)).all()
        holds = session.scalars(select(CreditHold)).all()
        account = session.scalar(select(CreditAccount))

        assert len(jobs) == 1
        assert len(holds) == 1
        assert account is not None
        assert account.balance_units == 1000
        assert account.reserved_units == 20


def test_create_usage_job_rejects_idempotency_payload_mismatch(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]
    first_payload = {
        "idempotency_key": "job-create-mismatch",
        "operation_kind": "translate",
        "request_ref": "page-1",
        "estimated_units": 20,
    }
    second_payload = {
        "idempotency_key": "job-create-mismatch",
        "operation_kind": "translate",
        "request_ref": "page-2",
        "estimated_units": 20,
    }

    first_response = client.post("/usage/jobs", json=first_payload, headers=_session_headers(session_key))
    second_response = client.post("/usage/jobs", json=second_payload, headers=_session_headers(session_key))

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    _assert_error(second_response.json(), code="usage_conflict")
    assert second_response.json()["error"]["details"]["reason"] == "idempotency_payload_mismatch"


def test_create_usage_job_rejects_insufficient_credit(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    login_payload = _login(client, "user@example.com")
    session_key = login_payload["session_key"]

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        assert account is not None
        account.balance_units = 10
        session.commit()

    response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-too-expensive",
            "operation_kind": "translate",
            "request_ref": "page-2",
            "estimated_units": 20,
        },
        headers=_session_headers(session_key),
    )

    assert response.status_code == 409
    _assert_error(response.json(), code="insufficient_credits")

    with sqlite_session_factory() as session:
        assert session.scalar(select(UsageJob)) is None
        assert session.scalar(select(CreditHold)) is None


def test_create_usage_job_expires_only_authenticated_users_stale_holds(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    first_session_key = _login(client, "first@example.com")["session_key"]
    second_session_key = _login(client, "second@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-stale-first-user",
            "operation_kind": "translate",
            "request_ref": "page-stale",
            "estimated_units": 20,
        },
        headers=_session_headers(first_session_key),
    )
    assert create_response.status_code == 200

    with sqlite_session_factory() as session:
        hold = session.scalar(select(CreditHold))
        assert hold is not None
        hold.expires_at = hold.expires_at.replace(year=2020)
        session.commit()

    second_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-second-user",
            "operation_kind": "translate",
            "request_ref": "page-second",
            "estimated_units": 10,
        },
        headers=_session_headers(second_session_key),
    )

    assert second_response.status_code == 200

    with sqlite_session_factory() as session:
        first_user = session.scalar(select(User).where(User.email == "first@example.com"))
        second_user = session.scalar(select(User).where(User.email == "second@example.com"))
        assert first_user is not None
        assert second_user is not None

        first_account = session.scalar(select(CreditAccount).where(CreditAccount.user_id == first_user.id))
        second_account = session.scalar(select(CreditAccount).where(CreditAccount.user_id == second_user.id))
        assert first_account is not None
        assert second_account is not None
        assert first_account.reserved_units == 20
        assert second_account.reserved_units == 10


def test_create_usage_job_releases_same_users_stale_hold_before_reserving(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-stale-release",
            "operation_kind": "translate",
            "request_ref": "page-stale-release",
            "estimated_units": 20,
        },
        headers=_session_headers(session_key),
    )
    assert create_response.status_code == 200

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        hold = session.scalar(select(CreditHold))
        assert account is not None
        assert hold is not None
        account.balance_units = 20
        hold.expires_at = hold.expires_at.replace(year=2020)
        session.commit()

    next_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-after-expiry",
            "operation_kind": "translate",
            "request_ref": "page-after-expiry",
            "estimated_units": 20,
        },
        headers=_session_headers(session_key),
    )

    assert next_response.status_code == 200

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        holds = session.scalars(select(CreditHold).order_by(CreditHold.expires_at)).all()
        assert account is not None
        assert account.balance_units == 20
        assert account.reserved_units == 20
        assert len(holds) == 2
        assert holds[0].status.value == "released"
        assert holds[1].status.value == "held"


def test_capture_usage_job_captures_credit_only_once(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-capture-1",
            "operation_kind": "inpaint",
            "request_ref": "page-3",
            "estimated_units": 30,
        },
        headers=_session_headers(session_key),
    )
    job_id = create_response.json()["job_id"]

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
    assert first_capture.json()["hold_status"] == "captured"

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        ledger_entries = session.scalars(select(CreditLedger)).all()
        job = session.scalar(select(UsageJob))

        assert account is not None
        assert account.balance_units == 970
        assert account.reserved_units == 0
        assert len(ledger_entries) == 1
        assert job is not None
        assert job.status.value == "succeeded"


def test_capture_usage_job_rejects_expired_hold(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-expired-capture",
            "operation_kind": "inpaint",
            "request_ref": "page-expired",
            "estimated_units": 30,
        },
        headers=_session_headers(session_key),
    )
    job_id = create_response.json()["job_id"]

    with sqlite_session_factory() as session:
        hold = session.scalar(select(CreditHold))
        assert hold is not None
        hold.expires_at = hold.expires_at.replace(year=2020)
        session.commit()

    capture_response = client.post(
        f"/usage/jobs/{job_id}/capture",
        json={},
        headers=_session_headers(session_key),
    )
    get_response = client.get(
        f"/usage/jobs/{job_id}",
        headers=_session_headers(session_key),
    )

    assert capture_response.status_code == 409
    _assert_error(capture_response.json(), code="usage_conflict")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "failed"
    assert get_response.json()["hold_status"] == "released"
    assert get_response.json()["error_code"] == "credit_hold_expired"


def test_release_usage_job_releases_credit_only_once(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client, "user@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-release-1",
            "operation_kind": "mask",
            "request_ref": "page-4",
            "estimated_units": 40,
        },
        headers=_session_headers(session_key),
    )
    job_id = create_response.json()["job_id"]

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
    assert first_release.json()["error_code"] == "upstream_error"
    assert first_release.json()["error_detail"] == "timeout"

    with sqlite_session_factory() as session:
        account = session.scalar(select(CreditAccount))
        ledger_entries = session.scalars(select(CreditLedger)).all()
        job = session.scalar(select(UsageJob))

        assert account is not None
        assert account.balance_units == 1000
        assert account.reserved_units == 0
        assert len(ledger_entries) == 0
        assert job is not None
        assert job.status.value == "failed"


def test_get_usage_job_is_scoped_to_the_authenticated_user(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    first_session_key = _login(client, "first@example.com")["session_key"]
    second_session_key = _login(client, "second@example.com")["session_key"]

    create_response = client.post(
        "/usage/jobs",
        json={
            "idempotency_key": "job-scope-1",
            "operation_kind": "translate",
            "request_ref": "page-5",
            "estimated_units": 25,
        },
        headers=_session_headers(first_session_key),
    )
    job_id = create_response.json()["job_id"]

    own_response = client.get(
        f"/usage/jobs/{job_id}",
        headers=_session_headers(first_session_key),
    )
    other_response = client.get(
        f"/usage/jobs/{job_id}",
        headers=_session_headers(second_session_key),
    )

    assert own_response.status_code == 200
    assert other_response.status_code == 404
    _assert_error(other_response.json(), code="usage_job_not_found")

    with sqlite_session_factory() as session:
        users = session.scalars(select(User)).all()
        assert len(users) == 2
