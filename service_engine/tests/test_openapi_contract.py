from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _json_schema_ref(openapi: dict[str, object], *, path: str, method: str, status_code: str) -> str:
    response = openapi["paths"][path][method]["responses"][status_code]
    return response["content"]["application/json"]["schema"]["$ref"]


def _normalize_snapshot(value):
    if isinstance(value, dict):
        return {
            key: _normalize_snapshot(item)
            for key, item in sorted(value.items())
            if key not in {"title", "description", "operationId", "summary"}
        }
    if isinstance(value, list):
        return [_normalize_snapshot(item) for item in value]
    return value


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


def test_openapi_contract_snapshot_matches_expected_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    snapshot = {
        "securitySchemes": _normalize_snapshot(openapi["components"].get("securitySchemes", {})),
        "paths": _normalize_snapshot(openapi["paths"]),
        "schemas": _normalize_snapshot(
            {
                name: schema
                for name, schema in openapi["components"]["schemas"].items()
                if name not in {"HTTPValidationError", "ValidationError"}
            },
        ),
    }

    assert snapshot == {
        "paths": {
            "/auth/dev/login": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DevLoginRequest"},
                            },
                        },
                        "required": True,
                    },
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/DevLoginResponse"}}}},
                        "409": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "tags": ["auth"],
                },
            },
            "/auth/me": {
                "get": {
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/CurrentUserResponse"}}}},
                        "401": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "security": [{"HTTPBearer": []}],
                    "tags": ["auth"],
                },
            },
            "/healthz": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "additionalProperties": {"type": "string"},
                                        "type": "object",
                                    },
                                },
                            },
                        },
                    },
                    "tags": ["infra"],
                },
            },
            "/usage/jobs": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UsageJobCreateRequest"},
                            },
                        },
                        "required": True,
                    },
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UsageJobCreateResponse"}}}},
                        "401": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "409": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "security": [{"HTTPBearer": []}],
                    "tags": ["usage"],
                },
            },
            "/usage/jobs/{job_id}": {
                "get": {
                    "parameters": [
                        {
                            "in": "path",
                            "name": "job_id",
                            "required": True,
                            "schema": {"format": "uuid", "type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UsageJobResponse"}}}},
                        "401": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "404": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "409": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "security": [{"HTTPBearer": []}],
                    "tags": ["usage"],
                },
            },
            "/usage/jobs/{job_id}/capture": {
                "post": {
                    "parameters": [
                        {
                            "in": "path",
                            "name": "job_id",
                            "required": True,
                            "schema": {"format": "uuid", "type": "string"},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UsageJobCaptureRequest"},
                            },
                        },
                        "required": True,
                    },
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UsageJobResponse"}}}},
                        "401": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "404": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "409": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "security": [{"HTTPBearer": []}],
                    "tags": ["usage"],
                },
            },
            "/usage/jobs/{job_id}/release": {
                "post": {
                    "parameters": [
                        {
                            "in": "path",
                            "name": "job_id",
                            "required": True,
                            "schema": {"format": "uuid", "type": "string"},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UsageJobReleaseRequest"},
                            },
                        },
                        "required": True,
                    },
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UsageJobResponse"}}}},
                        "401": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "404": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "409": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                        "422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}},
                    },
                    "security": [{"HTTPBearer": []}],
                    "tags": ["usage"],
                },
            },
        },
        "schemas": {
            "AuthenticatedUserResponse": {
                "properties": {
                    "created_at": {"format": "date-time", "type": "string"},
                    "email": {"type": "string"},
                    "id": {"format": "uuid", "type": "string"},
                    "nickname": {"type": "string"},
                    "status": {"$ref": "#/components/schemas/UserStatus"},
                },
                "required": ["id", "email", "nickname", "status", "created_at"],
                "type": "object",
            },
            "CreditHoldStatus": {
                "enum": ["held", "captured", "released"],
                "type": "string",
            },
            "CurrentUserResponse": {
                "properties": {
                    "credit_balance": {"type": "integer"},
                    "reserved_units": {"type": "integer"},
                    "user": {"$ref": "#/components/schemas/AuthenticatedUserResponse"},
                },
                "required": ["user", "credit_balance", "reserved_units"],
                "type": "object",
            },
            "DevLoginRequest": {
                "additionalProperties": False,
                "properties": {
                    "email": {"type": "string"},
                    "nickname": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["email"],
                "type": "object",
            },
            "DevLoginResponse": {
                "properties": {
                    "credit_balance": {"type": "integer"},
                    "expires_in": {"type": "integer"},
                    "reserved_units": {"type": "integer"},
                    "session_key": {"type": "string"},
                    "user": {"$ref": "#/components/schemas/AuthenticatedUserResponse"},
                },
                "required": ["session_key", "expires_in", "user", "credit_balance", "reserved_units"],
                "type": "object",
            },
            "ErrorBody": {
                "properties": {
                    "code": {"type": "string"},
                    "details": {"anyOf": [{"additionalProperties": True, "type": "object"}, {"type": "null"}]},
                    "message": {"type": "string"},
                    "retryable": {"type": "boolean"},
                },
                "required": ["code", "message", "retryable"],
                "type": "object",
            },
            "ErrorResponse": {
                "properties": {"error": {"$ref": "#/components/schemas/ErrorBody"}},
                "required": ["error"],
                "type": "object",
            },
            "UsageJobCaptureRequest": {
                "additionalProperties": False,
                "properties": {},
                "type": "object",
            },
            "UsageJobCreateRequest": {
                "additionalProperties": False,
                "properties": {
                    "estimated_units": {"type": "integer"},
                    "idempotency_key": {"type": "string"},
                    "operation_kind": {"$ref": "#/components/schemas/UsageOperationKind"},
                    "request_ref": {"type": "string"},
                },
                "required": ["idempotency_key", "operation_kind", "request_ref", "estimated_units"],
                "type": "object",
            },
            "UsageJobCreateResponse": {
                "properties": {
                    "hold_expires_at": {"format": "date-time", "type": "string"},
                    "job_id": {"format": "uuid", "type": "string"},
                    "reserved_units": {"type": "integer"},
                    "status": {"$ref": "#/components/schemas/UsageJobStatus"},
                },
                "required": ["job_id", "status", "reserved_units", "hold_expires_at"],
                "type": "object",
            },
            "UsageJobReleaseRequest": {
                "additionalProperties": False,
                "properties": {
                    "error_code": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "type": "object",
            },
            "UsageJobResponse": {
                "properties": {
                    "error_code": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "error_detail": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "estimated_units": {"type": "integer"},
                    "finished_at": {"anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}]},
                    "hold_expires_at": {"format": "date-time", "type": "string"},
                    "hold_status": {"$ref": "#/components/schemas/CreditHoldStatus"},
                    "id": {"format": "uuid", "type": "string"},
                    "operation_kind": {"$ref": "#/components/schemas/UsageOperationKind"},
                    "request_ref": {"type": "string"},
                    "requested_at": {"format": "date-time", "type": "string"},
                    "reserved_units": {"type": "integer"},
                    "status": {"$ref": "#/components/schemas/UsageJobStatus"},
                },
                "required": [
                    "id",
                    "operation_kind",
                    "request_ref",
                    "estimated_units",
                    "status",
                    "reserved_units",
                    "hold_status",
                    "hold_expires_at",
                    "requested_at",
                ],
                "type": "object",
            },
            "UsageJobStatus": {
                "enum": ["authorized", "succeeded", "failed"],
                "type": "string",
            },
            "UsageOperationKind": {
                "enum": ["mask", "translate", "inpaint"],
                "type": "string",
            },
            "UserStatus": {
                "enum": ["active", "disabled"],
                "type": "string",
            },
        },
        "securitySchemes": {
            "HTTPBearer": {
                "scheme": "bearer",
                "type": "http",
            },
        },
    }
