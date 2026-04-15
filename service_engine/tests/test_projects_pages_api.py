from __future__ import annotations

import json
from email.parser import BytesParser
from email.policy import default

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.db import get_db_session
from app.main import create_app

PROJECT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
PAGE_ID_1 = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
PAGE_ID_2 = "01ARZ3NDEKTSV4RRFFQ69G5FAX"


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


def _assert_error(payload: dict[str, object], *, code: str) -> None:
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == code


def _create_project(client: TestClient, session_key: str, *, thumbnail_url=None) -> dict[str, object]:
    response = client.post(
        "/api/v1/projects",
        json={
            "id": PROJECT_ID,
            "name": "원피스 1122화",
            "thumbnail_url": thumbnail_url,
            "source_lang": "ja",
            "target_lang": "ko",
            "status": "todo",
            "folder": "주간연재/점프",
            "config": {"auto_detect": True},
        },
        headers=_session_headers(session_key),
    )
    assert response.status_code == 200
    return response.json()


def _snapshot_files(*, page_id: str, index: int, status: str = "waiting") -> dict[str, tuple[str, bytes, str]]:
    metadata = {
        "page": {
            "id": page_id,
            "project_id": PROJECT_ID,
            "index": index,
            "status": status,
            "text_blocks": [
                {
                    "id": "tb_001",
                    "page_id": page_id,
                    "bbox": {"x": 10, "y": 20, "width": 30, "height": 40},
                    "original": "おはよう",
                    "translated": "안녕",
                },
            ],
        },
    }
    return {
        "metadata": ("metadata.json", json.dumps(metadata).encode("utf-8"), "application/json"),
        "original_image": ("original.png", b"original-image", "image/png"),
        "layer_blob": ("page.bpy", b"layer-blob", "application/octet-stream"),
        "thumbnail": ("thumb.webp", b"thumbnail-bytes", "image/webp"),
    }


def _parse_multipart_parts(response) -> dict[str, dict[str, object]]:
    raw_message = (
        f"Content-Type: {response.headers['content-type']}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + response.content
    )
    message = BytesParser(policy=default).parsebytes(raw_message)
    parts: dict[str, dict[str, object]] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="Content-Disposition")
        parts[name] = {
            "content_type": part.get_content_type(),
            "payload": part.get_payload(decode=True),
        }
    return parts


def test_project_crud_and_thumbnail_round_trip(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)

    created = _create_project(client, session_key)
    assert created["thumbnail_url"] is None
    assert created["page_count"] == 0

    patch_response = client.patch(
        f"/api/v1/projects/{PROJECT_ID}",
        json={"thumbnail_url": "https://storage.example.test/covers/project.webp", "status": "in-progress"},
        headers=_session_headers(session_key),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["thumbnail_url"] == "https://storage.example.test/covers/project.webp"
    assert patch_response.json()["status"] == "in-progress"

    list_response = client.get("/api/v1/projects", headers=_session_headers(session_key))
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["thumbnail_url"] == "https://storage.example.test/covers/project.webp"

    delete_response = client.delete(f"/api/v1/projects/{PROJECT_ID}", headers=_session_headers(session_key))
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True, "project_id": PROJECT_ID}

    missing_response = client.get(f"/api/v1/projects/{PROJECT_ID}", headers=_session_headers(session_key))
    assert missing_response.status_code == 404
    _assert_error(missing_response.json(), code="project_not_found")


def test_page_snapshot_round_trip_and_project_page_count(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    create_page_response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1),
        headers=_session_headers(session_key),
    )
    assert create_page_response.status_code == 200
    page_payload = create_page_response.json()["page"]
    assert page_payload["id"] == PAGE_ID_1
    assert page_payload["index"] == 1
    assert page_payload["thumbnail_url"] == f"http://testserver/api/v1/pages/{PAGE_ID_1}/thumbnail"

    project_response = client.get(f"/api/v1/projects/{PROJECT_ID}", headers=_session_headers(session_key))
    assert project_response.status_code == 200
    assert project_response.json()["page_count"] == 1

    list_pages_response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        headers=_session_headers(session_key),
    )
    assert list_pages_response.status_code == 200
    assert list_pages_response.json()["items"][0]["thumbnail_url"] == f"http://testserver/api/v1/pages/{PAGE_ID_1}/thumbnail"

    thumbnail_response = client.get(
        f"/api/v1/pages/{PAGE_ID_1}/thumbnail",
        headers=_session_headers(session_key),
    )
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"] == "image/webp"
    assert thumbnail_response.content == b"thumbnail-bytes"

    snapshot_response = client.get(
        f"/api/v1/pages/{PAGE_ID_1}/snapshot",
        headers=_session_headers(session_key),
    )
    assert snapshot_response.status_code == 200
    parts = _parse_multipart_parts(snapshot_response)
    assert set(parts) == {"metadata", "original_image", "layer_blob", "thumbnail"}
    assert parts["original_image"]["content_type"] == "image/png"
    assert parts["thumbnail"]["payload"] == b"thumbnail-bytes"
    metadata_payload = json.loads(parts["metadata"]["payload"].decode("utf-8"))
    assert metadata_payload["page"]["id"] == PAGE_ID_1
    assert metadata_payload["page"]["status"] == "waiting"

    update_response = client.put(
        f"/api/v1/pages/{PAGE_ID_1}/snapshot",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1, status="done"),
        headers=_session_headers(session_key),
    )
    assert update_response.status_code == 200
    assert update_response.json()["page"]["status"] == "done"


def test_page_create_rejects_non_append_index(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=2),
        headers=_session_headers(session_key),
    )

    assert response.status_code == 409
    _assert_error(response.json(), code="page_conflict")
    assert response.json()["error"]["details"]["reason"] == "append_only_index_mismatch"


def test_page_delete_reindexes_remaining_pages(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    create_first = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1),
        headers=_session_headers(session_key),
    )
    assert create_first.status_code == 200
    create_second = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_2, index=2),
        headers=_session_headers(session_key),
    )
    assert create_second.status_code == 200

    delete_response = client.delete(
        f"/api/v1/pages/{PAGE_ID_1}",
        headers=_session_headers(session_key),
    )
    assert delete_response.status_code == 200

    list_pages_response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        headers=_session_headers(session_key),
    )
    assert list_pages_response.status_code == 200
    items = list_pages_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == PAGE_ID_2
    assert items[0]["index"] == 1


def test_page_thumbnail_is_private_to_project_owner(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    owner_session_key = _login(client, "owner@example.com")
    _create_project(client, owner_session_key)
    create_page_response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1),
        headers=_session_headers(owner_session_key),
    )
    assert create_page_response.status_code == 200

    other_session_key = _login(client, "other@example.com")
    response = client.get(
        f"/api/v1/pages/{PAGE_ID_1}/thumbnail",
        headers=_session_headers(other_session_key),
    )

    assert response.status_code == 404
    _assert_error(response.json(), code="page_not_found")


@pytest.mark.postgres
def test_page_snapshot_update_works_on_postgresql(postgres_session_factory: sessionmaker) -> None:
    client = _build_test_client(postgres_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    create_response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1),
        headers=_session_headers(session_key),
    )
    assert create_response.status_code == 200

    update_response = client.put(
        f"/api/v1/pages/{PAGE_ID_1}/snapshot",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1, status="done"),
        headers=_session_headers(session_key),
    )

    assert update_response.status_code == 200
    assert update_response.json()["page"]["status"] == "done"


def test_page_create_rejects_invalid_media_type(sqlite_session_factory: sessionmaker) -> None:
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    files = _snapshot_files(page_id=PAGE_ID_1, index=1)
    files["original_image"] = ("original.gif", b"gif-bytes", "image/gif")
    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=files,
        headers=_session_headers(session_key),
    )

    assert response.status_code == 422
    _assert_error(response.json(), code="validation_error")


def test_page_create_rejects_oversized_upload(
    sqlite_session_factory: sessionmaker,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROJECT_THUMBNAIL_MAX_BYTES", "4")
    get_settings.cache_clear()
    client = _build_test_client(sqlite_session_factory)
    session_key = _login(client)
    _create_project(client, session_key)

    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/pages",
        files=_snapshot_files(page_id=PAGE_ID_1, index=1),
        headers=_session_headers(session_key),
    )

    assert response.status_code == 422
    _assert_error(response.json(), code="validation_error")
