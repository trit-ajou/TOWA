from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union

from .artifacts import ArtifactDescriptor
from .credentials import CredentialBinding, ResolvedCredential
from .document_ir import DocumentIR
from .patches import PatchOperation


class ExecutionMode(str, Enum):
    LOCAL = "local"
    SAAS = "saas"


class StageStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class StageRuntimeContext:
    mode: ExecutionMode
    workspace_uri: str
    requested_by: Optional[str] = None
    cancellation_token: Optional[str] = None
    target_regions: list[str] = field(default_factory=list)
    selected_layer_ids: list[str] = field(default_factory=list)
    session_provider_secrets: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    service_session_key: Optional[str] = None
    service_base_url: Optional[str] = None
    service_request_ref: Optional[str] = None


@dataclass
class StageReport:
    stage_name: str
    stage_run_id: str
    status: StageStatus
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Union[float, int, str]] = field(default_factory=dict)
    provider: Optional[CredentialBinding] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StageRequest:
    schema_version: str
    pipeline_id: str
    job_id: str
    stage_name: str
    stage_run_id: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    patches_applied: list[PatchOperation] = field(default_factory=list)
    stage_config: dict[str, object] = field(default_factory=dict)
    credential_bindings: dict[str, CredentialBinding] = field(default_factory=dict)
    resolved_credentials: dict[str, ResolvedCredential] = field(default_factory=dict)
    runtime_context: Optional[StageRuntimeContext] = None


@dataclass
class StageResponse:
    schema_version: str
    stage_name: str
    stage_run_id: str
    status: StageStatus
    patches: list[PatchOperation] = field(default_factory=list)
    artifacts: dict[str, ArtifactDescriptor] = field(default_factory=dict)
    stage_report: Optional[StageReport] = None

    def __post_init__(self) -> None:
        if self.stage_report is None:
            raise ValueError("stage_report is required")
        if self.stage_report.stage_name != self.stage_name:
            raise ValueError("stage_report.stage_name must match response stage_name")
        if self.stage_report.stage_run_id != self.stage_run_id:
            raise ValueError("stage_report.stage_run_id must match response stage_run_id")
