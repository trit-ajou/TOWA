from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _json_schema_ref(
    openapi: dict[str, object],
    *,
    path: str,
    method: str,
    status_code: str,
    content_type: str = "application/json",
) -> str:
    response = openapi["paths"][path][method]["responses"][status_code]
    return response["content"][content_type]["schema"]["$ref"]


def test_auth_usage_and_storage_routes_document_common_error_envelope() -> None:
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
        path="/api/v1/projects",
        method="post",
        status_code="409",
    ) == "#/components/schemas/ErrorResponse"
    assert _json_schema_ref(
        openapi,
        path="/api/v1/pages/{page_id}",
        method="delete",
        status_code="404",
    ) == "#/components/schemas/ErrorResponse"


def test_openapi_documents_project_and_page_storage_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    paths = openapi["paths"]
    schemas = openapi["components"]["schemas"]

    assert set(paths["/api/v1/projects"].keys()) == {"get", "post"}
    assert set(paths["/api/v1/projects/{project_id}"].keys()) == {"get", "patch", "delete"}
    assert set(paths["/api/v1/projects/{project_id}/pages"].keys()) == {"get", "post"}
    assert set(paths["/api/v1/pages/{page_id}"].keys()) == {"delete"}
    assert set(paths["/api/v1/pages/{page_id}/snapshot"].keys()) == {"get", "put"}
    assert set(paths["/api/v1/pages/{page_id}/thumbnail"].keys()) == {"get"}

    assert _json_schema_ref(
        openapi,
        path="/api/v1/projects",
        method="post",
        status_code="200",
    ) == "#/components/schemas/ProjectResponse"
    assert _json_schema_ref(
        openapi,
        path="/api/v1/projects",
        method="get",
        status_code="200",
    ) == "#/components/schemas/ProjectListResponse"
    assert _json_schema_ref(
        openapi,
        path="/api/v1/projects/{project_id}/pages",
        method="get",
        status_code="200",
    ) == "#/components/schemas/PageListResponse"
    assert _json_schema_ref(
        openapi,
        path="/api/v1/projects/{project_id}/pages",
        method="post",
        status_code="200",
    ) == "#/components/schemas/PageSummaryEnvelope"
    assert _json_schema_ref(
        openapi,
        path="/api/v1/pages/{page_id}/snapshot",
        method="put",
        status_code="200",
    ) == "#/components/schemas/PageSummaryEnvelope"

    page_create_request = paths["/api/v1/projects/{project_id}/pages"]["post"]["requestBody"]["content"]
    page_update_request = paths["/api/v1/pages/{page_id}/snapshot"]["put"]["requestBody"]["content"]
    assert "multipart/form-data" in page_create_request
    assert "multipart/form-data" in page_update_request

    snapshot_get_content = paths["/api/v1/pages/{page_id}/snapshot"]["get"]["responses"]["200"]["content"]
    assert "multipart/mixed" in snapshot_get_content

    thumbnail_get_content = paths["/api/v1/pages/{page_id}/thumbnail"]["get"]["responses"]["200"]["content"]
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(set(thumbnail_get_content.keys()))

    project_response = schemas["ProjectResponse"]
    assert "thumbnail_url" in project_response["properties"]
    assert set(project_response["required"]) == {
        "id",
        "name",
        "source_lang",
        "target_lang",
        "page_count",
        "status",
        "folder",
        "config",
        "created_at",
        "updated_at",
    }

    page_summary = schemas["PageSummaryResponse"]
    assert page_summary["properties"]["thumbnail_url"]["type"] == "string"
