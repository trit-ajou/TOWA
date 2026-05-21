from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import traceback
from typing import Any
from urllib.parse import urlparse

from .contracts.artifacts import ArtifactDescriptor
from .contracts.document_ir import DocumentIR
from .contracts.stages import StageRequest, StageResponse, StageRuntimeContext
from .ipc.serde import (
    artifact_to_data,
    document_to_data,
    stage_request_to_data,
    stage_response_to_data,
)
from .logging_utils import redact_sensitive_data
from .storage import stage_transaction_dir


STAGE_DUMP_ENV = "TOWA_MODEL_ENGINE_STAGE_DUMP"
STAGE_DUMP_COPY_FILES_ENV = "TOWA_MODEL_ENGINE_STAGE_DUMP_COPY_FILES"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class StageArtifactDumper:
    def __init__(self, *, enabled: bool, copy_files: bool = True) -> None:
        self.enabled = enabled
        self.copy_files = copy_files

    @classmethod
    def from_runtime_context(
        cls,
        runtime_context: StageRuntimeContext | None,
        *,
        environ: dict[str, str] | None = None,
    ) -> "StageArtifactDumper":
        environ = environ if environ is not None else os.environ
        metadata = runtime_context.metadata if runtime_context is not None else {}
        enabled = _bool_setting(
            metadata.get("stage_artifact_dump"),
            environ.get(STAGE_DUMP_ENV),
            default=False,
        )
        copy_files = _bool_setting(
            metadata.get("stage_artifact_dump_copy_files"),
            environ.get(STAGE_DUMP_COPY_FILES_ENV),
            default=True,
        )
        return cls(enabled=enabled, copy_files=copy_files)

    def dump_input(self, request: StageRequest) -> Path | None:
        if not self.enabled:
            return None

        dump_dir = self._dump_dir(request)
        _write_json(dump_dir / "stage_request.json", stage_request_to_data(request))
        _write_json(
            dump_dir / "artifacts_before.json",
            _artifact_registry_to_data(request.artifacts),
        )
        if self.copy_files:
            copied_files = _copy_artifacts(
                dump_dir=dump_dir,
                phase="input",
                artifacts=request.artifacts,
            )
            _write_json(dump_dir / "copied_input_files.json", copied_files)
        return dump_dir

    def dump_output(
        self,
        *,
        request: StageRequest,
        response: StageResponse,
        artifacts_after: dict[str, ArtifactDescriptor],
        document_after: DocumentIR | None = None,
    ) -> Path | None:
        if not self.enabled:
            return None

        dump_dir = self._dump_dir(request)
        _write_json(dump_dir / "stage_response.json", stage_response_to_data(response))
        _write_json(
            dump_dir / "artifacts_after.json",
            _artifact_registry_to_data(artifacts_after),
        )
        if document_after is not None:
            _write_json(dump_dir / "document_after.json", document_to_data(document_after))
        if self.copy_files:
            copied_files = _copy_artifacts(
                dump_dir=dump_dir,
                phase="output",
                artifacts=response.artifacts,
            )
            _write_json(dump_dir / "copied_output_files.json", copied_files)
        return dump_dir

    def dump_exception(
        self,
        *,
        request: StageRequest,
        exc: BaseException,
    ) -> Path | None:
        if not self.enabled:
            return None

        dump_dir = self._dump_dir(request)
        _write_json(
            dump_dir / "stage_exception.json",
            {
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        return dump_dir

    def _dump_dir(self, request: StageRequest) -> Path:
        # Keep debug material inside the stage transaction so it follows existing retention rules.
        dump_dir = stage_transaction_dir(request) / "stage_artifact_dump"
        dump_dir.mkdir(parents=True, exist_ok=True)
        return dump_dir


def _bool_setting(
    metadata_value: Any,
    env_value: str | None,
    *,
    default: bool,
) -> bool:
    for value in (metadata_value, env_value):
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


def _artifact_registry_to_data(
    artifacts: dict[str, ArtifactDescriptor],
) -> dict[str, dict[str, Any]]:
    return {
        artifact_ref: artifact_to_data(descriptor)
        for artifact_ref, descriptor in sorted(artifacts.items())
    }


def _copy_artifacts(
    *,
    dump_dir: Path,
    phase: str,
    artifacts: dict[str, ArtifactDescriptor],
) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    files_dir = dump_dir / "files" / phase
    for artifact_ref, descriptor in sorted(artifacts.items()):
        entry: dict[str, Any] = {
            "artifact_ref": artifact_ref,
            "source_uri": descriptor.uri,
            "phase": phase,
        }
        source_path = _file_path_from_uri(descriptor.uri)
        if source_path is None:
            entry["copied"] = False
            entry["reason"] = "unsupported_uri"
            copied.append(entry)
            continue
        if not source_path.is_file():
            entry["copied"] = False
            entry["reason"] = "missing_file"
            copied.append(entry)
            continue

        files_dir.mkdir(parents=True, exist_ok=True)
        target_path = files_dir / _dump_filename(artifact_ref, source_path)
        if target_path.exists():
            target_path.unlink()
        try:
            os.link(source_path, target_path)
            method = "hardlink"
        except OSError:
            shutil.copy2(source_path, target_path)
            method = "copy"

        entry["copied"] = True
        entry["method"] = method
        entry["dump_path"] = target_path.resolve().as_posix()
        entry["byte_size"] = target_path.stat().st_size
        copied.append(entry)
    return copied


def _file_path_from_uri(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(parsed.path)


def _dump_filename(artifact_ref: str, source_path: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", artifact_ref.removeprefix("artifact://"))
    name = name.strip("_") or "artifact"
    digest = hashlib.sha1(artifact_ref.encode("utf-8")).hexdigest()[:12]
    if len(name) > 80:
        name = name[-80:]
    name = f"{name}_{digest}"
    suffix = source_path.suffix or ".bin"
    if not name.endswith(suffix):
        name = f"{name}{suffix}"
    return name


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            redact_sensitive_data(payload),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
