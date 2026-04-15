from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UsageJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    operation_kind: str
    request_ref: str
    estimated_units: int = Field(gt=0)


class UsageJobCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UsageJobReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str | None = None
    reason: str | None = None


ModelOperationKind = Literal["detect", "inpaint", "translate", "pipeline"]
ModelJobStatus = Literal["queued", "running", "succeeded", "failed", "partial"]


class ModelJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "v1"
    idempotency_key: str
    operation_kind: ModelOperationKind
    request_ref: str
    document: dict[str, Any]
    artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    runtime_context: dict[str, Any]


class ModelJobCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    pipeline_id: str
    status: ModelJobStatus
    operation_kind: ModelOperationKind
    request_ref: str
    status_url: str


class ModelJobDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    pipeline_id: str
    status: ModelJobStatus
    operation_kind: ModelOperationKind
    request_ref: str
    document: dict[str, Any]
    document_patch: dict[str, Any] = Field(default_factory=lambda: {"patches": []})
    artifacts: dict[str, dict[str, Any]]
    stage_reports: list[dict[str, Any]] = Field(default_factory=list)
    error: dict[str, Any] | None = None
