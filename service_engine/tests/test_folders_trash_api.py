from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db_session
from app.main import create_app


def _build_test_client(sqlite_session_factory: sessionmaker) -> TestClient:
    app = create_app()

    def override_db_session():
        with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def _session_headers(session_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_key}"}


def _login(client: TestClient, email: str = "user@example.com") -> str:
    response = client.post("/auth/dev/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["session_key"]


def _assert_error(payload: dict[str, object], *, code: str, reason: str | None = None) -> None:
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    if reason is not None:
        assert error["details"]["reason"] == reason


def _create_folder(
    client: TestClient,
    session_key: str,
    *,
    name: str,
    parent_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/folders",
        json={"name": name, "parent_id": parent_id},
        headers=_session_headers(session_key),
    )
    assert response.status_code == 200
    return response.json()


def _create_project(
    client: TestClient,
    session_key: str,
    *,
    project_id: str,
    folder_id: str | None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/projects",
        json={
            "id": project_id,
            "name": f"project-{project_id[-4:]}",
            "thumbnail_url": None,
            "source_lang": "ja",
            "target_lang": "ko",
            "status": "todo",
            "folder_id": folder_id,
            "config": {},
        },
        headers=_session_headers(session_key),
    )
    assert response.status_code == 200
    return response.json()


def test_folder_crud_validation_cycle_and_user_scope(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)

    root = _create_folder(client, session_key, name="주간연재")
    child = _create_folder(client, session_key, name="점프", parent_id=root["id"])
    assert child["path"] == "주간연재/점프"

    duplicate_response = client.post(
        "/api/v1/folders",
        json={"name": "주간연재", "parent_id": None},
        headers=_session_headers(session_key),
    )
    assert duplicate_response.status_code == 409
    _assert_error(duplicate_response.json(), code="folder_conflict", reason="duplicate_folder_name")

    invalid_response = client.post(
        "/api/v1/folders",
        json={"name": "bad/name", "parent_id": None},
        headers=_session_headers(session_key),
    )
    assert invalid_response.status_code == 422

    search_response = client.get(
        "/api/v1/folders?search=점",
        headers=_session_headers(session_key),
    )
    assert search_response.status_code == 200
    assert [item["id"] for item in search_response.json()["items"]] == [child["id"]]

    rename_response = client.patch(
        f"/api/v1/folders/{child['id']}",
        json={"name": "매거진"},
        headers=_session_headers(session_key),
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["path"] == "주간연재/매거진"

    cycle_response = client.patch(
        f"/api/v1/folders/{root['id']}",
        json={"parent_id": child["id"]},
        headers=_session_headers(session_key),
    )
    assert cycle_response.status_code == 400
    _assert_error(cycle_response.json(), code="bad_request")

    other_session_key = _login(client, "other@example.com")
    other_response = client.patch(
        f"/api/v1/folders/{root['id']}",
        json={"name": "steal"},
        headers=_session_headers(other_session_key),
    )
    assert other_response.status_code == 404
    _assert_error(other_response.json(), code="folder_not_found")


def test_folder_delete_reparent_conflict_and_success(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)

    parent = _create_folder(client, session_key, name="Parent")
    _create_folder(client, session_key, name="Conflict", parent_id=parent["id"])
    _create_folder(client, session_key, name="Conflict")

    conflict_response = client.delete(
        f"/api/v1/folders/{parent['id']}?reparent=true",
        headers=_session_headers(session_key),
    )
    assert conflict_response.status_code == 409
    _assert_error(conflict_response.json(), code="folder_conflict", reason="duplicate_folder_name")

    source = _create_folder(client, session_key, name="Source")
    child = _create_folder(client, session_key, name="Child", parent_id=source["id"])
    project = _create_project(
        client,
        session_key,
        project_id="01ARZ3NDEKTSV4RRFFQ69G5FB0",
        folder_id=source["id"],
    )

    delete_response = client.delete(
        f"/api/v1/folders/{source['id']}?reparent=true",
        headers=_session_headers(session_key),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None

    folders_response = client.get("/api/v1/folders", headers=_session_headers(session_key))
    assert folders_response.status_code == 200
    moved_child = next(item for item in folders_response.json()["items"] if item["id"] == child["id"])
    assert moved_child["parent_id"] is None
    assert moved_child["path"] == "Child"

    project_response = client.get(f"/api/v1/projects/{project['id']}", headers=_session_headers(session_key))
    assert project_response.status_code == 200
    assert project_response.json()["folder_id"] is None


def test_folder_cascade_restore_and_permanent_delete(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)

    root = _create_folder(client, session_key, name="Cascade")
    child = _create_folder(client, session_key, name="Nested", parent_id=root["id"])
    project = _create_project(
        client,
        session_key,
        project_id="01ARZ3NDEKTSV4RRFFQ69G5FB1",
        folder_id=child["id"],
    )

    non_empty_response = client.delete(f"/api/v1/folders/{root['id']}", headers=_session_headers(session_key))
    assert non_empty_response.status_code == 409
    _assert_error(non_empty_response.json(), code="folder_conflict", reason="folder_not_empty")

    live_permanent_response = client.delete(
        f"/api/v1/folders/{root['id']}?permanent=true",
        headers=_session_headers(session_key),
    )
    assert live_permanent_response.status_code == 400

    cascade_response = client.delete(
        f"/api/v1/folders/{root['id']}?cascade=trash",
        headers=_session_headers(session_key),
    )
    assert cascade_response.status_code == 200
    assert cascade_response.json()["deleted_at"] is not None

    hidden_project_response = client.get(f"/api/v1/projects/{project['id']}", headers=_session_headers(session_key))
    assert hidden_project_response.status_code == 404

    trash_response = client.get("/api/v1/trash", headers=_session_headers(session_key))
    assert trash_response.status_code == 200
    trash_types = [item["type"] for item in trash_response.json()["items"]]
    assert trash_types.count("folder") == 2
    assert trash_types.count("project") == 1

    restore_response = client.post(
        f"/api/v1/folders/{root['id']}/restore",
        headers=_session_headers(session_key),
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None

    restored_project_response = client.get(f"/api/v1/projects/{project['id']}", headers=_session_headers(session_key))
    assert restored_project_response.status_code == 200
    assert restored_project_response.json()["folder_path"] == "Cascade/Nested"

    cascade_again_response = client.delete(
        f"/api/v1/folders/{root['id']}?cascade=trash",
        headers=_session_headers(session_key),
    )
    assert cascade_again_response.status_code == 200

    permanent_response = client.delete(
        f"/api/v1/folders/{root['id']}?permanent=true",
        headers=_session_headers(session_key),
    )
    assert permanent_response.status_code == 200
    assert permanent_response.json() == {"deleted": True, "folder_id": root["id"]}

    empty_trash_response = client.get("/api/v1/trash", headers=_session_headers(session_key))
    assert empty_trash_response.status_code == 200
    assert empty_trash_response.json()["items"] == []
