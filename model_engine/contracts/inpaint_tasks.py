from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


JsonValue = Any


@dataclass
class InpaintTask:
    task_id: str
    source_artifact_ref: str
    text_region_refs: list[str] = field(default_factory=list)
    crop_bbox: dict[str, int] = field(default_factory=dict)
    expanded_bbox: dict[str, int] = field(default_factory=dict)
    mask_artifact_ref: str = ""
    target_layer_id: str = "layer_inpainting"
    composite_mode: str = "replace"
    provider_params: dict[str, JsonValue] = field(default_factory=dict)


@dataclass
class InpaintTasksPayload:
    schema_version: str
    planner: str
    source_artifact_ref: str
    target_layer_id: str
    tasks: list[InpaintTask] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


def inpaint_task_from_mapping(payload: dict[str, JsonValue]) -> InpaintTask:
    return InpaintTask(
        task_id=str(payload["task_id"]),
        source_artifact_ref=str(payload["source_artifact_ref"]),
        text_region_refs=[str(item) for item in payload.get("text_region_refs", [])],
        crop_bbox={key: int(value) for key, value in dict(payload.get("crop_bbox", {})).items()},
        expanded_bbox={key: int(value) for key, value in dict(payload.get("expanded_bbox", {})).items()},
        mask_artifact_ref=str(payload.get("mask_artifact_ref", "")),
        target_layer_id=str(payload.get("target_layer_id", "layer_inpainting")),
        composite_mode=str(payload.get("composite_mode", "replace")),
        provider_params=dict(payload.get("provider_params", {})),
    )


def inpaint_tasks_payload_from_mapping(payload: dict[str, JsonValue]) -> InpaintTasksPayload:
    return InpaintTasksPayload(
        schema_version=str(payload.get("schema_version", "v1")),
        planner=str(payload["planner"]),
        source_artifact_ref=str(payload["source_artifact_ref"]),
        target_layer_id=str(payload["target_layer_id"]),
        tasks=[inpaint_task_from_mapping(item) for item in payload.get("tasks", [])],
        metadata=dict(payload.get("metadata", {})),
    )
