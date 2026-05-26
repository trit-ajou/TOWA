from __future__ import annotations

import json
import logging
import re
import traceback
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "bearer",
    "credential",
    "password",
    "secret",
    "session_key",
    "token",
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)([\"'\s:=]+)([^,\"'\s]+)"
)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger.log(level, "%s %s", event, _json_fields(fields))


def log_exception(
    logger: logging.Logger,
    event: str,
    **fields: Any,
) -> None:
    fields.setdefault("traceback", traceback.format_exc())
    logger.error("%s %s", event, _json_fields(fields))


def _json_fields(fields: dict[str, Any]) -> str:
    return json.dumps(
        redact_sensitive_data(fields),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def redact_sensitive_data(value: Any) -> Any:
    return _redact_value(value)


def _redact_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(item_key): _redact_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        value = _BEARER_RE.sub("Bearer [redacted]", value)
        return _SECRET_ASSIGNMENT_RE.sub(r"\1\2[redacted]", value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)
