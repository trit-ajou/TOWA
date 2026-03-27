from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..contracts.credentials import BillingMode, CredentialSource
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.stages import ExecutionMode


class CustomAdapterType(str, Enum):
    PYTHON_CALLABLE = "python_callable"
    HTTP_API = "http_api"


@dataclass
class CustomModelDefinition:
    schema_version: str
    adapter_type: CustomAdapterType
    manifest: StageManifest
    adapter_config: dict[str, Any] = field(default_factory=dict)


def custom_model_definition_from_data(payload: dict[str, Any]) -> CustomModelDefinition:
    schema_version = str(payload.get("schema_version", "v1"))
    if schema_version != "v1":
        raise ValueError(f"Unsupported custom model schema_version: {schema_version}")

    adapter_type = CustomAdapterType(str(payload["adapter_type"]))
    manifest = StageManifest(
        model_id=str(payload["model_id"]),
        adapter_id=str(payload["adapter_id"]),
        stage_kind=StageKind(str(payload["stage_kind"])),
        input_contract_version=str(payload.get("input_contract_version", "v1")),
        output_contract_version=str(payload.get("output_contract_version", "v1")),
        required_artifact_kinds=[str(item) for item in payload.get("required_artifact_kinds", [])],
        produced_artifact_kinds=[str(item) for item in payload.get("produced_artifact_kinds", [])],
        supported_modes=[
            ExecutionMode(str(item))
            for item in payload.get(
                "supported_modes",
                [ExecutionMode.LOCAL.value, ExecutionMode.SAAS.value],
            )
        ],
        allowed_credential_sources=[
            CredentialSource(str(item))
            for item in payload.get(
                "allowed_credential_sources",
                [CredentialSource.NONE.value],
            )
        ],
        billing_modes=[
            BillingMode(str(item))
            for item in payload.get(
                "billing_modes",
                [BillingMode.NONE.value],
            )
        ],
        resource_profile=ResourceProfile(
            cpu_threads=int(payload.get("resource_profile", {}).get("cpu_threads", 1)),
            memory_mb=int(payload.get("resource_profile", {}).get("memory_mb", 0)),
            gpu_required=bool(payload.get("resource_profile", {}).get("gpu_required", False)),
            gpu_memory_mb=int(payload.get("resource_profile", {}).get("gpu_memory_mb", 0)),
            latency_tier=str(payload.get("resource_profile", {}).get("latency_tier", "default")),
        ),
        custom_model=bool(payload.get("custom_model", True)),
        priority=int(payload.get("priority", 0)),
        display_name=str(payload.get("display_name", "")),
        tags=[str(item) for item in payload.get("tags", [])],
    )
    return CustomModelDefinition(
        schema_version=schema_version,
        adapter_type=adapter_type,
        manifest=manifest,
        adapter_config=dict(payload.get("adapter_config", {})),
    )
