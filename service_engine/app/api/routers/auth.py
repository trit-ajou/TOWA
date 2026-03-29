from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_session_token
from app.api.errors import openapi_error_responses, raise_auth_http_error
from app.api.schemas.auth import (
    AuthenticatedUserResponse,
    CurrentUserResponse,
    DevLoginRequest,
    DevLoginResponse,
)
from app.db import get_db_session
from app.modules.auth import service as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _current_user_response(context: auth_service.AuthenticatedContext) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=AuthenticatedUserResponse.model_validate(context.user),
        credit_balance=context.credit_account.balance_units,
        reserved_units=context.credit_account.reserved_units,
    )


@router.post(
    "/dev/login",
    response_model=DevLoginResponse,
    responses=openapi_error_responses(422, 409),
)
def dev_login(
    payload: DevLoginRequest,
    session: Session = Depends(get_db_session),
) -> DevLoginResponse:
    try:
        result = auth_service.create_dev_session(
            session,
            email=payload.email,
            nickname=payload.nickname,
        )
    except Exception as exc:  # noqa: BLE001
        raise_auth_http_error(exc)
    return DevLoginResponse(
        session_key=result.session_key,
        expires_in=result.expires_in,
        user=AuthenticatedUserResponse.model_validate(result.context.user),
        credit_balance=result.context.credit_account.balance_units,
        reserved_units=result.context.credit_account.reserved_units,
    )


@router.get("/me", response_model=CurrentUserResponse, responses=openapi_error_responses(401))
def get_me(
    session_token: str = Depends(get_session_token),
    session: Session = Depends(get_db_session),
) -> CurrentUserResponse:
    try:
        context = auth_service.authenticate_session_token(session, session_token=session_token)
    except Exception as exc:  # noqa: BLE001
        raise_auth_http_error(exc)
    return _current_user_response(context)

