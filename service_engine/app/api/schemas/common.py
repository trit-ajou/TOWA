from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    error: ErrorBody

