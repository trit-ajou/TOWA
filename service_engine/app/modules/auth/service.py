from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import ensure_utc, utcnow
from app.core.passwords import hash_password, verify_password
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


class EmailNotAllowedError(AuthServiceError):
    """Dev login is restricted and this email is not on the allowlist."""


class InvalidInviteCodeError(AuthServiceError):
    """Signup invite code is missing or invalid."""


class EmailAlreadyRegisteredError(AuthServiceError):
    """Signup attempted with an email that already has an account."""


class InvalidCredentialsError(AuthServiceError):
    """Login email/password did not match."""


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


def create_password_signup(
    session: Session,
    *,
    email: str,
    password: str,
    invite_code: str,
    nickname: str | None,
) -> DevLoginResult:
    # Invite code is validated before any DB work; codes are configured out of band.
    if invite_code.strip() not in get_settings().signup_invite_codes():
        raise InvalidInviteCodeError("Invalid invite code")
    normalized_email = _normalize_email(email)
    normalized_nickname = _normalize_optional_nickname(nickname)
    password_hash = hash_password(password)
    session_bundle = generate_session_token()

    with session.begin():
        existing = session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            raise EmailAlreadyRegisteredError(f"Email already registered: {normalized_email}")
        user = User(
            email=normalized_email,
            nickname=normalized_nickname or _default_nickname(normalized_email),
            status=UserStatus.ACTIVE,
            password_hash=password_hash,
        )
        session.add(user)
        session.flush()

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


def authenticate_password_login(
    session: Session,
    *,
    email: str,
    password: str,
) -> DevLoginResult:
    normalized_email = _normalize_email(email)
    session_bundle = generate_session_token()

    with session.begin():
        user = session.scalar(
            select(User)
            .options(selectinload(User.credit_account))
            .where(User.email == normalized_email),
        )
        # Same error whether the email is unknown or the password is wrong (no user enumeration).
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

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


def create_dev_session(
    session: Session,
    *,
    email: str,
    nickname: str | None,
) -> DevLoginResult:
    normalized_email = _normalize_email(email)
    # Temporary access gate: when an allowlist is configured, only those emails may sign in.
    allowed_emails = get_settings().dev_login_allowed_emails()
    if allowed_emails and normalized_email.lower() not in allowed_emails:
        raise EmailNotAllowedError(f"Email not permitted to sign in: {normalized_email}")
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
