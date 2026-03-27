from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping, Optional

from ..adapters.base import ModelAdapter
from ..adapters.callable import CallableModelAdapter
from ..adapters.http_api import HttpApiModelAdapter
from ..models.registry import ModelRegistry
from .spec import CustomAdapterType, CustomModelDefinition, custom_model_definition_from_data


class CustomModelLoader:
    """Load developer-supplied model manifests from disk into the registry."""

    def __init__(self, *, environ: Optional[Mapping[str, str]] = None) -> None:
        self._environ = dict(environ or os.environ)

    def load_directory(self, directory: str | Path) -> list[ModelAdapter]:
        root = Path(directory)
        if not root.exists():
            raise FileNotFoundError(f"Custom model directory does not exist: {root}")

        adapters: list[ModelAdapter] = []
        for path in sorted(root.rglob("*.json")):
            adapters.append(self.load_file(path))
        return adapters

    def load_file(self, path: str | Path) -> ModelAdapter:
        payload = json.loads(Path(path).read_text())
        definition = custom_model_definition_from_data(payload)
        return self._build_adapter(definition)

    def load_into_registry(self, registry: ModelRegistry, directory: str | Path) -> list[str]:
        manifests: list[str] = []
        for adapter in self.load_directory(directory):
            registry.register(adapter)
            manifests.append(adapter.manifest.model_id)
        return manifests

    def _build_adapter(self, definition: CustomModelDefinition) -> ModelAdapter:
        if definition.adapter_type is CustomAdapterType.PYTHON_CALLABLE:
            import_path = str(definition.adapter_config["import_path"])
            return CallableModelAdapter.from_import_path(
                definition.manifest,
                import_path=import_path,
            )

        if definition.adapter_type is CustomAdapterType.HTTP_API:
            endpoint_url = self._resolve_endpoint_url(definition.adapter_config)
            return HttpApiModelAdapter(
                definition.manifest,
                endpoint_url=endpoint_url,
                timeout_seconds=float(definition.adapter_config.get("timeout_seconds", 30.0)),
                headers={
                    str(key): str(value)
                    for key, value in dict(definition.adapter_config.get("headers", {})).items()
                },
                auth_header_name=_optional_string(
                    definition.adapter_config.get("auth_header_name")
                ),
                auth_header_prefix=_optional_string(
                    definition.adapter_config.get("auth_header_prefix")
                ),
                credential_alias=str(
                    definition.adapter_config.get("credential_alias", "primary_provider")
                ),
            )

        raise ValueError(f"Unsupported adapter_type: {definition.adapter_type.value}")

    def _resolve_endpoint_url(self, adapter_config: dict[str, object]) -> str:
        endpoint_url = _optional_string(adapter_config.get("endpoint_url"))
        if endpoint_url:
            return endpoint_url

        env_name = _optional_string(adapter_config.get("endpoint_url_env"))
        if not env_name:
            raise ValueError("http_api adapter requires endpoint_url or endpoint_url_env")

        try:
            return self._environ[env_name]
        except KeyError as exc:
            raise ValueError(
                f"Environment variable not set for endpoint_url_env: {env_name}"
            ) from exc


def load_custom_models_into_registry(
    registry: ModelRegistry,
    directory: str | Path,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> list[str]:
    loader = CustomModelLoader(environ=environ)
    return loader.load_into_registry(registry, directory)


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)
