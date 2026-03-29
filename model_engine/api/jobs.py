from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock, Thread
import time
from typing import Any, Callable, Optional
from uuid import uuid4

from ..contracts.artifacts import ArtifactDescriptor, ArtifactStatus
from ..contracts.document_ir import DocumentIR
from ..contracts.stages import ExecutionMode, StageReport, StageRuntimeContext, StageStatus
from ..ipc.serde import document_from_data, document_to_data, stage_report_to_data
from .schemas import ModelJobCreateRequest
from .service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)


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
    "detect": ["text_detection"],
    "inpaint": ["text_detection", "mask_or_erase_planning", "inpaint"],
    "translate": ["text_detection", "ocr", "translation"],
}
OPERATION_META_KEYS = {
    "detect": "text_detection",
    "inpaint": "inpaint",
    "translate": "translation",
}


@dataclass(slots=True)
class ModelJobError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class JobSubmission:
    schema_version: str
    idempotency_key: str
    operation_kind: str
    request_ref: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext


@dataclass(slots=True)
class JobExecutionRequest:
    job_id: str
    pipeline_id: str
    schema_version: str
    operation_kind: str
    request_ref: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext


@dataclass(slots=True)
class JobExecutionResult:
    status: ModelJobStatus
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    stage_reports: list[StageReport] = field(default_factory=list)
    error: dict[str, Any] | None = None


@dataclass
class ModelJobRecord:
    job_id: str
    pipeline_id: str
    idempotency_key: str
    schema_version: str
    operation_kind: str
    request_ref: str
    document: DocumentIR
    artifacts: dict[str, ArtifactDescriptor]
    runtime_context: StageRuntimeContext
    status: ModelJobStatus = ModelJobStatus.QUEUED
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

        return JobExecutionResult(
            status=ModelJobStatus.SUCCEEDED,
            document=active_document,
            artifacts=dict(request.artifacts),
            stage_reports=stage_reports,
        )


class ModelJobManager:
    def __init__(
        self,
        *,
        executor: JobExecutor | None = None,
        service_client_factory: Callable[[], ServiceEngineBridgeClient] | None = None,
    ) -> None:
        self._executor = executor or PlaceholderJobExecutor()
        self._service_client_factory = service_client_factory
        self._lock = Lock()
        self._jobs_by_id: dict[str, ModelJobRecord] = {}
        self._job_ids_by_idempotency: dict[str, str] = {}

    def create_job(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        self._validate_submission(submission, authorization=authorization)

        with self._lock:
            existing_id = self._job_ids_by_idempotency.get(submission.idempotency_key)
            if existing_id is not None:
                existing = self._jobs_by_id[existing_id]
                status_code = 200 if existing.status in TERMINAL_JOB_STATUSES else 202
                return status_code, self._create_response(existing)

        usage_job_id = self._authorize_usage_hold(submission, authorization=authorization)
        record = ModelJobRecord(
            job_id=f"job_{uuid4().hex}",
            pipeline_id=f"pipe_{uuid4().hex}",
            idempotency_key=submission.idempotency_key,
            schema_version=submission.schema_version,
            operation_kind=submission.operation_kind,
            request_ref=submission.request_ref,
            document=submission.document,
            artifacts=submission.artifacts,
            runtime_context=submission.runtime_context,
            usage_job_id=usage_job_id,
        )

        with self._lock:
            existing_id = self._job_ids_by_idempotency.get(submission.idempotency_key)
            if existing_id is not None:
                existing = self._jobs_by_id[existing_id]
                status_code = 200 if existing.status in TERMINAL_JOB_STATUSES else 202
                return status_code, self._create_response(existing)
            self._jobs_by_id[record.job_id] = record
            self._job_ids_by_idempotency[record.idempotency_key] = record.job_id
            create_response = self._create_response(record)

        Thread(
            target=self._run_job,
            args=(record.job_id, authorization),
            daemon=True,
        ).start()
        return 202, create_response

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._jobs_by_id.get(job_id)
            if record is None:
                raise ModelJobError(
                    status_code=404,
                    code="model_job_not_found",
                    message=f"Unknown job_id: {job_id}",
                )
            return self._detail_response(record)

    def _run_job(self, job_id: str, authorization: str | None) -> None:
        with self._lock:
            record = self._jobs_by_id[job_id]
            record.status = ModelJobStatus.RUNNING

        request = JobExecutionRequest(
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            schema_version=record.schema_version,
            operation_kind=record.operation_kind,
            request_ref=record.request_ref,
            document=record.document.clone(),
            artifacts=dict(record.artifacts),
            runtime_context=record.runtime_context,
        )

        try:
            result = self._executor.execute(request)
        except Exception as exc:  # pragma: no cover - defensive path exercised in tests via custom executor
            result = JobExecutionResult(
                status=ModelJobStatus.FAILED,
                document=record.document.clone(),
                artifacts=dict(record.artifacts),
                error=_error_payload(
                    code="model_stage_failed",
                    message=str(exc),
                    details={"operation_kind": record.operation_kind},
                ),
            )

        billing_error = self._finalize_billing(
            record=record,
            authorization=authorization,
            result=result,
        )
        if billing_error is not None:
            result.error = _merge_error_payload(result.error, billing_error)
            if result.status is ModelJobStatus.SUCCEEDED:
                result.status = ModelJobStatus.PARTIAL

        with self._lock:
            stored = self._jobs_by_id[job_id]
            stored.status = result.status
            stored.document = result.document
            stored.artifacts = result.artifacts
            stored.stage_reports = result.stage_reports
            stored.error = result.error

    def _finalize_billing(
        self,
        *,
        record: ModelJobRecord,
        authorization: str | None,
        result: JobExecutionResult,
    ) -> dict[str, Any] | None:
        if record.runtime_context.mode is not ExecutionMode.SAAS or record.usage_job_id is None:
            return None

        client = self._require_service_client()
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

    def _authorize_usage_hold(
        self,
        submission: JobSubmission,
        *,
        authorization: str | None,
    ) -> str | None:
        if submission.runtime_context.mode is not ExecutionMode.SAAS:
            return None

        client = self._require_service_client()
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
            "artifacts": {
                artifact_ref: artifact_descriptor_to_api_data(descriptor)
                for artifact_ref, descriptor in record.artifacts.items()
            },
            "stage_reports": [stage_report_to_data(report) for report in record.stage_reports],
            "error": record.error,
        }


def submission_from_api_payload(payload: ModelJobCreateRequest) -> JobSubmission:
    runtime_context = runtime_context_from_api_data(payload.runtime_context)
    return JobSubmission(
        schema_version=payload.schema_version,
        idempotency_key=payload.idempotency_key,
        operation_kind=payload.operation_kind,
        request_ref=payload.request_ref,
        document=document_from_data(payload.document),
        artifacts={
            artifact_ref: artifact_descriptor_from_api_data(descriptor)
            for artifact_ref, descriptor in payload.artifacts.items()
        },
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
    )


def artifact_descriptor_from_api_data(payload: dict[str, Any]) -> ArtifactDescriptor:
    return ArtifactDescriptor(
        artifact_ref=str(payload["artifact_ref"]),
        kind=str(payload["kind"]),
        media_type=str(payload["media_type"]),
        uri=str(payload["uri"]),
        width=payload.get("width"),
        height=payload.get("height"),
        byte_size=payload.get("byte_size"),
        checksum=payload.get("checksum"),
        version=int(payload.get("version", 1)),
        producer_stage=payload.get("producer_stage"),
        status=ArtifactStatus(payload.get("status", ArtifactStatus.READY.value)),
        expires_at=_parse_datetime(payload.get("expires_at")),
        metadata=dict(payload.get("metadata", {})),
    )


def artifact_descriptor_to_api_data(descriptor: ArtifactDescriptor) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_ref": descriptor.artifact_ref,
        "kind": descriptor.kind,
        "media_type": descriptor.media_type,
        "uri": descriptor.uri,
        "version": descriptor.version,
        "status": descriptor.status.value,
        "metadata": dict(descriptor.metadata),
    }
    if descriptor.width is not None:
        payload["width"] = descriptor.width
    if descriptor.height is not None:
        payload["height"] = descriptor.height
    if descriptor.byte_size is not None:
        payload["byte_size"] = descriptor.byte_size
    if descriptor.checksum is not None:
        payload["checksum"] = descriptor.checksum
    if descriptor.producer_stage is not None:
        payload["producer_stage"] = descriptor.producer_stage
    if descriptor.expires_at is not None:
        payload["expires_at"] = descriptor.expires_at.isoformat()
    return payload


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


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))
