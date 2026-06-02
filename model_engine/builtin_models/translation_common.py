from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Any, Optional

from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.credentials import CredentialBinding
from ..contracts.document_ir import TextBlock
from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus
from ..contracts.translated_text_blocks import TranslatedTextBlocksPayload
from ..storage import stage_run_slug, stage_transaction_dir


_TRANSLATED_TEXT_BLOCKS_MEDIA_TYPE = "application/json"


def resolve_source_blocks(request: StageRequest, *, engine_name: str) -> list[TextBlock]:
    if not request.document.text_blocks:
        raise ValueError(f"{engine_name} requires at least one text block")
    source_blocks = [block for block in request.document.text_blocks]
    if not any(block.source_lang_text.strip() for block in source_blocks):
        raise ValueError(
            f"{engine_name} requires text blocks with source_lang_text. "
            "Run detect first and submit the detected text_blocks to translate."
        )
    return source_blocks


def apply_translations(
    source_blocks: list[TextBlock],
    translation_entries: list[dict[str, str]],
    *,
    engine: str,
    model_name: str,
    source_language: str,
    target_language: str,
) -> tuple[list[TextBlock], list[str], dict[str, Any]]:
    warnings: list[str] = []
    by_block_id = {
        entry["block_id"]: entry["translated_text"]
        for entry in translation_entries
        if entry["block_id"]
    }
    translated_blocks: list[TextBlock] = []
    translated_count = 0
    missing_count = 0
    used_positional_alignment = False

    for index, block in enumerate(source_blocks):
        translated_text = by_block_id.get(block.block_id, "")
        if not translated_text and index < len(translation_entries):
            positional_text = translation_entries[index]["translated_text"]
            if positional_text:
                translated_text = positional_text
                used_positional_alignment = True

        if translated_text:
            translated_count += 1
        else:
            missing_count += 1

        translated_blocks.append(
            TextBlock(
                block_id=block.block_id,
                source_lang_text=block.source_lang_text,
                translated_text=translated_text,
                polygon=list(block.polygon),
                bbox=dict(block.bbox),
                reading_order=block.reading_order,
                speaker=block.speaker,
                style_hint=dict(block.style_hint),
                font_hint=dict(block.font_hint),
                writing_mode=block.writing_mode,
                source_region_ref=block.source_region_ref,
            )
        )

    if used_positional_alignment:
        warnings.append("translation_result_positionally_aligned")
    if missing_count:
        warnings.append(f"translation_missing_count={missing_count}")

    return translated_blocks, warnings, {
        "engine": engine,
        "model_name": model_name,
        "source_language": source_language,
        "target_language": target_language,
        "source_block_count": len(source_blocks),
        "translated_count": translated_count,
        "missing_count": missing_count,
    }


def build_translation_success_response(
    request: StageRequest,
    *,
    engine: str,
    model_name: str,
    source_language: str,
    target_language: str,
    translated_blocks: list[TextBlock],
    warnings: list[str],
    metrics: dict[str, Any],
    provider: Optional[CredentialBinding],
    started_at: datetime,
) -> StageResponse:
    payload = TranslatedTextBlocksPayload(
        schema_version=request.schema_version,
        engine=engine,
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        blocks=translated_blocks,
        metadata=metrics,
    )
    artifact_descriptor = write_translated_text_blocks_artifact(request, payload)
    status = StageStatus.SUCCEEDED if metrics["missing_count"] == 0 else StageStatus.PARTIAL
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[artifact_descriptor.artifact_ref],
        warnings=warnings,
        metrics={
            "engine": engine,
            "model_name": model_name,
            "source_language": source_language,
            "target_language": target_language,
            "source_block_count": metrics["source_block_count"],
            "translated_count": metrics["translated_count"],
            "missing_count": metrics["missing_count"],
        },
        provider=provider,
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        patches=[
            PatchOperation(
                op="replace_text_blocks",
                payload={"text_blocks": [asdict(block) for block in translated_blocks]},
            ),
            PatchOperation(
                op="set_stage_meta",
                payload={
                    "key": "translation",
                    "value": {
                        "engine": engine,
                        "model_name": model_name,
                        "artifact_ref": artifact_descriptor.artifact_ref,
                        "source_language": source_language,
                        "target_language": target_language,
                        "translated_count": metrics["translated_count"],
                        "missing_count": metrics["missing_count"],
                    },
                },
            ),
        ],
        artifacts={artifact_descriptor.artifact_ref: artifact_descriptor},
        stage_report=report,
    )


def write_translated_text_blocks_artifact(
    request: StageRequest,
    payload: TranslatedTextBlocksPayload,
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    artifact_path = stage_dir / f"{run_slug}_translated_text_blocks.json"
    artifact_path.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/translated_text_blocks"
    )
    return ArtifactDescriptor(
        artifact_ref=artifact_ref,
        kind="translated_text_blocks",
        media_type=_TRANSLATED_TEXT_BLOCKS_MEDIA_TYPE,
        uri=artifact_path.resolve().as_uri(),
        byte_size=artifact_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={
            "engine": payload.engine,
            "model_name": payload.model_name,
            "source_language": payload.source_language,
            "target_language": payload.target_language,
            "translated_count": payload.metadata.get("translated_count", 0),
            "missing_count": payload.metadata.get("missing_count", 0),
        },
    )


def build_failed_translation_response(
    request: StageRequest,
    *,
    engine: str,
    model_name: str,
    source_language: str,
    target_language: str,
    source_blocks: list[TextBlock],
    provider: Optional[CredentialBinding],
    started_at: datetime,
    error: Exception,
) -> StageResponse:
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        warnings=[],
        metrics={
            "engine": engine,
            "model_name": model_name,
            "source_language": source_language,
            "target_language": target_language,
            "source_block_count": len(source_blocks),
        },
        provider=provider,
        error_code=error_code_for_translation_exception(error),
        error_message=str(error),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
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


def error_code_for_translation_exception(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "provider_timeout"
    if isinstance(error, ValueError):
        return "translation_invalid_output"
    return "translation_provider_error"
