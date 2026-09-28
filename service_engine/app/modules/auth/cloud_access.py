"""Cloud-access gate for the platform AI key (interim operating policy, 2026-09).

Signed-in users either run AI on the platform key ("cloud", billed against
their credits) or on their own provider key. The platform path can be limited
with a shared cloud password: unlocking it once is remembered per account, and
an admin changing (or clearing) the password revokes every unlock. With no
password configured, cloud is open to every signed-in user.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.passwords import hash_password, verify_password
from app.modules.auth.models import CloudAccessPolicy, User

POLICY_ID = 1


class CloudAccessRequiredError(RuntimeError):
    """The platform key needs the cloud password, which this user has not unlocked."""


class InvalidCloudPasswordError(RuntimeError):
    """The submitted cloud password is wrong."""


@dataclass(frozen=True)
class CloudAccessState:
    required: bool  # a cloud password is configured
    granted: bool  # this user may use the platform key right now


def _policy(session: Session) -> CloudAccessPolicy | None:
    return session.get(CloudAccessPolicy, POLICY_ID)


def cloud_access_state(session: Session, *, user: User) -> CloudAccessState:
    policy = _policy(session)
    if policy is None or policy.password_hash is None:
        return CloudAccessState(required=False, granted=True)
    return CloudAccessState(required=True, granted=user.cloud_access_version == policy.version)


def ensure_cloud_access(session: Session, *, user: User) -> None:
    if not cloud_access_state(session, user=user).granted:
        raise CloudAccessRequiredError("Cloud access requires the cloud password.")


def unlock_cloud_access(session: Session, *, user: User, password: str) -> CloudAccessState:
    """Remember an unlock for `user` if `password` matches. Caller owns the transaction."""
    policy = _policy(session)
    if policy is None or policy.password_hash is None:
        return CloudAccessState(required=False, granted=True)
    if not verify_password(password, policy.password_hash):
        raise InvalidCloudPasswordError("Invalid cloud password.")
    user.cloud_access_version = policy.version
    return CloudAccessState(required=True, granted=True)


def set_cloud_password(session: Session, *, password: str | None) -> int:
    """Set (or clear with None) the cloud password; revokes every existing unlock.

    Returns the new policy version. Caller owns the transaction.
    """
    if password is not None and not password.strip():
        raise ValueError("Cloud password must not be empty.")
    policy = _policy(session)
    if policy is None:
        policy = CloudAccessPolicy(id=POLICY_ID, version=0)
        session.add(policy)
    policy.password_hash = hash_password(password) if password is not None else None
    policy.version = (policy.version or 0) + 1
    session.flush()
    return policy.version
