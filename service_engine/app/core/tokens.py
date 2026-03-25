from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import secrets

from app.core.clock import utcnow
from app.core.settings import get_settings


@dataclass(frozen=True)
class SessionTokenBundle:
    plaintext: str
    token_hash: str
    expires_at: datetime
    expires_in: int


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> SessionTokenBundle:
    settings = get_settings()
    plaintext = secrets.token_urlsafe(48)
    expires_at = utcnow() + timedelta(hours=settings.auth_session_ttl_hours)
    expires_in = settings.auth_session_ttl_hours * 60 * 60
    return SessionTokenBundle(
        plaintext=plaintext,
        token_hash=hash_token(plaintext),
        expires_at=expires_at,
        expires_in=expires_in,
    )

