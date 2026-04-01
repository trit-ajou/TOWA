from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from PIL import Image

from ..adapters.callable import CallableModelAdapter
from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.document_ir import TextBlock
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.ocr_text_blocks import OcrTextBlocksPayload
from ..contracts.patches import PatchOperation
from ..contracts.stages import ExecutionMode, StageReport, StageRequest, StageResponse, StageStatus
from ..contracts.text_regions import TextRegion, text_regions_payload_from_mapping
from ..models.registry import ModelRegistry
from ..storage import stage_run_slug, stage_transaction_dir


MANGA_OCR_MODEL_ID = "builtin.manga_ocr.recognizer"
_OCR_TEXT_BLOCKS_MEDIA_TYPE = "application/json"


def build_manga_ocr_manifest() -> StageManifest:
    return StageManifest(
        model_id=MANGA_OCR_MODEL_ID,
        adapter_id="adapter.builtin.manga_ocr.recognizer",
        stage_kind=StageKind.OCR,
        required_artifact_kinds=["bitmap", "text_regions"],
        produced_artifact_kinds=["ocr_text_blocks"],
        supported_modes=[ExecutionMode.LOCAL],
        resource_profile=ResourceProfile(
            cpu_threads=2,
            memory_mb=2048,
            gpu_required=False,
            latency_tier="local_inference",
        ),
        custom_model=False,
        priority=50,
        display_name="Manga OCR Recognizer",
        tags=["builtin", "manga-ocr", "ocr", "japanese_manga"],
    )


def build_manga_ocr_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_manga_ocr_manifest(),
        import_path="model_engine.builtin_models.manga_ocr:manga_ocr_handler",
    )


def register_manga_ocr_model(registry: ModelRegistry) -> str:
    registry.register(build_manga_ocr_adapter())
    return MANGA_OCR_MODEL_ID


def manga_ocr_handler(request: StageRequest) -> StageResponse:
    return run_manga_ocr(request)


def run_manga_ocr(
    request: StageRequest,
    *,
    recognize_region_fn: Optional[Callable[[Image.Image, dict[str, object]], object]] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    bitmap_artifact = _resolve_bitmap_artifact(request)
    text_regions_artifact = _resolve_text_regions_artifact(request)
    image_path = _file_path_from_uri(bitmap_artifact.uri)
    text_regions_payload = text_regions_payload_from_mapping(
        json.loads(_file_path_from_uri(text_regions_artifact.uri).read_text(encoding="utf-8"))
    )
    stage_config = dict(request.stage_config)
    recognizer = recognize_region_fn or _recognize_with_manga_ocr

    with Image.open(image_path) as base_image:
        base_image = base_image.convert("RGB")
        blocks, metrics = _recognize_text_blocks(
            base_image,
            text_regions_payload.regions,
            stage_config=stage_config,
            recognizer=recognizer,
        )

    payload = OcrTextBlocksPayload(
        schema_version=request.schema_version,
        engine="manga_ocr",
        source_artifact_ref=bitmap_artifact.artifact_ref,
        text_regions_artifact_ref=text_regions_artifact.artifact_ref,
        blocks=blocks,
        metadata=metrics,
    )
    artifact_descriptor = _write_ocr_text_blocks_artifact(request, payload)
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[artifact_descriptor.artifact_ref],
        warnings=[],
        metrics={
            "engine": "manga_ocr",
            "language_hint": str(stage_config.get("language_hint", "ja")),
            "region_count": metrics["region_count"],
            "recognized_count": metrics["recognized_count"],
            "empty_region_count": metrics["empty_region_count"],
            "avg_confidence": metrics["avg_confidence"],
            "writing_mode_detected": metrics["writing_mode_detected"],
            "text_regions_artifact_ref": text_regions_artifact.artifact_ref,
        },
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        patches=[
            PatchOperation(
                op="replace_text_blocks",
                payload={"text_blocks": [asdict(block) for block in blocks]},
            ),
            PatchOperation(
                op="set_stage_meta",
                payload={
                    "key": "ocr",
                    "value": {
                        "engine": "manga_ocr",
                        "artifact_ref": artifact_descriptor.artifact_ref,
                        "recognized_count": metrics["recognized_count"],
                        "empty_region_count": metrics["empty_region_count"],
                    },
                },
            ),
        ],
        artifacts={artifact_descriptor.artifact_ref: artifact_descriptor},
        stage_report=report,
    )


def _resolve_bitmap_artifact(request: StageRequest) -> ArtifactDescriptor:
    preferred_ref = request.stage_config.get("input_artifact_ref")
    if isinstance(preferred_ref, str):
        artifact = request.artifacts.get(preferred_ref)
        if artifact is None:
            raise KeyError(f"Configured input_artifact_ref not found: {preferred_ref}")
        if artifact.kind != "bitmap":
            raise ValueError(f"Configured input_artifact_ref is not a bitmap: {preferred_ref}")
        return artifact

    for artifact in request.artifacts.values():
        if artifact.kind == "bitmap":
            return artifact
    raise ValueError("manga-ocr requires at least one bitmap artifact")


def _resolve_text_regions_artifact(request: StageRequest) -> ArtifactDescriptor:
    preferred_ref = request.stage_config.get("text_regions_artifact_ref")
    if isinstance(preferred_ref, str):
        artifact = request.artifacts.get(preferred_ref)
        if artifact is None:
            raise KeyError(f"Configured text_regions_artifact_ref not found: {preferred_ref}")
        if artifact.kind != "text_regions":
            raise ValueError(f"Configured text_regions_artifact_ref is not text_regions: {preferred_ref}")
        return artifact

    for artifact in request.artifacts.values():
        if artifact.kind == "text_regions":
            return artifact
    raise ValueError("manga-ocr requires a text_regions artifact")


def _file_path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise RuntimeError("manga-ocr currently supports only file:// artifacts")
    return Path(parsed.path)


def _recognize_text_blocks(
    base_image: Image.Image,
    regions: list[TextRegion],
    *,
    stage_config: dict[str, object],
    recognizer: Callable[[Image.Image, dict[str, object]], object],
) -> tuple[list[TextBlock], dict[str, Any]]:
    padding = int(stage_config.get("region_padding", 0))
    blocks: list[TextBlock] = []
    confidence_values: list[float] = []
    writing_modes: set[str] = set()
    empty_region_count = 0

    for index, region in enumerate(regions, start=1):
        crop = _crop_region(base_image, region, padding=padding)
        recognition = _normalize_recognition_result(recognizer(crop, stage_config))
        recognized_text = recognition["text"].strip()
        if not recognized_text:
            empty_region_count += 1
            continue
        if recognition["confidence"] is not None:
            confidence_values.append(float(recognition["confidence"]))
        writing_mode = recognition["writing_mode"] or str(stage_config.get("writing_mode_hint", "unknown"))
        writing_modes.add(writing_mode)
        blocks.append(
            TextBlock(
                block_id=f"block_{index:04d}",
                source_lang_text=recognized_text,
                translated_text="",
                polygon=list(region.polygon),
                bbox=dict(region.bbox),
                reading_order=region.reading_order,
                writing_mode=writing_mode,
                source_region_ref=region.region_id,
            )
        )

    avg_confidence = (
        round(sum(confidence_values) / len(confidence_values), 6)
        if confidence_values
        else None
    )
    writing_mode_detected = "mixed" if len(writing_modes) > 1 else (next(iter(writing_modes)) if writing_modes else "unknown")
    return blocks, {
        "region_count": len(regions),
        "recognized_count": len(blocks),
        "empty_region_count": empty_region_count,
        "avg_confidence": avg_confidence,
        "writing_mode_detected": writing_mode_detected,
    }


def _crop_region(base_image: Image.Image, region: TextRegion, *, padding: int) -> Image.Image:
    bbox = region.bbox
    left = max(0, int(bbox.get("x", 0.0) - padding))
    top = max(0, int(bbox.get("y", 0.0) - padding))
    right = min(base_image.width, int(bbox.get("x", 0.0) + bbox.get("width", 0.0) + padding))
    bottom = min(base_image.height, int(bbox.get("y", 0.0) + bbox.get("height", 0.0) + padding))
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid OCR region bbox: {bbox}")
    return base_image.crop((left, top, right, bottom))


def _normalize_recognition_result(result: object) -> dict[str, Any]:
    if isinstance(result, str):
        return {"text": result, "confidence": None, "writing_mode": None}
    if not isinstance(result, dict):
        raise ValueError("manga-ocr recognizer must return either a string or a mapping")
    return {
        "text": str(result.get("text", "")),
        "confidence": float(result["confidence"]) if result.get("confidence") is not None else None,
        "writing_mode": str(result["writing_mode"]) if result.get("writing_mode") is not None else None,
    }


def _write_ocr_text_blocks_artifact(
    request: StageRequest,
    payload: OcrTextBlocksPayload,
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    artifact_path = stage_dir / f"{run_slug}_ocr_text_blocks.json"
    artifact_path.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    artifact_ref = f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/ocr_text_blocks"
    return ArtifactDescriptor(
        artifact_ref=artifact_ref,
        kind="ocr_text_blocks",
        media_type=_OCR_TEXT_BLOCKS_MEDIA_TYPE,
        uri=artifact_path.resolve().as_uri(),
        byte_size=artifact_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={
            "engine": payload.engine,
            "recognized_count": len(payload.blocks),
            "source_artifact_ref": payload.source_artifact_ref,
            "text_regions_artifact_ref": payload.text_regions_artifact_ref,
        },
    )


def _recognize_with_manga_ocr(image: Image.Image, config: dict[str, object]) -> dict[str, Any]:
    _ = config
    try:
        from manga_ocr import MangaOcr
    except ImportError as exc:
        raise RuntimeError(
            "manga-ocr is not installed. Add it to the local environment before running the built-in OCR stage."
        ) from exc

    recognizer = MangaOcr()
    recognized_text = recognizer(image)
    return {
        "text": recognized_text,
        "confidence": None,
        "writing_mode": str(config.get("writing_mode_hint", "unknown")),
    }
