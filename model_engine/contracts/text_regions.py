from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .document_ir import Point, SelectionShape


JsonValue = Any


@dataclass
class TextRegion:
    region_id: str
    polygon: SelectionShape = field(default_factory=list)
    bbox: dict[str, float] = field(default_factory=dict)
    confidence: Optional[float] = None
    reading_order: Optional[int] = None
    source_artifact_ref: Optional[str] = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass
class TextRegionsPayload:
    schema_version: str
    detector: str
    source_artifact_ref: str
    image_width: int
    image_height: int
    regions: list[TextRegion] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


def text_region_from_mapping(payload: dict[str, JsonValue]) -> TextRegion:
    polygon = [
        Point(x=float(point["x"]), y=float(point["y"]))
        for point in payload.get("polygon", [])
    ]
    return TextRegion(
        region_id=str(payload["region_id"]),
        polygon=polygon,
        bbox={key: float(value) for key, value in dict(payload.get("bbox", {})).items()},
        confidence=_optional_float(payload.get("confidence")),
        reading_order=payload.get("reading_order"),
        source_artifact_ref=payload.get("source_artifact_ref"),
        metadata=dict(payload.get("metadata", {})),
    )


def text_regions_payload_from_mapping(payload: dict[str, JsonValue]) -> TextRegionsPayload:
    return TextRegionsPayload(
        schema_version=str(payload.get("schema_version", "v1")),
        detector=str(payload["detector"]),
        source_artifact_ref=str(payload["source_artifact_ref"]),
        image_width=int(payload["image_width"]),
        image_height=int(payload["image_height"]),
        regions=[
            text_region_from_mapping(item)
            for item in payload.get("regions", [])
        ],
        metadata=dict(payload.get("metadata", {})),
    )


def _optional_float(value: object) -> Optional[float]:
    if value is None:
        return None
    return float(value)
