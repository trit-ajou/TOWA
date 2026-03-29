from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


JsonValue = Any


@dataclass
class Point:
    x: float
    y: float


SelectionShape = list[Point]
Selection = list[SelectionShape]


@dataclass
class Transform:
    scale: float = 1.0
    rotation: float = 0.0
    mirror_x: bool = False
    mirror_y: bool = False


@dataclass
class FilterSettings:
    enabled: bool = False
    blend_mode: str = "normal"
    opacity: float = 1.0
    gamma: float = 1.0
    brightness: float = 0.0
    contrast: float = 0.0
    vibrance: float = 0.0
    threshold: float = 0.0
    desaturate: bool = False
    invert: bool = False
    duotone_enabled: bool = False
    duotone_color_1: Optional[str] = None
    duotone_color_2: Optional[str] = None


@dataclass
class TextStyle:
    value: str = ""
    font: str = ""
    size: float = 0.0
    unit: str = "px"
    line_height: float = 1.0
    spacing: float = 0.0
    color: str = "#000000"


@dataclass
class TextBlock:
    block_id: str
    source_lang_text: str = ""
    translated_text: str = ""
    polygon: SelectionShape = field(default_factory=list)
    bbox: dict[str, float] = field(default_factory=dict)
    reading_order: Optional[int] = None
    speaker: Optional[str] = None
    style_hint: dict[str, JsonValue] = field(default_factory=dict)
    font_hint: dict[str, JsonValue] = field(default_factory=dict)
    writing_mode: str = "horizontal"
    source_region_ref: Optional[str] = None


@dataclass
class LayerIR:
    id: str
    name: str
    type: str
    left: float
    top: float
    width: float
    height: float
    visible: bool = True
    transparent: bool = True
    source_ref: Optional[str] = None
    mask_ref: Optional[str] = None
    transform: Transform = field(default_factory=Transform)
    filters: FilterSettings = field(default_factory=FilterSettings)
    text: TextStyle = field(default_factory=TextStyle)
    props: dict[str, JsonValue] = field(default_factory=dict)


@dataclass
class DocumentIR:
    id: str
    name: str
    width: int
    height: int
    layers: list[LayerIR] = field(default_factory=list)
    selections: dict[str, Selection] = field(default_factory=dict)
    active_selection: Selection = field(default_factory=list)
    invert_selection: bool = False
    text_blocks: list[TextBlock] = field(default_factory=list)
    stage_meta: dict[str, JsonValue] = field(default_factory=dict)

    def clone(self) -> "DocumentIR":
        return deepcopy(self)

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)

    def get_layer(self, layer_id: str) -> Optional[LayerIR]:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def require_layer(self, layer_id: str) -> LayerIR:
        layer = self.get_layer(layer_id)
        if layer is None:
            raise KeyError(f"Unknown layer_id: {layer_id}")
        return layer

    def remove_layer(self, layer_id: str) -> LayerIR:
        for index, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return self.layers.pop(index)
        raise KeyError(f"Unknown layer_id: {layer_id}")


def layer_from_mapping(payload: dict[str, JsonValue]) -> LayerIR:
    """Normalize loose payloads into the canonical layer dataclass."""

    transform_payload = payload.get("transform", {})
    filters_payload = payload.get("filters", {})
    text_payload = payload.get("text", {})
    return LayerIR(
        id=str(payload["id"]),
        name=str(payload["name"]),
        type=str(payload["type"]),
        left=float(payload.get("left", 0)),
        top=float(payload.get("top", 0)),
        width=float(payload["width"]),
        height=float(payload["height"]),
        visible=bool(payload.get("visible", True)),
        transparent=bool(payload.get("transparent", True)),
        source_ref=payload.get("source_ref"),
        mask_ref=payload.get("mask_ref"),
        transform=Transform(
            scale=float(transform_payload.get("scale", 1.0)),
            rotation=float(transform_payload.get("rotation", 0.0)),
            mirror_x=bool(transform_payload.get("mirror_x", transform_payload.get("mirrorX", False))),
            mirror_y=bool(transform_payload.get("mirror_y", transform_payload.get("mirrorY", False))),
        ),
        filters=FilterSettings(
            enabled=bool(filters_payload.get("enabled", False)),
            blend_mode=str(filters_payload.get("blend_mode", filters_payload.get("blendMode", "normal"))),
            opacity=float(filters_payload.get("opacity", 1.0)),
            gamma=float(filters_payload.get("gamma", 1.0)),
            brightness=float(filters_payload.get("brightness", 0.0)),
            contrast=float(filters_payload.get("contrast", 0.0)),
            vibrance=float(filters_payload.get("vibrance", 0.0)),
            threshold=float(filters_payload.get("threshold", 0.0)),
            desaturate=bool(filters_payload.get("desaturate", False)),
            invert=bool(filters_payload.get("invert", False)),
            duotone_enabled=bool(filters_payload.get("duotone_enabled", filters_payload.get("duotoneEnabled", False))),
            duotone_color_1=filters_payload.get("duotone_color_1", filters_payload.get("duotoneColor1")),
            duotone_color_2=filters_payload.get("duotone_color_2", filters_payload.get("duotoneColor2")),
        ),
        text=TextStyle(
            value=str(text_payload.get("value", "")),
            font=str(text_payload.get("font", "")),
            size=float(text_payload.get("size", 0.0)),
            unit=str(text_payload.get("unit", "px")),
            line_height=float(text_payload.get("line_height", text_payload.get("lineHeight", 1.0))),
            spacing=float(text_payload.get("spacing", 0.0)),
            color=str(text_payload.get("color", "#000000")),
        ),
        props=dict(payload.get("props", {})),
    )


def text_block_from_mapping(payload: dict[str, JsonValue]) -> TextBlock:
    polygon = [
        Point(x=float(point["x"]), y=float(point["y"]))
        for point in payload.get("polygon", [])
    ]
    return TextBlock(
        block_id=str(payload["block_id"]),
        source_lang_text=str(payload.get("source_lang_text", "")),
        translated_text=str(payload.get("translated_text", "")),
        polygon=polygon,
        bbox=dict(payload.get("bbox", {})),
        reading_order=payload.get("reading_order"),
        speaker=payload.get("speaker"),
        style_hint=dict(payload.get("style_hint", {})),
        font_hint=dict(payload.get("font_hint", {})),
        writing_mode=str(payload.get("writing_mode", "horizontal")),
        source_region_ref=payload.get("source_region_ref"),
    )
