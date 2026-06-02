from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from enum import Enum
from typing import Any, Iterable

from fastapi import Request, Response

CACHE_CONTROL_PRIVATE_REVALIDATE = "private, no-cache"
UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def etag_for_parts(scope: str, *parts: Any) -> str:
    payload = json.dumps(
        [scope, *parts],
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f'W/"{scope}:{digest}"'


def latest_datetime(values: Iterable[datetime | None]) -> datetime:
    normalized = [_normalized_datetime(value) for value in values if value is not None]
    if not normalized:
        return UNIX_EPOCH
    return max(normalized)


def conditional_not_modified_response(
    request: Request,
    *,
    etag: str,
    last_modified: datetime,
) -> Response | None:
    if _if_none_match_satisfied(request.headers.get("if-none-match"), etag):
        return _not_modified_response(etag=etag, last_modified=last_modified)

    if _if_modified_since_satisfied(request.headers.get("if-modified-since"), last_modified):
        return _not_modified_response(etag=etag, last_modified=last_modified)

    return None


def set_cache_headers(response: Response, *, etag: str, last_modified: datetime) -> None:
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = http_datetime(last_modified)
    response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE_REVALIDATE


def http_datetime(value: datetime) -> str:
    return format_datetime(_normalized_datetime(value).replace(microsecond=0), usegmt=True)


def _not_modified_response(*, etag: str, last_modified: datetime) -> Response:
    response = Response(status_code=304)
    set_cache_headers(response, etag=etag, last_modified=last_modified)
    return response


def _if_none_match_satisfied(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False
    candidates = [candidate.strip() for candidate in header_value.split(",")]
    if "*" in candidates:
        return True
    strong_etag = etag[2:] if etag.startswith("W/") else etag
    for candidate in candidates:
        if candidate == etag:
            return True
        candidate_strong = candidate[2:] if candidate.startswith("W/") else candidate
        if candidate_strong == strong_etag:
            return True
    return False


def _if_modified_since_satisfied(header_value: str | None, last_modified: datetime) -> bool:
    if not header_value:
        return False
    try:
        since = parsedate_to_datetime(header_value)
    except (TypeError, ValueError):
        return False
    since = _normalized_datetime(since).replace(microsecond=0)
    comparable_last_modified = _normalized_datetime(last_modified).replace(microsecond=0)
    return comparable_last_modified <= since


def _normalized_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return _normalized_datetime(value).isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)
