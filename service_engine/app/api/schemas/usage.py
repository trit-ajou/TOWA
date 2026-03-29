from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import CreditHoldStatus, UsageJobStatus, UsageOperationKind


class UsageJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    operation_kind: UsageOperationKind
    request_ref: str
    estimated_units: int


class UsageJobCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: UsageJobStatus
    reserved_units: int
    hold_expires_at: datetime


class UsageJobCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UsageJobReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str | None = None
    reason: str | None = None


class UsageJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_kind: UsageOperationKind
    request_ref: str
    estimated_units: int
    status: UsageJobStatus
    reserved_units: int
    hold_status: CreditHoldStatus
    hold_expires_at: datetime
    error_code: str | None = None
    error_detail: str | None = None
    requested_at: datetime
    finished_at: datetime | None = None

