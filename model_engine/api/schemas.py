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
