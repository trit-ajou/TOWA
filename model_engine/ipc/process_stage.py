from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Optional

from ..contracts.stages import StageRequest, StageResponse
from ..stages.base import Stage
from .serde import stage_request_to_data, stage_response_from_data


class ProcessStage(Stage):
    """Run a stage in a separate Python process over stdin/stdout JSON IPC."""

    def __init__(
        self,
        stage_name: str,
        *,
        handler: str,
        python_executable: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
        config: Optional[dict[str, object]] = None,
    ) -> None:
        self._stage_name = stage_name
        self._handler = handler
        self._python_executable = python_executable or sys.executable
        self._extra_args = extra_args or []
        self._config = config or {}

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        config = dict(self._config)
        config["handler"] = self._handler
        return config

    def run(self, request: StageRequest) -> StageResponse:
        command = [
            self._python_executable,
            "-m",
            "model_engine.ipc.worker_entrypoint",
            "--handler",
            self._handler,
        ] + list(self._extra_args)

        payload = json.dumps(stage_request_to_data(request))
        env = os.environ.copy()
        env.update(build_stage_env(request))
        completed = subprocess.run(
            command,
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "unknown process error"
            raise RuntimeError(
                "Stage process failed: "
                f"stage={self.stage_name} returncode={completed.returncode} stderr={stderr}"
            )

        stdout = completed.stdout.strip()
        if not stdout:
            raise RuntimeError(f"Stage process returned no stdout payload: stage={self.stage_name}")

        try:
            response_payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Stage process returned invalid JSON: stage={self.stage_name}"
            ) from exc
        return stage_response_from_data(response_payload)


def build_stage_env(request: StageRequest) -> dict[str, str]:
    env: dict[str, str] = {}
    primary = request.resolved_credentials.get("primary_provider")
    if primary is not None:
        env["TOWA_STAGE_PROVIDER_NAME"] = primary.binding.provider
        env["TOWA_STAGE_CREDENTIAL_SOURCE"] = primary.binding.credential_source.value
        env["TOWA_STAGE_CREDENTIAL_ID"] = primary.binding.credential_id
        env["TOWA_STAGE_CREDENTIAL_VERSION"] = primary.binding.credential_version
        env["TOWA_STAGE_BILLING_MODE"] = primary.binding.billing_mode.value
        api_key = primary.secret("api_key")
        if api_key is not None:
            env["TOWA_STAGE_SECRET_API_KEY"] = api_key

    for alias, resolved in request.resolved_credentials.items():
        prefix = f"TOWA_STAGE_{alias.upper()}"
        env[f"{prefix}_PROVIDER_NAME"] = resolved.binding.provider
        env[f"{prefix}_CREDENTIAL_SOURCE"] = resolved.binding.credential_source.value
        env[f"{prefix}_CREDENTIAL_ID"] = resolved.binding.credential_id
        env[f"{prefix}_CREDENTIAL_VERSION"] = resolved.binding.credential_version
        env[f"{prefix}_BILLING_MODE"] = resolved.binding.billing_mode.value
        api_key = resolved.secret("api_key")
        if api_key is not None:
            env[f"{prefix}_SECRET_API_KEY"] = api_key
    return env
