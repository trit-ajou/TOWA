from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Lock, Thread
import time
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

from .artifact_io import (
    JobArtifactDownload,
    UploadedBinaryPart,
    UnsupportedArtifactUriError,
    artifact_descriptor_to_api_data,
    artifact_descriptors_from_api_payload,
    file_artifact_path,
)
from ..config.runtime_config import load_runtime_config, runtime_config_value
from ..builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    MANGA_OCR_MODEL_ID,
    MINDLOGIC_IMAGE_MODEL,
    MINDLOGIC_INPAINT_MODEL_ID,
    NANOBANANA_INPAINT_MODEL_ID,
    OPENAI_COMPATIBLE_DEFAULT_BASE_URL,
    OPENAI_COMPATIBLE_DEFAULT_MODEL,
    OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
    VERTEX_TRANSLATION_MODEL_ID,
    register_craft_text_detection_model,
    register_manga_ocr_model,
    register_mindlogic_inpaint_model,
    register_nanobanana_inpaint_model,
    register_openai_compatible_translation_model,
    register_vertex_translation_model,
)
from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.document_ir import DocumentIR
from ..contracts.models import StageKind
from ..contracts.patches import PatchOperation
from ..contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageRuntimeContext,
    StageStatus,
)
from ..ipc.serde import document_from_data, document_to_data, patch_to_data, stage_report_to_data
from ..logging_utils import log_event, log_exception
from ..models import ModelRegistry
from ..orchestrator import PipelineOrchestrator
from ..stages import AdapterBackedStage, Stage, run_mask_or_erase_planning
from .service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)

if TYPE_CHECKING:
    from .schemas import ModelJobCreateRequest

logger = logging.getLogger(__name__)
RUNTIME_CONFIG = load_runtime_config()


class ModelJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


TERMINAL_JOB_STATUSES = frozenset(
    {
        ModelJobStatus.SUCCEEDED,
        ModelJobStatus.FAILED,
        ModelJobStatus.PARTIAL,
    }
)
SUPPORTED_OPERATIONS = frozenset({"detect", "inpaint", "translate"})
USAGE_ESTIMATE_UNITS = {
    "detect": 5,
    "inpaint": 20,
    "translate": 20,
}
SERVICE_USAGE_OPERATION_KIND = {
    "detect": "mask",
    "inpaint": "inpaint",
    "translate": "translate",
}
OPERATION_STAGE_NAMES = {
    "detect": ["text_detection", "ocr"],
    "inpaint": ["text_detection", "mask_or_erase_planning", "inpaint"],
    "translate": ["translation"],
}
OPERATION_META_KEYS = {
    "detect": "text_detection",
    "inpaint": "inpaint",
    "translate": "translation",
}


@dataclass
class ModelJobError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


@dataclass
class JobSubmission:
    schema_version: str
    idempotency_key: str
    operation_kind: str
    request_ref: str
    request_fingerprint: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext


@dataclass
class JobExecutionRequest:
    job_id: str
    pipeline_id: str
    schema_version: str
    operation_kind: str
    request_ref: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext


@dataclass
class JobExecutionResult:
    status: ModelJobStatus
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    document_patch: list[PatchOperation] = field(default_factory=list)
    stage_reports: list[StageReport] = field(default_factory=list)
    error: dict[str, Any] | None = None


@dataclass
class ModelJobRecord:
    job_id: str
    pipeline_id: str
    owner_scope: str
    idempotency_key: str
    request_fingerprint: str
    schema_version: str
    operation_kind: str
    request_ref: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext
    status: ModelJobStatus = ModelJobStatus.QUEUED
    document_patch: list[PatchOperation] = field(default_factory=list)
    stage_reports: list[StageReport] = field(default_factory=list)
    error: dict[str, Any] | None = None
    usage_job_id: str | None = None


class JobExecutor(ABC):
    @abstractmethod
    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        raise NotImplementedError


class PlaceholderJobExecutor(JobExecutor):
    def __init__(self, *, sleep_seconds: float = 0.05) -> None:
        self._sleep_seconds = sleep_seconds

    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        active_document = request.document.clone()
        stage_reports: list[StageReport] = []
        stage_names = OPERATION_STAGE_NAMES[request.operation_kind]

        for index, stage_name in enumerate(stage_names, start=1):
            if self._sleep_seconds:
                time.sleep(self._sleep_seconds)
            started_at = datetime.now(timezone.utc)
            finished_at = datetime.now(timezone.utc)
            stage_reports.append(
                StageReport(
                    stage_name=stage_name,
                    stage_run_id=f"{request.pipeline_id}:{stage_name}:{index}",
                    status=StageStatus.SUCCEEDED,
                    metrics={
                        "executor": "placeholder",
                        "operation_kind": request.operation_kind,
                        "request_ref": request.request_ref,
                    },
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )

        active_document.stage_meta[OPERATION_META_KEYS[request.operation_kind]] = {
            "status": "done",
            "executor": "placeholder",
            "job_id": request.job_id,
            "pipeline_id": request.pipeline_id,
            "stage_count": len(stage_reports),
        }
        document_patch = [
            PatchOperation(
                op="set_stage_meta",
                payload={
                    "key": OPERATION_META_KEYS[request.operation_kind],
                    "value": dict(active_document.stage_meta[OPERATION_META_KEYS[request.operation_kind]]),
                },
            )
        ]

        return JobExecutionResult(
            status=ModelJobStatus.SUCCEEDED,
            document=active_document,
            artifacts=dict(request.artifacts),
            document_patch=document_patch,
            stage_reports=stage_reports,
        )


class OrchestratedJobExecutor(JobExecutor):
    def __init__(
        self,
        *,
        registry: ModelRegistry | None = None,
        orchestrator: PipelineOrchestrator | None = None,
    ) -> None:
        self._registry = registry or _build_builtin_registry()
        self._orchestrator = orchestrator

    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        stages = _build_operation_stages(request, registry=self._registry)
        orchestrator = self._orchestrator or PipelineOrchestrator()
        result = orchestrator.run(
            document=request.document,
            stages=stages,
            runtime_context=request.runtime_context,
            initial_artifacts=request.artifacts,
            job_id=request.job_id,
            pipeline_id=request.pipeline_id,
        )
        return JobExecutionResult(
            status=_job_status_from_stage_status(result.status),
            document=result.document,
            artifacts=result.artifacts,
            document_patch=list(result.applied_patches),
            stage_reports=result.stage_reports,
            error=_error_from_stage_reports(result.stage_reports),
        )


class FunctionStage(Stage):
    """Wrap deterministic planner handlers so API jobs can compose them with model stages."""

    def __init__(
        self,
        stage_name: str,
        handler: Callable[[StageRequest], StageResponse],
        *,
        config: dict[str, object] | None = None,
    ) -> None:
        self._stage_name = stage_name
        self._handler = handler
        self._config = dict(config or {})

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        return dict(self._config)

    def run(self, request: StageRequest) -> StageResponse:
        return self._handler(request)


class ModelJobManager:
    def __init__(
        self,
        *,
        executor: JobExecutor | None = None,
        service_client_factory: Callable[[], ServiceEngineBridgeClient] | None = None,
    ) -> None:
        self._executor = executor or OrchestratedJobExecutor()
        self._service_client_factory = service_client_factory
        self._lock = Lock()
        self._jobs_by_id: dict[str, ModelJobRecord] = {}
        self._job_ids_by_idempotency: dict[tuple[str, str], str] = {}

    def create_job(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        self._validate_submission(submission, authorization=authorization)
        submission = self._normalized_submission(submission, authorization=authorization)
        owner_scope = self._owner_scope(submission, authorization=authorization)
        idempotency_scope = (owner_scope, submission.idempotency_key)

        with self._lock:
            existing_id = self._job_ids_by_idempotency.get(idempotency_scope)
            if existing_id is not None:
                existing = self._jobs_by_id[existing_id]
                self._assert_matching_idempotent_replay(existing, submission)
                status_code = 200 if existing.status in TERMINAL_JOB_STATUSES else 202
                log_event(
                    logger,
                    logging.INFO,
                    "model_job_idempotent_replay",
                    job_id=existing.job_id,
                    pipeline_id=existing.pipeline_id,
                    status=existing.status.value,
                    operation_kind=existing.operation_kind,
                    request_ref=existing.request_ref,
                    status_code=status_code,
                )
                return status_code, self._create_response(existing)

        usage_job_id = self._authorize_usage_hold(submission)
        record = ModelJobRecord(
            job_id=f"job_{uuid4().hex}",
            pipeline_id=f"pipe_{uuid4().hex}",
            owner_scope=owner_scope,
            idempotency_key=submission.idempotency_key,
            request_fingerprint=submission.request_fingerprint,
            schema_version=submission.schema_version,
            operation_kind=submission.operation_kind,
            request_ref=submission.request_ref,
            document=submission.document,
            artifacts=submission.artifacts,
            runtime_context=submission.runtime_context,
            usage_job_id=usage_job_id,
        )

        with self._lock:
            existing_id = self._job_ids_by_idempotency.get(idempotency_scope)
            if existing_id is not None:
                existing = self._jobs_by_id[existing_id]
                self._assert_matching_idempotent_replay(existing, submission)
                status_code = 200 if existing.status in TERMINAL_JOB_STATUSES else 202
                log_event(
                    logger,
                    logging.INFO,
                    "model_job_idempotent_replay",
                    job_id=existing.job_id,
                    pipeline_id=existing.pipeline_id,
                    status=existing.status.value,
                    operation_kind=existing.operation_kind,
                    request_ref=existing.request_ref,
                    status_code=status_code,
                )
                return status_code, self._create_response(existing)
            self._jobs_by_id[record.job_id] = record
            self._job_ids_by_idempotency[idempotency_scope] = record.job_id
            create_response = self._create_response(record)

        log_event(
            logger,
            logging.INFO,
            "model_job_accepted",
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            operation_kind=record.operation_kind,
            request_ref=record.request_ref,
            mode=record.runtime_context.mode.value,
            usage_job_id=record.usage_job_id,
        )
        Thread(
            target=self._run_job,
            args=(record.job_id,),
            daemon=True,
        ).start()
        return 202, create_response

    def get_job(self, job_id: str, *, authorization: str | None = None) -> dict[str, Any]:
        with self._lock:
            record = self._jobs_by_id.get(job_id)
            if record is None:
                raise ModelJobError(
                    status_code=404,
                    code="model_job_not_found",
                    message=f"Unknown job_id: {job_id}",
                )
            self._assert_job_read_access(record, authorization=authorization)
            return self._detail_response(record)

    def get_artifact(
        self,
        job_id: str,
        *,
        artifact_ref: str,
        authorization: str | None = None,
    ) -> JobArtifactDownload:
        with self._lock:
            record = self._jobs_by_id.get(job_id)
            if record is None:
                raise ModelJobError(
                    status_code=404,
                    code="model_job_not_found",
                    message=f"Unknown job_id: {job_id}",
                )
            self._assert_job_read_access(record, authorization=authorization)
            descriptor = record.artifacts.get(artifact_ref)
            if descriptor is None:
                raise ModelJobError(
                    status_code=404,
                    code="model_artifact_not_found",
                    message=f"Unknown artifact_ref for job {job_id}: {artifact_ref}",
                    details={"artifact_ref": artifact_ref},
                )

        try:
            artifact_path = file_artifact_path(descriptor)
        except UnsupportedArtifactUriError as exc:
            raise ModelJobError(
                status_code=422,
                code="model_artifact_unsupported_uri",
                message=exc.message,
                details={"artifact_ref": exc.artifact_ref, "uri": exc.uri},
            ) from exc
        if not artifact_path.is_file():
            raise ModelJobError(
                status_code=404,
                code="model_artifact_not_found",
                message=f"Artifact binary does not exist for ref: {artifact_ref}",
                details={"artifact_ref": artifact_ref},
            )
        return JobArtifactDownload(descriptor=descriptor, path=artifact_path)

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs_by_id[job_id]
            record.status = ModelJobStatus.RUNNING

        log_event(
            logger,
            logging.INFO,
            "model_job_started",
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            operation_kind=record.operation_kind,
            request_ref=record.request_ref,
            mode=record.runtime_context.mode.value,
            usage_job_id=record.usage_job_id,
        )
        request = JobExecutionRequest(
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            schema_version=record.schema_version,
            operation_kind=record.operation_kind,
            request_ref=record.request_ref,
            document=record.document.clone(),
            artifacts=dict(record.artifacts),
            runtime_context=_runtime_context_for_job_execution(record),
        )

        try:
            result = self._executor.execute(request)
        except Exception as exc:  # pragma: no cover - defensive path exercised in tests via custom executor
            log_exception(
                logger,
                "model_job_exception",
                job_id=record.job_id,
                pipeline_id=record.pipeline_id,
                operation_kind=record.operation_kind,
                request_ref=record.request_ref,
                exception_type=type(exc).__name__,
            )
            result = JobExecutionResult(
                status=ModelJobStatus.FAILED,
                document=record.document.clone(),
                artifacts=dict(record.artifacts),
                document_patch=[],
                error=_error_payload(
                    code="model_stage_failed",
                    message=str(exc),
                    details={"operation_kind": record.operation_kind},
                ),
            )

        billing_error = self._finalize_billing(
            record=record,
            result=result,
        )
        if billing_error is not None:
            log_event(
                logger,
                logging.ERROR,
                "model_job_billing_finalization_failed",
                job_id=record.job_id,
                pipeline_id=record.pipeline_id,
                operation_kind=record.operation_kind,
                request_ref=record.request_ref,
                error=billing_error,
            )
            result.error = _merge_error_payload(result.error, billing_error)
            if result.status is ModelJobStatus.SUCCEEDED:
                result.status = ModelJobStatus.PARTIAL

        with self._lock:
            stored = self._jobs_by_id[job_id]
            stored.status = result.status
            stored.document = result.document
            stored.artifacts = result.artifacts
            stored.document_patch = result.document_patch
            stored.stage_reports = result.stage_reports
            stored.error = result.error

        log_event(
            logger,
            logging.INFO if result.status is ModelJobStatus.SUCCEEDED else logging.ERROR,
            "model_job_finished",
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            operation_kind=record.operation_kind,
            request_ref=record.request_ref,
            status=result.status.value,
            stage_count=len(result.stage_reports),
            patch_count=len(result.document_patch),
            artifact_count=len(result.artifacts),
            error=result.error,
        )

    def _finalize_billing(
        self,
        *,
        record: ModelJobRecord,
        result: JobExecutionResult,
    ) -> dict[str, Any] | None:
        if record.runtime_context.mode is not ExecutionMode.SAAS or record.usage_job_id is None:
            return None

        client = self._require_service_client()
        authorization = _service_authorization(record.runtime_context)
        try:
            if result.status in {ModelJobStatus.SUCCEEDED, ModelJobStatus.PARTIAL}:
                client.post(
                    f"/usage/jobs/{record.usage_job_id}/capture",
                    body={},
                    authorization=authorization,
                )
            else:
                client.post(
                    f"/usage/jobs/{record.usage_job_id}/release",
                    body={
                        "error_code": result.error["code"] if result.error else "model_job_failed",
                        "reason": result.error["message"] if result.error else "model job failed",
                    },
                    authorization=authorization,
                )
        except ServiceEngineHTTPError as exc:
            return _error_payload(
                code="billing_sync_failed",
                message="service engine billing finalization failed",
                retryable=exc.status_code >= 500,
                details={
                    "status_code": exc.status_code,
                    "payload": exc.payload,
                },
            )
        except ServiceEngineUnavailableError as exc:
            return _error_payload(
                code="service_engine_unreachable",
                message=str(exc),
                retryable=True,
            )

        return None

    def _validate_submission(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None,
    ) -> None:
        if submission.schema_version != "v1":
            raise ModelJobError(
                status_code=422,
                code="model_validation_error",
                message=f"Unsupported schema_version: {submission.schema_version}",
            )
        if submission.operation_kind not in SUPPORTED_OPERATIONS:
            raise ModelJobError(
                status_code=422,
                code="model_validation_error",
                message=f"Unsupported operation_kind: {submission.operation_kind}",
            )
        if submission.runtime_context.mode is ExecutionMode.SAAS and not authorization:
            raise ModelJobError(
                status_code=401,
                code="session_key_required",
                message="Authorization header is required for saas mode",
            )

    def _assert_job_read_access(
        self,
        record: ModelJobRecord,
        *,
        authorization: str | None,
    ) -> None:
        if record.runtime_context.mode is not ExecutionMode.SAAS:
            return
        if not authorization:
            raise ModelJobError(
                status_code=401,
                code="session_key_required",
                message="Authorization header is required for saas mode",
            )
        if record.owner_scope != _saas_owner_scope(authorization):
            raise ModelJobError(
                status_code=404,
                code="model_job_not_found",
                message=f"Unknown job_id: {record.job_id}",
            )

    def _assert_matching_idempotent_replay(
        self,
        record: ModelJobRecord,
        submission: JobSubmission,
    ) -> None:
        if record.request_fingerprint == submission.request_fingerprint:
            return
        raise ModelJobError(
            status_code=409,
            code="model_job_conflict",
            message="idempotency_key cannot be reused with a different request payload",
            details={"reason": "idempotency_payload_mismatch"},
        )

    def _owner_scope(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None,
    ) -> str:
        if submission.runtime_context.mode is ExecutionMode.SAAS:
            if not authorization:
                raise ModelJobError(
                    status_code=401,
                    code="session_key_required",
                    message="Authorization header is required for saas mode",
                )
            return _saas_owner_scope(authorization)
        requested_by = (submission.runtime_context.requested_by or "").strip()
        return f"local:{requested_by}" if requested_by else "local"

    def _normalized_submission(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None,
    ) -> JobSubmission:
        if submission.runtime_context.mode is not ExecutionMode.SAAS:
            return submission

        service_session_key = _service_session_key_from_authorization(authorization)
        runtime_context = submission.runtime_context
        runtime_context.service_session_key = service_session_key
        return submission

    def _authorize_usage_hold(
        self,
        submission: JobSubmission,
    ) -> str | None:
        if submission.runtime_context.mode is not ExecutionMode.SAAS:
            return None

        client = self._require_service_client()
        authorization = _service_authorization(submission.runtime_context)
        payload = client.post(
            "/usage/jobs",
            body={
                "idempotency_key": submission.idempotency_key,
                "operation_kind": SERVICE_USAGE_OPERATION_KIND[submission.operation_kind],
                "request_ref": submission.request_ref,
                "estimated_units": USAGE_ESTIMATE_UNITS[submission.operation_kind],
            },
            authorization=authorization,
        )
        log_event(
            logger,
            logging.INFO,
            "model_job_usage_hold_authorized",
            operation_kind=submission.operation_kind,
            request_ref=submission.request_ref,
            usage_job_id=str(payload["job_id"]),
        )
        return str(payload["job_id"])

    def _require_service_client(self) -> ServiceEngineBridgeClient:
        if self._service_client_factory is None:
            raise ModelJobError(
                status_code=502,
                code="service_engine_unreachable",
                message="service bridge is not configured",
                retryable=True,
            )
        return self._service_client_factory()

    @staticmethod
    def _create_response(record: ModelJobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "pipeline_id": record.pipeline_id,
            "status": record.status.value,
            "operation_kind": record.operation_kind,
            "request_ref": record.request_ref,
            "status_url": f"/v1/jobs/{record.job_id}",
        }

    @staticmethod
    def _detail_response(record: ModelJobRecord) -> dict[str, Any]:
        return {
            "job_id": record.job_id,
            "pipeline_id": record.pipeline_id,
            "status": record.status.value,
            "operation_kind": record.operation_kind,
            "request_ref": record.request_ref,
            "document": document_to_data(record.document),
            "document_patch": {"patches": [patch_to_data(patch) for patch in record.document_patch]},
            "artifacts": {
                artifact_ref: artifact_descriptor_to_api_data(descriptor)
                for artifact_ref, descriptor in record.artifacts.items()
            },
            "stage_reports": [stage_report_to_data(report) for report in record.stage_reports],
            "error": record.error,
        }


def submission_from_api_payload(payload: "ModelJobCreateRequest") -> JobSubmission:
    runtime_context = runtime_context_from_api_data(payload.runtime_context)
    normalized_artifacts = artifact_descriptors_from_api_payload(payload.artifacts)
    return JobSubmission(
        schema_version=payload.schema_version,
        idempotency_key=payload.idempotency_key,
        operation_kind=payload.operation_kind,
        request_ref=payload.request_ref,
        request_fingerprint=_request_fingerprint(
            {
                "schema_version": payload.schema_version,
                "operation_kind": payload.operation_kind,
                "request_ref": payload.request_ref,
                "document": payload.document,
                "artifacts": payload.artifacts,
                "runtime_context": payload.runtime_context,
            }
        ),
        document=document_from_data(payload.document),
        artifacts=normalized_artifacts,
        runtime_context=runtime_context,
    )


def submission_from_multipart_payload(
    payload: "ModelJobCreateRequest",
    *,
    primary_bitmap: UploadedBinaryPart,
) -> JobSubmission:
    runtime_context = runtime_context_from_api_data(payload.runtime_context)
    upload_checksum = f"sha256:{hashlib.sha256(primary_bitmap.content).hexdigest()}"
    normalized_artifacts = artifact_descriptors_from_api_payload(
        payload.artifacts,
        primary_bitmap=primary_bitmap,
        primary_bitmap_checksum=upload_checksum,
    )
    return JobSubmission(
        schema_version=payload.schema_version,
        idempotency_key=payload.idempotency_key,
        operation_kind=payload.operation_kind,
        request_ref=payload.request_ref,
        request_fingerprint=_request_fingerprint(
            {
                "schema_version": payload.schema_version,
                "operation_kind": payload.operation_kind,
                "request_ref": payload.request_ref,
                "document": payload.document,
                "artifacts": payload.artifacts,
                "runtime_context": payload.runtime_context,
                "uploads": {
                    "primary_bitmap": {
                        "sha256": upload_checksum,
                        "media_type": primary_bitmap.media_type,
                    }
                },
            }
        ),
        document=document_from_data(payload.document),
        artifacts=normalized_artifacts,
        runtime_context=runtime_context,
    )


def runtime_context_from_api_data(payload: dict[str, Any]) -> StageRuntimeContext:
    return StageRuntimeContext(
        mode=ExecutionMode(payload["mode"]),
        workspace_uri=str(payload["workspace_uri"]),
        requested_by=payload.get("requested_by"),
        cancellation_token=payload.get("cancellation_token"),
        target_regions=list(payload.get("target_regions", [])),
        selected_layer_ids=list(payload.get("selected_layer_ids", [])),
        session_provider_secrets=dict(payload.get("session_provider_secrets", {})),
        metadata=dict(payload.get("metadata", {})),
        service_session_key=payload.get("service_session_key"),
        service_base_url=payload.get("service_base_url"),
        service_request_ref=payload.get("service_request_ref"),
    )


def _error_payload(
    *,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "details": details,
    }


def _merge_error_payload(
    primary: dict[str, Any] | None,
    secondary: dict[str, Any],
) -> dict[str, Any]:
    if primary is None:
        return secondary
    details = dict(primary.get("details") or {})
    details["billing"] = secondary
    return {
        "code": primary["code"],
        "message": primary["message"],
        "retryable": bool(primary.get("retryable", False)),
        "details": details,
    }


def _request_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _saas_owner_scope(authorization: str) -> str:
    normalized = authorization.strip()
    return f"saas:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _service_session_key_from_authorization(authorization: str | None) -> str:
    normalized = (authorization or "").strip()
    if not normalized:
        raise ModelJobError(
            status_code=401,
            code="session_key_required",
            message="Authorization header is required for saas mode",
        )

    scheme, _, token = normalized.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ModelJobError(
            status_code=401,
            code="session_key_required",
            message="Authorization header is required for saas mode",
        )
    return token.strip()


def _service_authorization(runtime_context: StageRuntimeContext) -> str:
    session_key = (runtime_context.service_session_key or "").strip()
    if not session_key:
        raise ValueError("runtime_context.service_session_key is required for saas mode")
    return f"Bearer {session_key}"


def _runtime_context_for_job_execution(record: ModelJobRecord) -> StageRuntimeContext:
    parsed = urlparse(record.runtime_context.workspace_uri)
    if parsed.scheme == "file":
        return record.runtime_context

    workspace_path = _server_job_workspace_path(record.job_id)
    metadata = dict(record.runtime_context.metadata)
    metadata.setdefault("client_workspace_uri", record.runtime_context.workspace_uri)
    return replace(
        record.runtime_context,
        workspace_uri=workspace_path.as_uri(),
        metadata=metadata,
    )


def _server_job_workspace_path(job_id: str) -> Path:
    root = Path(os.environ.get("TOWA_MODEL_ENGINE_WORKSPACE_ROOT", "/tmp/towa_model_engine/workspaces"))
    path = root / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _build_builtin_registry() -> ModelRegistry:
    registry = ModelRegistry()
    register_craft_text_detection_model(registry)
    register_manga_ocr_model(registry)
    register_nanobanana_inpaint_model(registry)
    register_mindlogic_inpaint_model(registry)
    register_openai_compatible_translation_model(registry)
    register_vertex_translation_model(registry)
    return registry


def _build_operation_stages(
    request: JobExecutionRequest,
    *,
    registry: ModelRegistry,
) -> list[Stage]:
    if request.operation_kind == "detect":
        input_artifact_ref = _resolve_primary_bitmap_artifact_ref(request.artifacts)
        common_detection_config = _common_detection_config(input_artifact_ref)
        return [
            AdapterBackedStage(
                "text_detection",
                stage_kind=StageKind.TEXT_DETECTION,
                registry=registry,
                preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
                config=common_detection_config,
            ),
            AdapterBackedStage(
                "ocr",
                stage_kind=StageKind.OCR,
                registry=registry,
                preferred_model_id=MANGA_OCR_MODEL_ID,
                config=_manga_ocr_stage_config(input_artifact_ref),
            ),
        ]

    if request.operation_kind == "translate":
        return [
            AdapterBackedStage(
                "translation",
                stage_kind=StageKind.TRANSLATION,
                registry=registry,
                preferred_model_id=_translation_model_id_from_runtime(request.runtime_context),
                config={
                    **_translation_provider_config_from_runtime(request.runtime_context),
                    "source_language": "Japanese",
                    "target_language": "Korean",
                },
            ),
        ]

    if request.operation_kind == "inpaint":
        input_artifact_ref = _resolve_primary_bitmap_artifact_ref(request.artifacts)
        common_detection_config = _common_detection_config(input_artifact_ref)
        return [
            AdapterBackedStage(
                "text_detection",
                stage_kind=StageKind.TEXT_DETECTION,
                registry=registry,
                preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
                config=common_detection_config,
            ),
            FunctionStage(
                "mask_or_erase_planning",
                run_mask_or_erase_planning,
                config={
                    "input_artifact_ref": input_artifact_ref,
                    "padding": 12,
                    "target_layer_id": "layer_inpainting",
                },
            ),
            AdapterBackedStage(
                "inpaint",
                stage_kind=StageKind.INPAINT,
                registry=registry,
                preferred_model_id=_inpaint_model_id_from_runtime(request.runtime_context),
                config={
                    "input_artifact_ref": input_artifact_ref,
                    "target_layer_id": "layer_inpainting",
                    "output_mask_mode": "mask_artifact",
                    "output_mask_dilate_radius": 2,
                    **_inpaint_provider_config_from_runtime(request.runtime_context),
                },
            ),
        ]

    raise ValueError(f"Unsupported operation_kind: {request.operation_kind}")


def _common_detection_config(input_artifact_ref: str) -> dict[str, object]:
    return {
        "input_artifact_ref": input_artifact_ref,
        "text_threshold": 0.7,
        "link_threshold": 0.4,
        "low_text": 0.4,
    }


def _manga_ocr_stage_config(input_artifact_ref: str) -> dict[str, object]:
    return {
        "input_artifact_ref": input_artifact_ref,
        "writing_mode_hint": "vertical",
        "region_padding": 12,
        "merge_regions": True,
        "merge_gap_px": 24,
        "merge_min_overlap_ratio": 0.25,
        "reading_order_mode": "vertical_rtl",
        "min_ocr_region_area_px": 160,
        "min_ocr_region_area_ratio": 0.00015,
        "max_text_density_per_1000_px2": 1.5,
        "small_region_long_text_area_px": 6000,
        "small_region_long_text_area_ratio": 0.004,
        "small_region_long_text_min_chars": 16,
        "hallucination_action": "mark",
    }


def _resolve_primary_bitmap_artifact_ref(artifacts: dict[str, ArtifactDescriptor]) -> str:
    for artifact_ref, descriptor in artifacts.items():
        if descriptor.kind == "bitmap":
            return artifact_ref
    raise ValueError("Model jobs require at least one bitmap artifact")


def _translation_model_id_from_runtime(runtime_context: StageRuntimeContext) -> str:
    backend = (
        runtime_context.metadata.get("translation_backend")
        or runtime_config_value(RUNTIME_CONFIG, "TOWA_TRANSLATION_BACKEND")
    )
    if backend == "vertex":
        return VERTEX_TRANSLATION_MODEL_ID
    return OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID


def _inpaint_model_id_from_runtime(runtime_context: StageRuntimeContext) -> str:
    provider = _inpaint_provider_from_runtime(runtime_context)
    if provider == "mindlogic":
        return MINDLOGIC_INPAINT_MODEL_ID
    return NANOBANANA_INPAINT_MODEL_ID


def _inpaint_provider_config_from_runtime(
    runtime_context: StageRuntimeContext,
) -> dict[str, object]:
    provider = _inpaint_provider_from_runtime(runtime_context)
    if provider == "mindlogic":
        return {
            "provider": "mindlogic",
            "model_name": str(
                runtime_context.metadata.get("inpaint_model_name")
                or runtime_config_value(RUNTIME_CONFIG, "TOWA_INPAINT_MODEL_NAME")
                or MINDLOGIC_IMAGE_MODEL
            ),
        }
    return {"provider": "nanobanana"}


def _inpaint_provider_from_runtime(runtime_context: StageRuntimeContext) -> str:
    return str(
        runtime_context.metadata.get("inpaint_provider")
        or runtime_config_value(
            RUNTIME_CONFIG,
            "TOWA_INPAINT_PROVIDER",
            aliases=("inpaint_provider", "inpaint.provider"),
        )
        or "nanobanana"
    )


def _translation_provider_config_from_runtime(
    runtime_context: StageRuntimeContext,
) -> dict[str, object]:
    backend = (
        runtime_context.metadata.get("translation_backend")
        or runtime_config_value(RUNTIME_CONFIG, "TOWA_TRANSLATION_BACKEND")
    )
    if backend == "vertex":
        return {
            "provider": "translation_provider",
            "model_name": str(
                runtime_context.metadata.get("translation_model_name")
                or runtime_config_value(RUNTIME_CONFIG, "TOWA_TRANSLATION_MODEL_NAME")
                or "gemini-3.1-flash-lite-preview"
            ),
        }

    api_key = str(
        runtime_context.metadata.get("openai_compatible_api_key")
        or runtime_config_value(
            RUNTIME_CONFIG,
            "TOWA_OPENAI_COMPATIBLE_API_KEY",
            aliases=("openai_compatible_api_key", "translation.openai_compatible_api_key"),
        )
        or ""
    )
    config: dict[str, object] = {
        "base_url": str(
            runtime_context.metadata.get("openai_compatible_base_url")
            or runtime_config_value(RUNTIME_CONFIG, "TOWA_OPENAI_COMPATIBLE_BASE_URL")
            or OPENAI_COMPATIBLE_DEFAULT_BASE_URL
        ),
        "model_name": str(
            runtime_context.metadata.get("translation_model_name")
            or runtime_config_value(RUNTIME_CONFIG, "TOWA_TRANSLATION_MODEL_NAME")
            or OPENAI_COMPATIBLE_DEFAULT_MODEL
        ),
    }
    if api_key:
        config["api_key"] = api_key
    if "openai_compatible" in runtime_context.session_provider_secrets:
        config["provider"] = "openai_compatible"
    else:
        config["skip_provider_resolution"] = True
    return config


def _job_status_from_stage_status(status: StageStatus) -> ModelJobStatus:
    if status is StageStatus.SUCCEEDED:
        return ModelJobStatus.SUCCEEDED
    if status is StageStatus.PARTIAL:
        return ModelJobStatus.PARTIAL
    return ModelJobStatus.FAILED


def _error_from_stage_reports(stage_reports: list[StageReport]) -> dict[str, Any] | None:
    for report in reversed(stage_reports):
        if report.status is StageStatus.FAILED:
            return _error_payload(
                code=report.error_code or "model_stage_failed",
                message=report.error_message or f"{report.stage_name} failed",
                details={"stage_name": report.stage_name},
            )
    return None
