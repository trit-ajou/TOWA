from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..adapters.base import ModelAdapter
from ..contracts.credentials import CredentialSource
from ..contracts.models import StageKind, StageManifest
from ..contracts.stages import StageRequest


class ModelSelectionError(RuntimeError):
    """Raised when no compatible adapter can satisfy a stage request."""


@dataclass
class ModelSelection:
    adapter: ModelAdapter
    manifest: StageManifest
    reason: str


class ModelRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter: ModelAdapter) -> None:
        model_id = adapter.manifest.model_id
        if model_id in self._adapters:
            raise ValueError(f"Duplicate model_id registration: {model_id}")
        self._adapters[model_id] = adapter

    def get(self, model_id: str) -> ModelAdapter:
        try:
            return self._adapters[model_id]
        except KeyError as exc:
            raise ModelSelectionError(f"Unknown model_id: {model_id}") from exc

    def list_manifests(self, stage_kind: Optional[StageKind] = None) -> list[StageManifest]:
        manifests = [adapter.manifest for adapter in self._adapters.values()]
        if stage_kind is None:
            return manifests
        return [manifest for manifest in manifests if manifest.stage_kind is stage_kind]

    def load_custom_model_directory(
        self,
        directory: str,
        *,
        environ: Optional[dict[str, str]] = None,
    ) -> list[str]:
        # The import stays local so the registry core does not depend on loader wiring.
        from ..custom_models.loader import load_custom_models_into_registry

        return load_custom_models_into_registry(self, directory, environ=environ)

    def select_for_request(
        self,
        *,
        stage_kind: StageKind,
        request: StageRequest,
        preferred_model_id: Optional[str] = None,
    ) -> ModelSelection:
        if preferred_model_id:
            adapter = self.get(preferred_model_id)
            manifest = adapter.manifest
            if not _is_manifest_compatible(manifest, request, stage_kind):
                raise ModelSelectionError(
                    f"Preferred model is not compatible: model_id={preferred_model_id}"
                )
            return ModelSelection(
                adapter=adapter,
                manifest=manifest,
                reason=f"preferred_model_id={preferred_model_id}",
            )

        candidates = [
            adapter
            for adapter in self._adapters.values()
            if _is_manifest_compatible(adapter.manifest, request, stage_kind)
        ]
        if not candidates:
            raise ModelSelectionError(
                f"No compatible model adapter for stage_kind={stage_kind.value}"
            )

        candidates.sort(
            key=lambda adapter: (
                adapter.manifest.priority,
                1 if adapter.manifest.custom_model else 0,
                adapter.manifest.model_id,
            ),
            reverse=True,
        )
        selected = candidates[0]
        return ModelSelection(
            adapter=selected,
            manifest=selected.manifest,
            reason="highest_priority_compatible_manifest",
        )


def _is_manifest_compatible(
    manifest: StageManifest,
    request: StageRequest,
    stage_kind: StageKind,
) -> bool:
    if manifest.stage_kind is not stage_kind:
        return False
    if manifest.input_contract_version != request.schema_version:
        return False
    if not request.runtime_context or not manifest.supports_mode(request.runtime_context.mode):
        return False
    if not _has_required_artifact_kinds(manifest, request):
        return False
    if not _credential_source_allowed(manifest, request):
        return False
    return True


def _has_required_artifact_kinds(manifest: StageManifest, request: StageRequest) -> bool:
    available_kinds = {descriptor.kind for descriptor in request.artifacts.values()}
    return all(kind in available_kinds for kind in manifest.required_artifact_kinds)


def _credential_source_allowed(manifest: StageManifest, request: StageRequest) -> bool:
    if not manifest.allowed_credential_sources:
        return True

    primary = request.credential_bindings.get("primary_provider")
    if primary is None:
        return CredentialSource.NONE in manifest.allowed_credential_sources
    return primary.credential_source in manifest.allowed_credential_sources
