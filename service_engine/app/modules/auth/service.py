from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import ensure_utc, utcnow
from app.core.settings import get_settings
from app.core.tokens import generate_session_token, hash_token
from app.db.enums import UserStatus
from app.modules.auth.models import AuthSession, User
from app.modules.billing.models import CreditAccount


class AuthServiceError(RuntimeError):
    pass


class InvalidSessionError(AuthServiceError):
    pass


class SessionExpiredError(InvalidSessionError):
    pass


@dataclass(frozen=True)
class AuthenticatedContext:
    user: User
    auth_session: AuthSession
    credit_account: CreditAccount


@dataclass(frozen=True)
class DevLoginResult:
    session_key: str
    expires_in: int
    context: AuthenticatedContext


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("email must not be blank.")
    return normalized


def _normalize_optional_nickname(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _default_nickname(email: str) -> str:
    local_part = email.split("@", 1)[0].strip()
    return (local_part or "user")[:50]


def _ensure_credit_account(session: Session, *, user: User) -> CreditAccount:
    if user.credit_account is None:
        credit_account = CreditAccount(
            user_id=user.id,
            balance_units=get_settings().initial_credit_units,
            reserved_units=0,
        )
        session.add(credit_account)
        session.flush()
        return credit_account
    return user.credit_account


def _build_context(user: User, auth_session: AuthSession) -> AuthenticatedContext:
    credit_account = user.credit_account
    if credit_account is None:
        raise AuthServiceError(f"Missing credit account for user {user.id}.")
    return AuthenticatedContext(
        user=user,
        auth_session=auth_session,
        credit_account=credit_account,
    )


def create_dev_session(
    session: Session,
    *,
    email: str,
    nickname: str | None,
) -> DevLoginResult:
    normalized_email = _normalize_email(email)
    normalized_nickname = _normalize_optional_nickname(nickname)
    session_bundle = generate_session_token()

    with session.begin():
        user = session.scalar(
            select(User)
            .options(selectinload(User.credit_account))
            .where(User.email == normalized_email),
        )
        if user is None:
            user = User(
                email=normalized_email,
                nickname=normalized_nickname or _default_nickname(normalized_email),
                status=UserStatus.ACTIVE,
            )
            session.add(user)
            session.flush()
        elif normalized_nickname is not None:
            user.nickname = normalized_nickname

        credit_account = _ensure_credit_account(session, user=user)
        auth_session = AuthSession(
            user_id=user.id,
            session_token_hash=session_bundle.token_hash,
            expires_at=session_bundle.expires_at,
            last_used_at=utcnow(),
        )
        session.add(auth_session)
        session.flush()

    return DevLoginResult(
        session_key=session_bundle.plaintext,
        expires_in=session_bundle.expires_in,
        context=AuthenticatedContext(
            user=user,
            auth_session=auth_session,
            credit_account=credit_account,
        ),
    )


def authenticate_session_token(session: Session, *, session_token: str) -> AuthenticatedContext:
    auth_session = session.scalar(
        select(AuthSession)
        .options(selectinload(AuthSession.user).selectinload(User.credit_account))
        .where(AuthSession.session_token_hash == hash_token(session_token)),
    )
    if auth_session is None or auth_session.revoked_at is not None:
        raise InvalidSessionError("Session key is invalid.")

    if ensure_utc(auth_session.expires_at) <= utcnow():
        raise SessionExpiredError("Session key has expired.")

    user = auth_session.user
    if user.status is not UserStatus.ACTIVE:
        raise InvalidSessionError("User is inactive.")

    return _build_context(user, auth_session)
