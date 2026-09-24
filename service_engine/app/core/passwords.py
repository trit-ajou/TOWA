from __future__ import annotations

import hashlib
import hmac
import secrets

# Self-contained password hashing via stdlib PBKDF2 to avoid pulling in an extra
# dependency. Stored form: "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>".
_ALGO = "pbkdf2_sha256"
_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    ).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iterations_str, salt, digest = stored.split("$", 3)
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    # Constant-time comparison to avoid leaking match progress via timing.
    return hmac.compare_digest(candidate, digest)
