from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from .contracts.artifacts import ArtifactDescriptor, ArtifactRegistry, InMemoryArtifactRegistry
from .contracts.document_ir import DocumentIR
from .contracts.patches import PatchOperation, apply_patches
from .contracts.stages import StageReport, StageRequest, StageResponse, StageRuntimeContext, StageStatus
from .credentials import CredentialResolver, DefaultCredentialResolver
from .stages.base import Stage


@dataclass
class PipelineRunResult:
    job_id: str
    pipeline_id: str
    status: StageStatus
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    applied_patches: list[PatchOperation] = field(default_factory=list)
    stage_reports: list[StageReport] = field(default_factory=list)


class PipelineOrchestrator:
    def __init__(
        self,
        artifact_registry: Optional[ArtifactRegistry] = None,
        credential_resolver: Optional[CredentialResolver] = None,
    ) -> None:
        self.artifact_registry = artifact_registry or InMemoryArtifactRegistry()
        self.credential_resolver = credential_resolver or DefaultCredentialResolver()

    def run(
        self,
        *,
        document: DocumentIR,
        stages: list[Stage],
        runtime_context: StageRuntimeContext,
        initial_artifacts: Optional[dict[str, ArtifactDescriptor]] = None,
        job_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> PipelineRunResult:
        active_document = document.clone()
        job_id = job_id or f"job_{uuid4().hex}"
        pipeline_id = pipeline_id or f"pipe_{uuid4().hex}"
        applied_patches: list[PatchOperation] = []
        stage_reports: list[StageReport] = []

        for descriptor in (initial_artifacts or {}).values():
            if descriptor.artifact_ref not in self.artifact_registry.snapshot():
                self.artifact_registry.register_artifact(descriptor)

        final_status = StageStatus.SUCCEEDED

        for index, stage in enumerate(stages, start=1):
            stage_run_id = f"{pipeline_id}:{stage.stage_name}:{index}"
            stage_config = stage.stage_config()
            credential_bindings, resolved_credentials = self.credential_resolver.resolve_for_stage(
                stage_name=stage.stage_name,
                runtime_context=runtime_context,
                stage_config=stage_config,
            )
            request = StageRequest(
                schema_version="v1",
                pipeline_id=pipeline_id,
                job_id=job_id,
                stage_name=stage.stage_name,
                stage_run_id=stage_run_id,
                document=active_document.clone(),
                artifacts=self.artifact_registry.snapshot(),
                patches_applied=list(applied_patches),
                stage_config=stage_config,
                credential_bindings=credential_bindings,
                resolved_credentials=resolved_credentials,
                runtime_context=runtime_context,
            )
            response = stage.run(request)

            for descriptor in response.artifacts.values():
                if descriptor.artifact_ref in self.artifact_registry.snapshot():
                    raise ValueError(f"stage returned duplicate artifact_ref: {descriptor.artifact_ref}")
                self.artifact_registry.register_artifact(descriptor)

            apply_patches(active_document, response.patches)
            applied_patches.extend(response.patches)
            stage_reports.append(response.stage_report)

            if response.status is StageStatus.FAILED:
                final_status = StageStatus.FAILED
                break
            if response.status is StageStatus.PARTIAL and final_status is not StageStatus.FAILED:
                final_status = StageStatus.PARTIAL

        return PipelineRunResult(
            job_id=job_id,
            pipeline_id=pipeline_id,
            status=final_status,
            document=active_document,
            artifacts=self.artifact_registry.snapshot(),
            applied_patches=applied_patches,
            stage_reports=stage_reports,
        )
