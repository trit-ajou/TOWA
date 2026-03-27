from __future__ import annotations

from datetime import datetime, timezone
import os

from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus


def append_demo_text_block(request: StageRequest) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    patch = PatchOperation(
        op="append_text_blocks",
        payload={
            "text_blocks": [
                {
                    "block_id": f"{request.stage_name}-block",
                    "source_lang_text": "demo",
                    "translated_text": "demo",
                }
            ]
        },
    )
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        warnings=[],
        metrics={"transport": "subprocess_json"},
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        patches=[patch],
        artifacts={},
        stage_report=report,
    )


def echo_provider_env(request: StageRequest) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    provider_name = os.environ.get("TOWA_STAGE_PROVIDER_NAME")
    credential_source = os.environ.get("TOWA_STAGE_CREDENTIAL_SOURCE")
    credential_id = os.environ.get("TOWA_STAGE_CREDENTIAL_ID")
    credential_version = os.environ.get("TOWA_STAGE_CREDENTIAL_VERSION")
    billing_mode = os.environ.get("TOWA_STAGE_BILLING_MODE")
    api_key = os.environ.get("TOWA_STAGE_SECRET_API_KEY")

    status = StageStatus.SUCCEEDED
    error_code = None
    error_message = None
    if not provider_name or not credential_source or not api_key:
        status = StageStatus.FAILED
        error_code = "missing_stage_env"
        error_message = "Provider credential env injection missing"

    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        warnings=[],
        metrics={
            "transport": "subprocess_json",
            "provider_name": provider_name or "",
            "credential_source": credential_source or "",
            "credential_id": credential_id or "",
            "credential_version": credential_version or "",
            "billing_mode": billing_mode or "",
            "secret_present": "yes" if api_key else "no",
        },
        provider=request.credential_bindings.get("primary_provider"),
        error_code=error_code,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        patches=[],
        artifacts={},
        stage_report=report,
    )


def fail_demo_stage(request: StageRequest) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        warnings=[],
        metrics={"transport": "subprocess_json"},
        error_code="demo_failure",
        error_message="Intentional IPC stage failure",
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        patches=[],
        artifacts={},
        stage_report=report,
    )
