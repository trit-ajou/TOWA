from __future__ import annotations

import json
from typing import Mapping, Optional
from urllib import error, request

from ..contracts.models import StageManifest
from ..contracts.stages import StageRequest, StageResponse
from ..ipc.serde import stage_request_to_data, stage_response_from_data
from .base import ModelAdapter


class HttpApiModelAdapter(ModelAdapter):
    """Invoke a remote model provider that speaks the stage request/response contract."""

    def __init__(
        self,
        manifest: StageManifest,
        *,
        endpoint_url: str,
        timeout_seconds: float = 30.0,
        headers: Optional[Mapping[str, str]] = None,
        auth_header_name: Optional[str] = None,
        auth_header_prefix: Optional[str] = None,
        credential_alias: str = "primary_provider",
    ) -> None:
        self._manifest = manifest
        self._endpoint_url = endpoint_url
        self._timeout_seconds = timeout_seconds
        self._headers = dict(headers or {})
        self._auth_header_name = auth_header_name
        self._auth_header_prefix = auth_header_prefix
        self._credential_alias = credential_alias

    @property
    def manifest(self) -> StageManifest:
        return self._manifest

    def run(self, request_payload: StageRequest) -> StageResponse:
        request_data = stage_request_to_data(request_payload)
        body = json.dumps(request_data).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self._headers,
        }
        auth_header_value = self._build_auth_header(request_payload)
        if auth_header_value is not None and self._auth_header_name:
            headers[self._auth_header_name] = auth_header_value

        http_request = request.Request(
            self._endpoint_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                response_data = json.load(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP model adapter failed with status={exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"HTTP model adapter failed to reach endpoint: {self._endpoint_url}"
            ) from exc

        return stage_response_from_data(response_data)

    def _build_auth_header(self, stage_request: StageRequest) -> Optional[str]:
        if not self._auth_header_name:
            return None

        credential = stage_request.resolved_credentials.get(self._credential_alias)
        if credential is None:
            return None

        secret = credential.secret("api_key") or credential.secret("token")
        if not secret:
            return None

        if self._auth_header_prefix:
            return f"{self._auth_header_prefix} {secret}"
        return secret
