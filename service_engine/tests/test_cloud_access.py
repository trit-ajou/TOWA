from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.cli import dev_admin
from app.db import get_db_session
from app.db.session import make_engine, make_session_factory
from app.main import create_app
from app.modules.auth import cloud_access
from app.modules.auth.models import CloudAccessPolicy
from auth_helpers import login_as

# Interim policy: the platform ("cloud") AI key can be limited with a shared
# cloud password; unlocks are remembered per account and revoked on change.


def _client(sqlite_session_factory: sessionmaker) -> TestClient:
    app = create_app()

    def override_db_session():
        with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def _headers(session_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_key}"}


def _set_password(sqlite_session_factory: sessionmaker, password: str | None) -> None:
    with sqlite_session_factory() as session, session.begin():
        cloud_access.set_cloud_password(session, password=password)


def _hold(client: TestClient, key: str, idem: str):
    return client.post(
        "/usage/jobs",
        headers=_headers(key),
        json={"idempotency_key": idem, "operation_kind": "translate", "request_ref": "page-1", "estimated_units": 5},
    )


def test_open_to_everyone_without_a_cloud_password(sqlite_session_factory: sessionmaker) -> None:
    client = _client(sqlite_session_factory)
    login = login_as(client, "a@example.com")
    assert login["cloud_access"] == {"required": False, "granted": True}
    assert _hold(client, login["session_key"], "h1").status_code == 200


def test_cloud_password_gates_platform_holds_until_unlocked(sqlite_session_factory: sessionmaker) -> None:
    client = _client(sqlite_session_factory)
    key = login_as(client, "a@example.com")["session_key"]
    _set_password(sqlite_session_factory, "open-sesame")

    me = client.get("/auth/me", headers=_headers(key)).json()
    assert me["cloud_access"] == {"required": True, "granted": False}
    blocked = _hold(client, key, "h1")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "cloud_access_required"

    wrong = client.post("/auth/cloud-access", headers=_headers(key), json={"password": "nope"})
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "invalid_cloud_password"

    ok = client.post("/auth/cloud-access", headers=_headers(key), json={"password": "open-sesame"})
    assert ok.status_code == 200
    assert ok.json()["cloud_access"] == {"required": True, "granted": True}
    assert _hold(client, key, "h2").status_code == 200

    # Remembered on the account: a new session keeps access.
    again = login_as(client, "a@example.com")
    assert again["cloud_access"]["granted"] is True


def test_changing_the_password_revokes_every_unlock(sqlite_session_factory: sessionmaker) -> None:
    client = _client(sqlite_session_factory)
    key = login_as(client, "a@example.com")["session_key"]
    _set_password(sqlite_session_factory, "first")
    client.post("/auth/cloud-access", headers=_headers(key), json={"password": "first"})

    _set_password(sqlite_session_factory, "second")

    me = client.get("/auth/me", headers=_headers(key)).json()
    assert me["cloud_access"] == {"required": True, "granted": False}
    assert _hold(client, key, "h1").status_code == 403


def test_clearing_the_password_opens_cloud_to_all(sqlite_session_factory: sessionmaker) -> None:
    client = _client(sqlite_session_factory)
    key = login_as(client, "a@example.com")["session_key"]
    _set_password(sqlite_session_factory, "pw")
    _set_password(sqlite_session_factory, None)

    me = client.get("/auth/me", headers=_headers(key)).json()
    assert me["cloud_access"] == {"required": False, "granted": True}
    assert _hold(client, key, "h1").status_code == 200


def test_admin_cli_sets_and_clears_the_cloud_password(monkeypatch, tmp_path: Path, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'cli-cloud.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    assert dev_admin.main(["migrate"]) == 0
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO("cli-secret\n"))
    assert dev_admin.main(["set-cloud-password", "--password-stdin"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["action"] == "set-cloud-password"
    assert "cli-secret" not in json.dumps(out)

    engine = make_engine(database_url)
    try:
        with make_session_factory(engine)() as session:
            policy = session.scalar(select(CloudAccessPolicy))
            assert policy is not None and policy.password_hash and policy.password_hash != "cli-secret"
            first_version = policy.version
        assert dev_admin.main(["clear-cloud-password"]) == 0
        with make_session_factory(engine)() as session:
            policy = session.scalar(select(CloudAccessPolicy))
            assert policy.password_hash is None
            assert policy.version == first_version + 1
    finally:
        engine.dispose()
