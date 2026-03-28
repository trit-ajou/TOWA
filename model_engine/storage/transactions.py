from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from ..contracts.stages import StageRequest


def workspace_root_from_request(request: StageRequest) -> Path:
    if request.runtime_context is None:
        return Path("/tmp/towa/workspace")
    parsed = urlparse(request.runtime_context.workspace_uri)
    if parsed.scheme != "file":
        raise RuntimeError("transaction-scoped storage currently requires file:// workspace_uri")
    return Path(parsed.path)


def stage_run_slug(stage_run_id: str) -> str:
    return stage_run_id.replace(":", "_")


def stage_transaction_dir(request: StageRequest) -> Path:
    root = workspace_root_from_request(request)
    stage_dir = (
        root
        / "transactions"
        / request.pipeline_id
        / request.stage_name
        / stage_run_slug(request.stage_run_id)
    )
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir
