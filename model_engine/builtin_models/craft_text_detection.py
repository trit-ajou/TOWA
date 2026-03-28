from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from PIL import Image

from ..adapters.callable import CallableModelAdapter
from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.document_ir import Point
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.patches import PatchOperation
from ..contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageStatus,
)
from ..contracts.text_regions import TextRegion, TextRegionsPayload
from ..models.registry import ModelRegistry
from ..storage import stage_run_slug, stage_transaction_dir


CRAFT_TEXT_DETECTION_MODEL_ID = "builtin.craft.text_detection"
_TEXT_REGIONS_MEDIA_TYPE = "application/json"
_DEFAULT_TEXT_THRESHOLD = 0.7
_DEFAULT_LINK_THRESHOLD = 0.4
_DEFAULT_LOW_TEXT = 0.4


def build_craft_text_detection_manifest() -> StageManifest:
    return StageManifest(
        model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
        adapter_id="adapter.builtin.craft.text_detection",
        stage_kind=StageKind.TEXT_DETECTION,
        required_artifact_kinds=["bitmap"],
        produced_artifact_kinds=["text_regions"],
        supported_modes=[ExecutionMode.LOCAL],
        resource_profile=ResourceProfile(
            cpu_threads=2,
            memory_mb=2048,
            gpu_required=False,
            latency_tier="local_inference",
        ),
        custom_model=False,
        priority=50,
        display_name="CRAFT Text Detection",
        tags=["builtin", "craft", "text_detection"],
    )


def build_craft_text_detection_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_craft_text_detection_manifest(),
        import_path="model_engine.builtin_models.craft_text_detection:craft_text_detection_handler",
    )


def register_craft_text_detection_model(registry: ModelRegistry) -> str:
    registry.register(build_craft_text_detection_adapter())
    return CRAFT_TEXT_DETECTION_MODEL_ID


def craft_text_detection_handler(request: StageRequest) -> StageResponse:
    return run_craft_text_detection(request)


def run_craft_text_detection(
    request: StageRequest,
    *,
    detect_text_fn: Optional[Callable[[str, dict[str, object]], dict[str, object]]] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    bitmap_artifact = _resolve_bitmap_artifact(request)
    image_path = _file_path_from_uri(bitmap_artifact.uri)
    if image_path is None:
        raise RuntimeError(
            "CRAFT text detection currently supports only file:// bitmap artifacts"
        )

    image_width, image_height = _image_size(image_path)
    stage_config = dict(request.stage_config)
    detect_text_fn = detect_text_fn or _detect_with_craft
    raw_result = detect_text_fn(str(image_path), stage_config)
    regions = _normalize_text_regions(
        raw_result,
        source_artifact_ref=bitmap_artifact.artifact_ref,
    )
    payload = TextRegionsPayload(
        schema_version=request.schema_version,
        detector="craft",
        source_artifact_ref=bitmap_artifact.artifact_ref,
        image_width=image_width,
        image_height=image_height,
        regions=regions,
        metadata={
            "text_threshold": float(stage_config.get("text_threshold", _DEFAULT_TEXT_THRESHOLD)),
            "link_threshold": float(stage_config.get("link_threshold", _DEFAULT_LINK_THRESHOLD)),
            "low_text": float(stage_config.get("low_text", _DEFAULT_LOW_TEXT)),
        },
    )
    artifact_descriptor = _write_text_regions_artifact(request, payload)
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[artifact_descriptor.artifact_ref],
        warnings=[],
        metrics={
            "detector": "craft",
            "region_count": len(payload.regions),
            "input_artifact_ref": bitmap_artifact.artifact_ref,
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
                op="set_stage_meta",
                payload={
                    "key": "text_detection",
                    "value": {
                        "engine": "craft",
                        "artifact_ref": artifact_descriptor.artifact_ref,
                        "region_count": len(payload.regions),
                    },
                },
            )
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
    raise ValueError("CRAFT text detection requires at least one bitmap artifact")


def _file_path_from_uri(uri: str) -> Optional[Path]:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(parsed.path)


def _image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        width, height = image.size
    return int(width), int(height)


def _normalize_text_regions(
    raw_result: dict[str, object],
    *,
    source_artifact_ref: str,
) -> list[TextRegion]:
    polygons = raw_result.get("polys") or raw_result.get("boxes") or []
    boxes = raw_result.get("boxes") or polygons
    confidence_values = (
        raw_result.get("scores")
        or raw_result.get("score_text")
        or raw_result.get("confidences")
        or []
    )
    regions: list[TextRegion] = []
    for index, raw_polygon in enumerate(polygons):
        polygon = _normalize_polygon(raw_polygon)
        bbox = _bbox_from_polygon(polygon)
        confidence = _resolve_confidence(confidence_values, index)
        if not polygon and index < len(boxes):
            polygon = _normalize_polygon(boxes[index])
            bbox = _bbox_from_polygon(polygon)
        regions.append(
            TextRegion(
                region_id=f"region_{index + 1:04d}",
                polygon=polygon,
                bbox=bbox,
                confidence=confidence,
                reading_order=index,
                source_artifact_ref=source_artifact_ref,
                metadata={},
            )
        )
    return regions


def _normalize_polygon(raw_polygon: object) -> list[Point]:
    if raw_polygon is None:
        return []

    points: list[Point] = []
    for raw_point in list(raw_polygon):
        x, y = _coerce_point(raw_point)
        points.append(Point(x=float(x), y=float(y)))
    return points


def _coerce_point(raw_point: object) -> tuple[float, float]:
    if isinstance(raw_point, dict):
        return float(raw_point["x"]), float(raw_point["y"])
    if hasattr(raw_point, "tolist"):
        raw_point = raw_point.tolist()
    values = list(raw_point)
    if len(values) != 2:
        raise ValueError("CRAFT polygon point must contain exactly two coordinates")
    return float(values[0]), float(values[1])


def _bbox_from_polygon(polygon: list[Point]) -> dict[str, float]:
    if not polygon:
        return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    xs = [point.x for point in polygon]
    ys = [point.y for point in polygon]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return {
        "x": float(min_x),
        "y": float(min_y),
        "width": float(max_x - min_x),
        "height": float(max_y - min_y),
    }


def _resolve_confidence(confidence_values: object, index: int) -> Optional[float]:
    if confidence_values is None:
        return None
    if hasattr(confidence_values, "tolist"):
        confidence_values = confidence_values.tolist()
    values = list(confidence_values)
    if index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    return float(value)


def _write_text_regions_artifact(
    request: StageRequest,
    payload: TextRegionsPayload,
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    artifact_path = stage_dir / f"{run_slug}_text_regions.json"
    artifact_path.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/text_regions"
    )
    return ArtifactDescriptor(
        artifact_ref=artifact_ref,
        kind="text_regions",
        media_type=_TEXT_REGIONS_MEDIA_TYPE,
        uri=artifact_path.resolve().as_uri(),
        width=payload.image_width,
        height=payload.image_height,
        byte_size=artifact_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={
            "detector": payload.detector,
            "region_count": len(payload.regions),
            "source_artifact_ref": payload.source_artifact_ref,
        },
    )
def _detect_with_craft(image_path: str, config: dict[str, object]) -> dict[str, object]:
    try:
        from craft_text_detector import Craft
    except ImportError as exc:
        raise RuntimeError(
            "craft-text-detector is not installed. Use Dockerfile.inference or install requirements-craft.txt."
        ) from exc

    detector = Craft(
        output_dir=None,
        cuda=bool(config.get("cuda", False)),
    )
    try:
        return detector.detect_text(
            image=image_path,
            text_threshold=float(config.get("text_threshold", _DEFAULT_TEXT_THRESHOLD)),
            link_threshold=float(config.get("link_threshold", _DEFAULT_LINK_THRESHOLD)),
            low_text=float(config.get("low_text", _DEFAULT_LOW_TEXT)),
        )
    finally:
        unload_all = getattr(detector, "unload_all_models", None)
        if callable(unload_all):
            unload_all()
