from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw

from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.inpaint_tasks import InpaintTask, InpaintTasksPayload
from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus
from ..contracts.text_regions import text_regions_payload_from_mapping


def run_mask_or_erase_planning(request: StageRequest) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    source_artifact = _resolve_bitmap_artifact(request)
    regions_artifact = _resolve_text_regions_artifact(request)
    text_regions = text_regions_payload_from_mapping(
        json.loads(_file_path_from_uri(regions_artifact.uri).read_text(encoding="utf-8"))
    )
    source_path = _file_path_from_uri(source_artifact.uri)
    with Image.open(source_path) as image:
        image_width, image_height = image.size

    target_layer_id = str(request.stage_config.get("target_layer_id", "layer_inpainting"))
    padding = int(request.stage_config.get("padding", 12))
    prompt = str(
        request.stage_config.get(
            "prompt",
            (
                "Use image 1 as the original manga page and image 2 as the edit guide. "
                "White areas in image 2 mark regions to edit, black areas must remain unchanged. "
                "Remove all visible source text, speech balloon text, and sound effects only inside the "
                "white regions. Reconstruct the underlying manga background, lineart, screentones, and "
                "balloon interiors naturally. Do not add any new text. Preserve composition, character art, "
                "panel borders, and all pixels outside the mask as faithfully as possible."
            ),
        )
    )

    tasks: list[InpaintTask] = []
    artifacts: dict[str, ArtifactDescriptor] = {}
    workspace_dir = _workspace_path(request)
    stage_dir = workspace_dir / request.pipeline_id / request.stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)

    for index, region in enumerate(text_regions.regions, start=1):
        expanded_bbox = _expand_bbox(region.bbox, image_width, image_height, padding)
        crop_bbox = _crop_bbox(region.bbox, image_width, image_height)
        mask_path = stage_dir / f"{request.stage_run_id.replace(':', '_')}_mask_{index:04d}.png"
        _write_mask(mask_path, expanded_bbox, region.polygon, region.bbox)
        mask_ref = (
            f"artifact://{request.pipeline_id}/{request.stage_name}/"
            f"{request.stage_run_id.replace(':', '_')}/mask/{index:04d}"
        )
        artifacts[mask_ref] = ArtifactDescriptor(
            artifact_ref=mask_ref,
            kind="erase_mask",
            media_type="image/png",
            uri=mask_path.resolve().as_uri(),
            width=expanded_bbox["width"],
            height=expanded_bbox["height"],
            byte_size=mask_path.stat().st_size,
            producer_stage=request.stage_name,
            metadata={
                "task_index": index,
                "target_layer_id": target_layer_id,
                "region_id": region.region_id,
            },
        )
        tasks.append(
            InpaintTask(
                task_id=f"task_{index:04d}",
                source_artifact_ref=source_artifact.artifact_ref,
                text_region_refs=[region.region_id],
                crop_bbox=crop_bbox,
                expanded_bbox=expanded_bbox,
                mask_artifact_ref=mask_ref,
                target_layer_id=target_layer_id,
                provider_params={"prompt": prompt},
            )
        )

    tasks_payload = InpaintTasksPayload(
        schema_version=request.schema_version,
        planner="rule_based_v1",
        source_artifact_ref=source_artifact.artifact_ref,
        target_layer_id=target_layer_id,
        tasks=tasks,
        metadata={"region_count": len(text_regions.regions), "padding": padding},
    )
    tasks_path = stage_dir / f"{request.stage_run_id.replace(':', '_')}_inpaint_tasks.json"
    tasks_path.write_text(
        json.dumps(tasks_payload.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    tasks_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/"
        f"{request.stage_run_id.replace(':', '_')}/inpaint_tasks"
    )
    artifacts[tasks_ref] = ArtifactDescriptor(
        artifact_ref=tasks_ref,
        kind="inpaint_tasks",
        media_type="application/json",
        uri=tasks_path.resolve().as_uri(),
        byte_size=tasks_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={
            "task_count": len(tasks),
            "target_layer_id": target_layer_id,
            "source_artifact_ref": source_artifact.artifact_ref,
        },
    )
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=sorted(artifacts.keys()),
        warnings=[],
        metrics={
            "planner": "rule_based_v1",
            "task_count": len(tasks),
            "target_layer_id": target_layer_id,
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
                    "key": "mask_or_erase_planning",
                    "value": {
                        "planner": "rule_based_v1",
                        "task_count": len(tasks),
                        "inpaint_tasks_ref": tasks_ref,
                        "target_layer_id": target_layer_id,
                    },
                },
            )
        ],
        artifacts=artifacts,
        stage_report=report,
    )


def _resolve_bitmap_artifact(request: StageRequest) -> ArtifactDescriptor:
    preferred_ref = request.stage_config.get("input_artifact_ref")
    if isinstance(preferred_ref, str):
        artifact = request.artifacts.get(preferred_ref)
        if artifact is None:
            raise KeyError(f"Configured input_artifact_ref not found: {preferred_ref}")
        return artifact
    for artifact in request.artifacts.values():
        if artifact.kind == "bitmap":
            return artifact
    raise ValueError("mask_or_erase_planning requires a bitmap artifact")


def _resolve_text_regions_artifact(request: StageRequest) -> ArtifactDescriptor:
    preferred_ref = request.stage_config.get("text_regions_artifact_ref")
    if isinstance(preferred_ref, str):
        artifact = request.artifacts.get(preferred_ref)
        if artifact is None:
            raise KeyError(f"Configured text_regions_artifact_ref not found: {preferred_ref}")
        return artifact
    for artifact in request.artifacts.values():
        if artifact.kind == "text_regions":
            return artifact
    raise ValueError("mask_or_erase_planning requires a text_regions artifact")


def _workspace_path(request: StageRequest) -> Path:
    if request.runtime_context is None:
        return Path("/tmp/towa/workspace")
    parsed = urlparse(request.runtime_context.workspace_uri)
    if parsed.scheme != "file":
        raise RuntimeError("mask_or_erase_planning requires file:// workspace_uri")
    return Path(parsed.path)


def _file_path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise RuntimeError("mask_or_erase_planning currently supports only file:// artifacts")
    return Path(parsed.path)


def _expand_bbox(
    bbox: dict[str, float],
    image_width: int,
    image_height: int,
    padding: int,
) -> dict[str, int]:
    x = int(max(0, bbox.get("x", 0.0) - padding))
    y = int(max(0, bbox.get("y", 0.0) - padding))
    right = int(min(image_width, bbox.get("x", 0.0) + bbox.get("width", 0.0) + padding))
    bottom = int(min(image_height, bbox.get("y", 0.0) + bbox.get("height", 0.0) + padding))
    return {"x": x, "y": y, "width": max(1, right - x), "height": max(1, bottom - y)}


def _crop_bbox(
    bbox: dict[str, float],
    image_width: int,
    image_height: int,
) -> dict[str, int]:
    x = int(max(0, bbox.get("x", 0.0)))
    y = int(max(0, bbox.get("y", 0.0)))
    right = int(min(image_width, bbox.get("x", 0.0) + bbox.get("width", 0.0)))
    bottom = int(min(image_height, bbox.get("y", 0.0) + bbox.get("height", 0.0)))
    return {"x": x, "y": y, "width": max(1, right - x), "height": max(1, bottom - y)}


def _write_mask(
    mask_path: Path,
    expanded_bbox: dict[str, int],
    polygon: list[object],
    bbox: dict[str, float],
) -> None:
    mask = Image.new("L", (expanded_bbox["width"], expanded_bbox["height"]), color=0)
    draw = ImageDraw.Draw(mask)
    relative_polygon = [
        (
            point.x - expanded_bbox["x"],
            point.y - expanded_bbox["y"],
        )
        for point in polygon
    ]
    if relative_polygon:
        draw.polygon(relative_polygon, fill=255)
    else:
        left = bbox.get("x", 0.0) - expanded_bbox["x"]
        top = bbox.get("y", 0.0) - expanded_bbox["y"]
        right = left + bbox.get("width", 0.0)
        bottom = top + bbox.get("height", 0.0)
        draw.rectangle((left, top, right, bottom), fill=255)
    mask.save(mask_path)
