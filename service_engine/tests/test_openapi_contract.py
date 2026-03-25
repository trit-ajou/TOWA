from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _json_schema_ref(openapi: dict[str, object], *, path: str, method: str, status_code: str) -> str:
    response = openapi["paths"][path][method]["responses"][status_code]
    return response["content"]["application/json"]["schema"]["$ref"]


def test_auth_and_usage_routes_document_common_error_envelope() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert _json_schema_ref(
        openapi,
        path="/auth/dev/login",
        method="post",
        status_code="422",
    ) == "#/components/schemas/ErrorResponse"
    assert _json_schema_ref(
        openapi,
        path="/auth/me",
        method="get",
        status_code="401",
    ) == "#/components/schemas/ErrorResponse"
    assert _json_schema_ref(
        openapi,
        path="/usage/jobs",
        method="post",
        status_code="401",
    ) == "#/components/schemas/ErrorResponse"
    assert _json_schema_ref(
        openapi,
        path="/usage/jobs/{job_id}/capture",
        method="post",
        status_code="409",
    ) == "#/components/schemas/ErrorResponse"

