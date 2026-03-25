from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.enums import CreditHoldStatus, UserStatus
from app.modules.auth.models import User
from app.modules.billing.models import CreditAccount, CreditHold


@dataclass(frozen=True)
class DevUserState:
    user_id: str
    email: str
    nickname: str
    balance_units: int
    reserved_units: int
    created_user: bool = False
    created_account: bool = False


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


def _load_user(session: Session, *, email: str) -> User | None:
    return session.scalar(
        select(User)
        .options(selectinload(User.credit_account))
        .where(User.email == _normalize_email(email)),
    )


def _ensure_credit_account(session: Session, *, user: User, balance_units: int) -> tuple[CreditAccount, bool]:
    if user.credit_account is not None:
        return user.credit_account, False
    account = CreditAccount(
        user_id=user.id,
        balance_units=balance_units,
        reserved_units=0,
    )
    session.add(account)
    session.flush()
    return account, True


def _present(user: User, *, created_user: bool = False, created_account: bool = False) -> DevUserState:
    if user.credit_account is None:
        raise ValueError(f"Missing credit account for user {user.email}.")
    return DevUserState(
        user_id=str(user.id),
        email=user.email,
        nickname=user.nickname,
        balance_units=user.credit_account.balance_units,
        reserved_units=user.credit_account.reserved_units,
        created_user=created_user,
        created_account=created_account,
    )


def seed_user(
    session: Session,
    *,
    email: str,
    nickname: str | None,
    initial_balance: int,
) -> DevUserState:
    if initial_balance < 0:
        raise ValueError("initial_balance must not be negative.")

    normalized_email = _normalize_email(email)
    normalized_nickname = _normalize_optional_nickname(nickname)

    with session.begin():
        created_user = False
        user = _load_user(session, email=normalized_email)
        if user is None:
            user = User(
                email=normalized_email,
                nickname=normalized_nickname or _default_nickname(normalized_email),
                status=UserStatus.ACTIVE,
            )
            session.add(user)
            session.flush()
            created_user = True
        elif normalized_nickname is not None:
            user.nickname = normalized_nickname

        _account, created_account = _ensure_credit_account(
            session,
            user=user,
            balance_units=initial_balance,
        )
        session.refresh(user)
        return _present(user, created_user=created_user, created_account=created_account)


def grant_credits(
    session: Session,
    *,
    email: str,
    units: int,
) -> DevUserState:
    if units <= 0:
        raise ValueError("units must be positive.")

    with session.begin():
        user = _load_user(session, email=email)
        if user is None:
            raise ValueError(f"User {email.strip().lower()} was not found.")
        account, _created = _ensure_credit_account(session, user=user, balance_units=0)
        account.balance_units += units
        session.flush()
        session.refresh(user)
        return _present(user)


def reset_credits(
    session: Session,
    *,
    email: str,
    balance: int,
) -> DevUserState:
    if balance < 0:
        raise ValueError("balance must not be negative.")

    with session.begin():
        user = _load_user(session, email=email)
        if user is None:
            raise ValueError(f"User {email.strip().lower()} was not found.")
        account, _created = _ensure_credit_account(session, user=user, balance_units=0)

        held_count = session.scalar(
            select(func.count())
            .select_from(CreditHold)
            .where(
                CreditHold.user_id == user.id,
                CreditHold.status == CreditHoldStatus.HELD,
            ),
        )
        if held_count:
            raise ValueError("Cannot reset credits while held credit exists.")

        account.balance_units = balance
        account.reserved_units = 0
        session.flush()
        session.refresh(user)
        return _present(user)

