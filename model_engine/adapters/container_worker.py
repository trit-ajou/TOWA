from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping, Optional
from urllib.parse import urlparse

from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.models import RuntimeMount, StageManifest
from ..contracts.stages import StageRequest, StageResponse
from ..ipc.process_stage import build_stage_env
from ..ipc.serde import stage_request_to_data, stage_response_from_data
from .base import ModelAdapter


class ContainerWorkerModelAdapter(ModelAdapter):
    """Run a stage handler inside an isolated container runtime."""

    def __init__(
        self,
        manifest: StageManifest,
        *,
        image: str,
        command: list[str],
        docker_executable: str = "docker",
        workspace_mount_path: str = "/workspace_out",
        path_mappings: Optional[list[RuntimeMount]] = None,
        environment: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not image:
            raise ValueError("container worker requires a runtime image")
        if not command:
            raise ValueError("container worker requires a runtime command")

        self._manifest = manifest
        self._image = image
        self._command = list(command)
        self._docker_executable = docker_executable
        self._workspace_mount_path = workspace_mount_path
        self._path_mappings = list(path_mappings or [])
        self._environment = {str(key): str(value) for key, value in dict(environment or {}).items()}

    @property
    def manifest(self) -> StageManifest:
        return self._manifest

    def run(self, request: StageRequest) -> StageResponse:
        container_request, mounts = _rewrite_request_for_container(
            request,
            workspace_mount_path=self._workspace_mount_path,
            path_mappings=self._path_mappings,
        )
        command = _build_docker_command(
            executable=self._docker_executable,
            image=self._image,
            runtime_command=self._command,
            mounts=mounts + list(self._manifest.cache_mounts),
            network_policy=self._manifest.network_policy,
        )
        payload = json.dumps(stage_request_to_data(container_request))
        env = os.environ.copy()
        env.update(self._environment)
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
            stderr = completed.stderr.strip() or "unknown container worker error"
            raise RuntimeError(
                "Container worker failed: "
                f"stage={request.stage_name} image={self._image} returncode={completed.returncode} stderr={stderr}"
            )

        stdout = completed.stdout.strip()
        if not stdout:
            raise RuntimeError(
                f"Container worker returned no stdout payload: stage={request.stage_name}"
            )

        try:
            response_payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Container worker returned invalid JSON: stage={request.stage_name}"
            ) from exc
        return stage_response_from_data(response_payload)


def default_container_worker_command(handler: str) -> list[str]:
    return [
        "python3",
        "-m",
        "model_engine.ipc.worker_entrypoint",
        "--handler",
        handler,
    ]


def _build_docker_command(
    *,
    executable: str,
    image: str,
    runtime_command: list[str],
    mounts: list[RuntimeMount],
    network_policy: str,
) -> list[str]:
    command = [executable, "run", "--rm", "-i"]
    if network_policy in {"disabled", "none"}:
        command.extend(["--network", "none"])

    for mount in _dedupe_mounts(mounts):
        spec = f"{mount.host_path}:{mount.container_path}"
        if mount.read_only:
            spec += ":ro"
        command.extend(["-v", spec])

    command.append(image)
    command.extend(runtime_command)
    return command


def _rewrite_request_for_container(
    request: StageRequest,
    *,
    workspace_mount_path: str,
    path_mappings: list[RuntimeMount],
) -> tuple[StageRequest, list[RuntimeMount]]:
    mounts = list(path_mappings)
    runtime_context = request.runtime_context
    rewritten_runtime = runtime_context

    workspace_host_path: Optional[Path] = None
    if runtime_context is not None:
        workspace_host_path = _file_uri_to_path(runtime_context.workspace_uri)
        if workspace_host_path is not None:
            mounts.append(
                RuntimeMount(
                    host_path=str(workspace_host_path),
                    container_path=workspace_mount_path,
                    read_only=False,
                )
            )
            rewritten_runtime = replace(
                runtime_context,
                workspace_uri=_path_to_file_uri(PurePosixPath(workspace_mount_path)),
            )

    runtime_mappings: list[RuntimeMount] = []
    if workspace_host_path is not None:
        runtime_mappings.append(
            RuntimeMount(
                host_path=str(workspace_host_path),
                container_path=workspace_mount_path,
                read_only=False,
            )
        )
    runtime_mappings.extend(path_mappings)

    rewritten_artifacts = {
        artifact_ref: _rewrite_artifact_uri(descriptor, runtime_mappings)
        for artifact_ref, descriptor in request.artifacts.items()
    }
    return replace(request, artifacts=rewritten_artifacts, runtime_context=rewritten_runtime), mounts


def _rewrite_artifact_uri(
    descriptor: ArtifactDescriptor,
    path_mappings: list[RuntimeMount],
) -> ArtifactDescriptor:
    rewritten_uri = _rewrite_file_uri(descriptor.uri, path_mappings)
    if rewritten_uri == descriptor.uri:
        return descriptor
    return replace(descriptor, uri=rewritten_uri)


def _rewrite_file_uri(uri: str, path_mappings: list[RuntimeMount]) -> str:
    host_path = _file_uri_to_path(uri)
    if host_path is None:
        return uri

    normalized_host = host_path.resolve(strict=False)
    for mapping in path_mappings:
        host_root = Path(mapping.host_path).resolve(strict=False)
        try:
            relative = normalized_host.relative_to(host_root)
        except ValueError:
            continue
        container_path = PurePosixPath(mapping.container_path) / PurePosixPath(relative.as_posix())
        return _path_to_file_uri(container_path)
    return uri


def _file_uri_to_path(uri: str) -> Optional[Path]:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(parsed.path)


def _path_to_file_uri(path: PurePosixPath) -> str:
    return f"file://{path.as_posix()}"


def _dedupe_mounts(mounts: list[RuntimeMount]) -> list[RuntimeMount]:
    deduped: list[RuntimeMount] = []
    seen: set[tuple[str, str, bool]] = set()
    for mount in mounts:
        key = (mount.host_path, mount.container_path, mount.read_only)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mount)
    return deduped
