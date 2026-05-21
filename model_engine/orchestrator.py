from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import logging
from typing import Any, Callable, Optional
from uuid import uuid4

from .contracts.artifacts import ArtifactDescriptor, ArtifactRegistry, InMemoryArtifactRegistry
from .contracts.document_ir import DocumentIR
from .contracts.patches import PatchOperation, apply_patches
from .contracts.stages import StageReport, StageRequest, StageResponse, StageRuntimeContext, StageStatus
from .credentials import CredentialResolver, DefaultCredentialResolver
from .logging_utils import log_event, log_exception
from .service_engine import ServiceEngineClient, UsageJobCreatePayload, UsageJobPayload
from .stage_artifact_dumps import StageArtifactDumper
from .stages.base import Stage

logger = logging.getLogger(__name__)

SERVICE_USAGE_ESTIMATED_UNITS = {
    "mask": 5,
    "inpaint": 20,
    "translate": 20,
}


@dataclass
class PipelineRunResult:
    job_id: str
    pipeline_id: str
    status: StageStatus
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    applied_patches: list[PatchOperation] = field(default_factory=list)
    stage_reports: list[StageReport] = field(default_factory=list)
    service_job_id: Optional[str] = None
    service_status: Optional[str] = None
    service_hold_status: Optional[str] = None
    service_hold_expires_at: Optional[datetime] = None
    service_requested_at: Optional[datetime] = None
    service_finished_at: Optional[datetime] = None


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
        stage_artifact_dumper = StageArtifactDumper.from_runtime_context(runtime_context)

        for index, stage in enumerate(stages, start=1):
            stage_run_id = f"{pipeline_id}:{stage.stage_name}:{index}"
            stage_config = stage.stage_config()
            request: StageRequest | None = None
            dump_dir = None
            log_event(
                logger,
                logging.INFO,
                "model_stage_started",
                job_id=job_id,
                pipeline_id=pipeline_id,
                stage_name=stage.stage_name,
                stage_run_id=stage_run_id,
                stage_index=index,
                stage_config_keys=sorted(stage_config),
            )

            try:
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
                dump_dir = stage_artifact_dumper.dump_input(request)
                response = stage.run(request)

                for descriptor in response.artifacts.values():
                    if descriptor.artifact_ref in self.artifact_registry.snapshot():
                        raise ValueError(
                            f"stage returned duplicate artifact_ref: {descriptor.artifact_ref}"
                        )
                    self.artifact_registry.register_artifact(descriptor)

                apply_patches(active_document, response.patches)
                applied_patches.extend(response.patches)
                stage_reports.append(response.stage_report)
                dump_dir = stage_artifact_dumper.dump_output(
                    request=request,
                    response=response,
                    artifacts_after=self.artifact_registry.snapshot(),
                    document_after=active_document,
                ) or dump_dir
            except Exception as exc:
                if request is not None:
                    dump_dir = stage_artifact_dumper.dump_exception(
                        request=request,
                        exc=exc,
                    ) or dump_dir
                log_exception(
                    logger,
                    "model_stage_exception",
                    job_id=job_id,
                    pipeline_id=pipeline_id,
                    stage_name=stage.stage_name,
                    stage_run_id=stage_run_id,
                    stage_index=index,
                    stage_artifact_dump_dir=str(dump_dir) if dump_dir else None,
                )
                raise

            log_event(
                logger,
                logging.INFO if response.status is StageStatus.SUCCEEDED else logging.ERROR,
                "model_stage_finished",
                job_id=job_id,
                pipeline_id=pipeline_id,
                stage_name=stage.stage_name,
                stage_run_id=stage_run_id,
                status=response.status.value,
                patch_count=len(response.patches),
                artifact_count=len(response.artifacts),
                warning_count=len(response.stage_report.warnings),
                error_code=response.stage_report.error_code,
                error_message=response.stage_report.error_message,
                stage_artifact_dump_dir=str(dump_dir) if dump_dir else None,
            )

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


class ServiceBackedPipelineRunner:
    def __init__(
        self,
        *,
        orchestrator: Optional[PipelineOrchestrator] = None,
        service_client_factory: Optional[Callable[[str], ServiceEngineClient]] = None,
    ) -> None:
        self._orchestrator = orchestrator or PipelineOrchestrator()
        self._service_client_factory = service_client_factory

    def run(
        self,
        *,
        document: DocumentIR,
        stages: list[Stage],
        runtime_context: StageRuntimeContext,
        initial_artifacts: Optional[dict[str, ArtifactDescriptor]] = None,
        job_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        request_ref: Optional[str] = None,
        operation_kind: Optional[str] = None,
        estimated_units: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> PipelineRunResult:
        if runtime_context.mode.value != "saas":
            return self._orchestrator.run(
                document=document,
                stages=stages,
                runtime_context=runtime_context,
                initial_artifacts=initial_artifacts,
                job_id=job_id,
                pipeline_id=pipeline_id,
            )

        service_session_key = _require_runtime_value(
            runtime_context.service_session_key,
            "runtime_context.service_session_key",
        )
        service_base_url = _require_runtime_value(
            runtime_context.service_base_url,
            "runtime_context.service_base_url",
        )
        resolved_request_ref = request_ref or runtime_context.service_request_ref or document.id
        if not resolved_request_ref:
            raise ValueError("request_ref is required for saas mode")

        resolved_operation_kind = operation_kind or _infer_service_operation_kind(stages)
        resolved_estimated_units = estimated_units or _estimated_units_for_operation_kind(
            resolved_operation_kind
        )
        resolved_idempotency_key = idempotency_key or _build_idempotency_key(
            document=document,
            stages=stages,
            runtime_context=runtime_context,
            operation_kind=resolved_operation_kind,
            request_ref=resolved_request_ref,
        )

        service_client = self._service_client_for_base_url(service_base_url)
        usage_job = service_client.create_usage_job(
            service_session_key,
            idempotency_key=resolved_idempotency_key,
            operation_kind=resolved_operation_kind,
            request_ref=resolved_request_ref,
            estimated_units=resolved_estimated_units,
        )

        try:
            result = self._orchestrator.run(
                document=document,
                stages=stages,
                runtime_context=runtime_context,
                initial_artifacts=initial_artifacts,
                job_id=job_id,
                pipeline_id=pipeline_id,
            )
        except Exception as exc:  # noqa: BLE001
            try:
                service_client.release_usage_job(
                    service_session_key,
                    job_id=usage_job.job_id,
                    error_code="pipeline_exception",
                    reason=str(exc),
                )
            except Exception as release_exc:  # noqa: BLE001
                release_exc.add_note("model_engine failed to release the reserved usage hold")
                raise release_exc from exc
            raise

        if result.status is StageStatus.FAILED:
            usage_result = service_client.release_usage_job(
                service_session_key,
                job_id=usage_job.job_id,
                error_code=_failure_error_code(result.stage_reports),
                reason=_failure_reason(result.stage_reports),
            )
            return _attach_service_usage(result, usage_job, usage_result)

        usage_result = service_client.capture_usage_job(
            service_session_key,
            job_id=usage_job.job_id,
        )
        return _attach_service_usage(result, usage_job, usage_result)

    def _service_client_for_base_url(self, base_url: str) -> ServiceEngineClient:
        if self._service_client_factory is not None:
            return self._service_client_factory(base_url)
        return ServiceEngineClient(base_url=base_url)


def _attach_service_usage(
    result: PipelineRunResult,
    usage_job: UsageJobCreatePayload,
    usage_result: UsageJobPayload,
) -> PipelineRunResult:
    result.service_job_id = usage_job.job_id
    result.service_status = usage_result.status
    result.service_hold_status = usage_result.hold_status
    result.service_hold_expires_at = usage_result.hold_expires_at
    result.service_requested_at = usage_result.requested_at
    result.service_finished_at = usage_result.finished_at
    return result


def _require_runtime_value(value: Optional[str], field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required for saas mode")
    return normalized


def _infer_service_operation_kind(stages: list[Stage]) -> str:
    stage_names = {stage.stage_name for stage in stages}
    if "inpaint" in stage_names:
        return "inpaint"
    if "translation" in stage_names or "ocr" in stage_names:
        return "translate"
    if "text_detection" in stage_names:
        # service_engine currently exposes `mask` for detection-class holds.
        return "mask"
    raise ValueError("unable to infer service operation kind from stages")


def _estimated_units_for_operation_kind(operation_kind: str) -> int:
    if operation_kind not in SERVICE_USAGE_ESTIMATED_UNITS:
        raise ValueError(f"unsupported service operation kind: {operation_kind}")
    return SERVICE_USAGE_ESTIMATED_UNITS[operation_kind]


def _build_idempotency_key(
    *,
    document: DocumentIR,
    stages: list[Stage],
    runtime_context: StageRuntimeContext,
    operation_kind: str,
    request_ref: str,
) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "document": {
                    "id": document.id,
                    "name": document.name,
                    "width": document.width,
                    "height": document.height,
                    "layer_ids": [layer.id for layer in document.layers],
                    "text_block_ids": [block.block_id for block in document.text_blocks],
                },
                "stages": [
                    {
                        "stage_name": stage.stage_name,
                        "stage_config": _normalize_for_fingerprint(stage.stage_config()),
                    }
                    for stage in stages
                ],
                "runtime": {
                    "target_regions": list(runtime_context.target_regions),
                    "selected_layer_ids": list(runtime_context.selected_layer_ids),
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"{operation_kind}:{request_ref}:{fingerprint}"


def _normalize_for_fingerprint(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalize_for_fingerprint(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalize_for_fingerprint(item) for item in value]
    return repr(value)


def _failure_error_code(stage_reports: list[StageReport]) -> str:
    for report in reversed(stage_reports):
        if report.status is StageStatus.FAILED and report.error_code:
            return report.error_code
    return "upstream_error"


def _failure_reason(stage_reports: list[StageReport]) -> str:
    for report in reversed(stage_reports):
        if report.status is StageStatus.FAILED:
            if report.error_message:
                return f"{report.stage_name}: {report.error_message}"
            return report.stage_name
    return "pipeline execution failed"
