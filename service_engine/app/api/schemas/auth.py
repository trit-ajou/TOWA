from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import UserStatus


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    nickname: str
    status: UserStatus
    created_at: datetime


class DevLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    nickname: str | None = None


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    invite_code: str
    nickname: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class DevLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_key: str
    expires_in: int
    user: AuthenticatedUserResponse
    credit_balance: int
    reserved_units: int


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: AuthenticatedUserResponse
    credit_balance: int
    reserved_units: int

