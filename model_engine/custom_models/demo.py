from __future__ import annotations

from datetime import datetime, timezone

from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus


def demo_text_detection(request: StageRequest) -> StageResponse:
    """Example custom model entrypoint used by docs and tests."""

    started_at = datetime.now(timezone.utc)
    patch = PatchOperation(
        op="set_stage_meta",
        payload={
            "key": "custom_model_demo",
            "value": "python_callable",
        },
    )
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        metrics={"transport": "python_callable"},
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
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
