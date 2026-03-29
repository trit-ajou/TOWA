from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_includes_cors_header_for_ui_origin() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/healthz",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_usage_jobs_supports_cors_preflight_for_authorized_requests() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/usage/jobs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
