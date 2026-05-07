from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .credentials import BillingMode, CredentialSource
from .stages import ExecutionMode


class StageKind(str, Enum):
    TEXT_DETECTION = "text_detection"
    OCR = "ocr"
    MASK_OR_ERASE_PLANNING = "mask_or_erase_planning"
    INPAINT = "inpaint"
    TRANSLATION = "translation"
    TYPESETTING = "typesetting"
    POSTPROCESS = "postprocess"


@dataclass
class ResourceProfile:
    cpu_threads: int = 1
    memory_mb: int = 0
    gpu_required: bool = False
    gpu_memory_mb: int = 0
    latency_tier: str = "default"


class ExecutionBackend(str, Enum):
    INPROCESS = "inprocess"
    HTTP_API = "http_api"
    SUBPROCESS_IPC = "subprocess_ipc"
    CONTAINER_WORKER = "container_worker"


@dataclass
class RuntimeMount:
    host_path: str
    container_path: str
    read_only: bool = False


@dataclass
class StageManifest:
    model_id: str
    adapter_id: str
    stage_kind: StageKind
    input_contract_version: str = "v1"
    output_contract_version: str = "v1"
    required_artifact_kinds: list[str] = field(default_factory=list)
    produced_artifact_kinds: list[str] = field(default_factory=list)
    supported_modes: list[ExecutionMode] = field(default_factory=lambda: [ExecutionMode.LOCAL, ExecutionMode.SAAS])
    allowed_credential_sources: list[CredentialSource] = field(default_factory=lambda: [CredentialSource.NONE])
    billing_modes: list[BillingMode] = field(default_factory=lambda: [BillingMode.NONE])
    resource_profile: ResourceProfile = field(default_factory=ResourceProfile)
    custom_model: bool = False
    priority: int = 0
    display_name: str = ""
    tags: list[str] = field(default_factory=list)
    execution_backend: ExecutionBackend = ExecutionBackend.INPROCESS
    runtime_family: str = "default"
    runtime_image: str = ""
    runtime_command: list[str] = field(default_factory=list)
    python_version: str = ""
    cuda_version: str = ""
    dependency_lock_ref: str = ""
    cache_mounts: list[RuntimeMount] = field(default_factory=list)
    network_policy: str = "default"

    def supports_mode(self, mode: ExecutionMode) -> bool:
        return mode in self.supported_modes
