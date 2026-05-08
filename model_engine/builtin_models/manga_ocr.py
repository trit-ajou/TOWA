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
from ..contracts.document_ir import Point, TextBlock
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.ocr_text_blocks import OcrTextBlocksPayload
from ..contracts.patches import PatchOperation
from ..contracts.stages import ExecutionMode, StageReport, StageRequest, StageResponse, StageStatus
from ..contracts.text_regions import TextRegion, text_regions_payload_from_mapping
from ..models.registry import ModelRegistry
from ..storage import stage_run_slug, stage_transaction_dir


MANGA_OCR_MODEL_ID = "builtin.manga_ocr.recognizer"
_OCR_TEXT_BLOCKS_MEDIA_TYPE = "application/json"
_DEFAULT_REGION_PADDING = 12
_DEFAULT_MERGE_REGIONS = True
_DEFAULT_MERGE_GAP_PX = 24
_DEFAULT_MERGE_OVERLAP_RATIO = 0.25
_DEFAULT_READING_ORDER_MODE = "vertical_rtl"
_DEFAULT_MIN_REGION_AREA_PX = 160.0
_DEFAULT_MIN_REGION_AREA_RATIO = 0.00015
_DEFAULT_MAX_TEXT_DENSITY_PER_1000_PX2 = 1.5
_DEFAULT_SMALL_REGION_LONG_TEXT_AREA_PX = 6000.0
_DEFAULT_SMALL_REGION_LONG_TEXT_AREA_RATIO = 0.004
_DEFAULT_SMALL_REGION_LONG_TEXT_MIN_CHARS = 16
_DEFAULT_HALLUCINATION_ACTION = "mark"


def build_manga_ocr_manifest() -> StageManifest:
    return StageManifest(
        model_id=MANGA_OCR_MODEL_ID,
        adapter_id="adapter.builtin.manga_ocr.recognizer",
        stage_kind=StageKind.OCR,
        required_artifact_kinds=["bitmap", "text_regions"],
        produced_artifact_kinds=["ocr_text_blocks"],
        supported_modes=[ExecutionMode.LOCAL, ExecutionMode.SAAS],
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
        warnings=list(metrics["warnings"]),
        metrics={
            "engine": "manga_ocr",
            "language_hint": str(stage_config.get("language_hint", "ja")),
            "region_count": metrics["region_count"],
            "ocr_region_count": metrics["ocr_region_count"],
            "recognized_count": metrics["recognized_count"],
            "empty_region_count": metrics["empty_region_count"],
            "skipped_small_region_count": metrics["skipped_small_region_count"],
            "needs_review_count": metrics["needs_review_count"],
            "high_density_count": metrics["high_density_count"],
            "small_region_long_text_count": metrics["small_region_long_text_count"],
            "dropped_hallucination_count": metrics["dropped_hallucination_count"],
            "merged_region_count": metrics["merged_region_count"],
            "max_source_regions_per_block": metrics["max_source_regions_per_block"],
            "avg_text_density_per_1000_px2": metrics["avg_text_density_per_1000_px2"],
            "max_text_density_per_1000_px2": metrics["max_text_density_per_1000_px2"],
            "min_ocr_region_area_px": metrics["min_ocr_region_area_px"],
            "avg_confidence": metrics["avg_confidence"],
            "writing_mode_detected": metrics["writing_mode_detected"],
            "reading_order_mode": metrics["reading_order_mode"],
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
                        "needs_review_count": metrics["needs_review_count"],
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
    padding = int(stage_config.get("region_padding", _DEFAULT_REGION_PADDING))
    blocks: list[TextBlock] = []
    confidence_values: list[float] = []
    writing_modes: set[str] = set()
    empty_region_count = 0
    skipped_small_region_count = 0
    needs_review_count = 0
    high_density_count = 0
    small_region_long_text_count = 0
    dropped_hallucination_count = 0
    source_region_counts: list[int] = []
    text_density_values: list[float] = []
    region_area_values: list[float] = []
    warnings: list[str] = []
    image_area = float(base_image.width * base_image.height)
    prepared_regions = _prepare_ocr_regions(regions, stage_config=stage_config)
    ocr_regions = _filter_small_regions(
        prepared_regions,
        image_area=image_area,
        stage_config=stage_config,
    )
    skipped_small_region_count = len(prepared_regions) - len(ocr_regions)
    ocr_regions = _sort_regions_for_reading_order(
        ocr_regions,
        mode=_reading_order_mode(stage_config),
    )

    for index, region in enumerate(ocr_regions, start=1):
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
        source_region_ids = list(region.metadata.get("source_region_ids", [region.region_id]))
        source_region_counts.append(len(source_region_ids))
        region_area = _bbox_area(region.bbox)
        text_density = _text_density_per_1000_px2(recognized_text, region.bbox)
        text_density_values.append(text_density)
        region_area_values.append(region_area)
        block_warnings = _ocr_quality_warnings(
            text=recognized_text,
            region_area=region_area,
            text_density=text_density,
            image_area=image_area,
            stage_config=stage_config,
        )
        if "high_text_density" in block_warnings:
            high_density_count += 1
        if "small_region_long_text" in block_warnings:
            small_region_long_text_count += 1
        if block_warnings:
            if _hallucination_action(stage_config) == "drop":
                dropped_hallucination_count += 1
                continue
            needs_review_count += 1
            warnings.extend(block_warnings)

        style_hint: dict[str, Any] = {}
        style_hint.update(
            {
                "ocr_text_density_per_1000_px2": text_density,
                "ocr_region_area_px": round(region_area, 3),
                "ocr_text_length": len(recognized_text),
            }
        )
        if recognition["confidence"] is not None:
            style_hint["ocr_confidence"] = float(recognition["confidence"])
        if block_warnings:
            style_hint.update(
                {
                    "ocr_status": "needs_review",
                    "ocr_warnings": block_warnings,
                }
            )
        blocks.append(
            TextBlock(
                block_id=f"block_{index:04d}",
                source_lang_text=recognized_text,
                translated_text="",
                polygon=list(region.polygon),
                bbox=dict(region.bbox),
                reading_order=len(blocks),
                writing_mode=writing_mode,
                source_region_ref=",".join(source_region_ids),
                style_hint=style_hint,
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
        "ocr_region_count": len(ocr_regions),
        "recognized_count": len(blocks),
        "empty_region_count": empty_region_count,
        "skipped_small_region_count": skipped_small_region_count,
        "needs_review_count": needs_review_count,
        "high_density_count": high_density_count,
        "small_region_long_text_count": small_region_long_text_count,
        "dropped_hallucination_count": dropped_hallucination_count,
        "avg_text_density_per_1000_px2": _average(text_density_values),
        "max_text_density_per_1000_px2": max(text_density_values) if text_density_values else None,
        "min_ocr_region_area_px": min(region_area_values) if region_area_values else None,
        "avg_confidence": avg_confidence,
        "writing_mode_detected": writing_mode_detected,
        "reading_order_mode": _reading_order_mode(stage_config),
        "merged_region_count": max(0, len(regions) - len(prepared_regions)),
        "max_source_regions_per_block": max(source_region_counts) if source_region_counts else 0,
        "warnings": sorted(set(warnings)),
    }


def _prepare_ocr_regions(
    regions: list[TextRegion],
    *,
    stage_config: dict[str, object],
) -> list[TextRegion]:
    if not bool(stage_config.get("merge_regions", _DEFAULT_MERGE_REGIONS)):
        return regions
    return _merge_text_regions(
        regions,
        merge_gap_px=float(stage_config.get("merge_gap_px", _DEFAULT_MERGE_GAP_PX)),
        min_overlap_ratio=float(
            stage_config.get("merge_min_overlap_ratio", _DEFAULT_MERGE_OVERLAP_RATIO)
        ),
    )


def _merge_text_regions(
    regions: list[TextRegion],
    *,
    merge_gap_px: float,
    min_overlap_ratio: float,
) -> list[TextRegion]:
    ordered = _sort_regions_for_reading_order(regions, mode="preserve")
    groups: list[list[TextRegion]] = []
    for region in ordered:
        target_group = None
        for group in groups:
            if any(
                _regions_should_merge(
                    existing,
                    region,
                    merge_gap_px=merge_gap_px,
                    min_overlap_ratio=min_overlap_ratio,
                )
                for existing in group
            ):
                target_group = group
                break
        if target_group is None:
            groups.append([region])
        else:
            target_group.append(region)

    groups.sort(key=_group_reading_order_key)
    return [_merged_region(group, index) for index, group in enumerate(groups, start=1)]


def _filter_small_regions(
    regions: list[TextRegion],
    *,
    image_area: float,
    stage_config: dict[str, object],
) -> list[TextRegion]:
    min_area_px = float(stage_config.get("min_ocr_region_area_px", _DEFAULT_MIN_REGION_AREA_PX))
    min_area_ratio = float(stage_config.get("min_ocr_region_area_ratio", _DEFAULT_MIN_REGION_AREA_RATIO))
    min_area = max(min_area_px, image_area * min_area_ratio)
    if min_area <= 0:
        return regions
    return [
        region
        for region in regions
        if _bbox_area(region.bbox) >= min_area
    ]


def _sort_regions_for_reading_order(regions: list[TextRegion], *, mode: str) -> list[TextRegion]:
    if mode == "vertical_rtl":
        return sorted(regions, key=_vertical_rtl_region_key)
    if mode == "horizontal_ltr":
        return sorted(regions, key=_horizontal_ltr_region_key)
    return sorted(
        regions,
        key=lambda region: (
            region.reading_order if region.reading_order is not None else 10**9,
            float(region.bbox.get("x", 0.0)),
            float(region.bbox.get("y", 0.0)),
        ),
    )


def _group_reading_order_key(group: list[TextRegion]) -> tuple[float, float, float, float]:
    bbox = _union_bbox([region.bbox for region in group])
    return _vertical_rtl_bbox_key(bbox)


def _vertical_rtl_region_key(region: TextRegion) -> tuple[float, float, float, float]:
    return _vertical_rtl_bbox_key(region.bbox)


def _vertical_rtl_bbox_key(bbox: dict[str, float]) -> tuple[float, float, float, float]:
    center_x = float(bbox.get("x", 0.0)) + float(bbox.get("width", 0.0)) / 2
    top = float(bbox.get("y", 0.0))
    left = float(bbox.get("x", 0.0))
    height = float(bbox.get("height", 0.0))
    return (-center_x, top, left, -height)


def _horizontal_ltr_region_key(region: TextRegion) -> tuple[float, float, float]:
    bbox = region.bbox
    return (
        float(bbox.get("y", 0.0)),
        float(bbox.get("x", 0.0)),
        -(float(bbox.get("width", 0.0)) * float(bbox.get("height", 0.0))),
    )


def _reading_order_mode(stage_config: dict[str, object]) -> str:
    configured = stage_config.get("reading_order_mode")
    if isinstance(configured, str) and configured:
        return configured
    writing_mode = str(stage_config.get("writing_mode_hint", "vertical")).lower()
    if writing_mode == "vertical":
        return _DEFAULT_READING_ORDER_MODE
    return "horizontal_ltr"


def _hallucination_action(stage_config: dict[str, object]) -> str:
    action = str(stage_config.get("hallucination_action", _DEFAULT_HALLUCINATION_ACTION)).lower()
    if action not in {"mark", "drop"}:
        return _DEFAULT_HALLUCINATION_ACTION
    return action


def _ocr_quality_warnings(
    *,
    text: str,
    region_area: float,
    text_density: float,
    image_area: float,
    stage_config: dict[str, object],
) -> list[str]:
    warnings: list[str] = []
    max_density = float(
        stage_config.get(
            "max_text_density_per_1000_px2",
            _DEFAULT_MAX_TEXT_DENSITY_PER_1000_PX2,
        )
    )
    if max_density > 0 and text_density > max_density:
        warnings.append("high_text_density")

    small_long_text_area = max(
        float(
            stage_config.get(
                "small_region_long_text_area_px",
                _DEFAULT_SMALL_REGION_LONG_TEXT_AREA_PX,
            )
        ),
        image_area
        * float(
            stage_config.get(
                "small_region_long_text_area_ratio",
                _DEFAULT_SMALL_REGION_LONG_TEXT_AREA_RATIO,
            )
        ),
    )
    small_long_text_min_chars = int(
        stage_config.get(
            "small_region_long_text_min_chars",
            _DEFAULT_SMALL_REGION_LONG_TEXT_MIN_CHARS,
        )
    )
    if (
        small_long_text_area > 0
        and region_area <= small_long_text_area
        and len(text) >= small_long_text_min_chars
    ):
        warnings.append("small_region_long_text")
    return warnings


def _average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _text_density_per_1000_px2(text: str, bbox: dict[str, float]) -> float:
    area = max(1.0, _bbox_area(bbox))
    return round((len(text) / area) * 1000.0, 6)


def _regions_should_merge(
    left: TextRegion,
    right: TextRegion,
    *,
    merge_gap_px: float,
    min_overlap_ratio: float,
) -> bool:
    left_bbox = left.bbox
    right_bbox = right.bbox
    return (
        _vertical_overlap_ratio(left_bbox, right_bbox) >= min_overlap_ratio
        and _horizontal_gap(left_bbox, right_bbox) <= merge_gap_px
    ) or (
        _horizontal_overlap_ratio(left_bbox, right_bbox) >= min_overlap_ratio
        and _vertical_gap(left_bbox, right_bbox) <= merge_gap_px
    )


def _merged_region(group: list[TextRegion], index: int) -> TextRegion:
    bbox = _union_bbox([region.bbox for region in group])
    confidence_values = [region.confidence for region in group if region.confidence is not None]
    reading_orders = [
        region.reading_order
        for region in group
        if region.reading_order is not None
    ]
    source_region_ids = [region.region_id for region in group]
    return TextRegion(
        region_id=f"ocr_region_{index:04d}",
        polygon=_polygon_from_bbox(bbox),
        bbox=bbox,
        confidence=(
            round(sum(confidence_values) / len(confidence_values), 6)
            if confidence_values
            else None
        ),
        reading_order=min(reading_orders) if reading_orders else index - 1,
        source_artifact_ref=group[0].source_artifact_ref,
        metadata={
            "source_region_ids": source_region_ids,
            "source_region_count": len(source_region_ids),
        },
    )


def _union_bbox(bboxes: list[dict[str, float]]) -> dict[str, float]:
    left = min(float(bbox.get("x", 0.0)) for bbox in bboxes)
    top = min(float(bbox.get("y", 0.0)) for bbox in bboxes)
    right = max(float(bbox.get("x", 0.0)) + float(bbox.get("width", 0.0)) for bbox in bboxes)
    bottom = max(float(bbox.get("y", 0.0)) + float(bbox.get("height", 0.0)) for bbox in bboxes)
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _bbox_area(bbox: dict[str, float]) -> float:
    return max(0.0, float(bbox.get("width", 0.0))) * max(0.0, float(bbox.get("height", 0.0)))


def _polygon_from_bbox(bbox: dict[str, float]) -> list[Point]:
    left = float(bbox["x"])
    top = float(bbox["y"])
    right = left + float(bbox["width"])
    bottom = top + float(bbox["height"])

    return [
        Point(x=left, y=top),
        Point(x=right, y=top),
        Point(x=right, y=bottom),
        Point(x=left, y=bottom),
    ]


def _horizontal_gap(left: dict[str, float], right: dict[str, float]) -> float:
    left_min = float(left.get("x", 0.0))
    left_max = left_min + float(left.get("width", 0.0))
    right_min = float(right.get("x", 0.0))
    right_max = right_min + float(right.get("width", 0.0))
    return max(0.0, max(left_min, right_min) - min(left_max, right_max))


def _vertical_gap(left: dict[str, float], right: dict[str, float]) -> float:
    left_min = float(left.get("y", 0.0))
    left_max = left_min + float(left.get("height", 0.0))
    right_min = float(right.get("y", 0.0))
    right_max = right_min + float(right.get("height", 0.0))
    return max(0.0, max(left_min, right_min) - min(left_max, right_max))


def _horizontal_overlap_ratio(left: dict[str, float], right: dict[str, float]) -> float:
    left_min = float(left.get("x", 0.0))
    left_max = left_min + float(left.get("width", 0.0))
    right_min = float(right.get("x", 0.0))
    right_max = right_min + float(right.get("width", 0.0))
    overlap = max(0.0, min(left_max, right_max) - max(left_min, right_min))
    denominator = max(1.0, min(float(left.get("width", 0.0)), float(right.get("width", 0.0))))
    return overlap / denominator


def _vertical_overlap_ratio(left: dict[str, float], right: dict[str, float]) -> float:
    left_min = float(left.get("y", 0.0))
    left_max = left_min + float(left.get("height", 0.0))
    right_min = float(right.get("y", 0.0))
    right_max = right_min + float(right.get("height", 0.0))
    overlap = max(0.0, min(left_max, right_max) - max(left_min, right_min))
    denominator = max(1.0, min(float(left.get("height", 0.0)), float(right.get("height", 0.0))))
    return overlap / denominator


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
    recognizer = config.get("_manga_ocr_recognizer")
    if recognizer is None:
        try:
            from manga_ocr import MangaOcr
        except ImportError as exc:
            raise RuntimeError(
                "manga-ocr is not installed. Add it to the local environment before running the built-in OCR stage."
            ) from exc

        recognizer = MangaOcr()
        config["_manga_ocr_recognizer"] = recognizer
    recognized_text = recognizer(image)
    return {
        "text": recognized_text,
        "confidence": None,
        "writing_mode": str(config.get("writing_mode_hint", "unknown")),
    }
