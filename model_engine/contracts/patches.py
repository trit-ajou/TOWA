from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from .document_ir import (
    DocumentIR,
    Selection,
    TextStyle,
    Transform,
    FilterSettings,
    layer_from_mapping,
    text_block_from_mapping,
)


class PatchOp(str, Enum):
    ADD_LAYER = "add_layer"
    REMOVE_LAYER = "remove_layer"
    UPDATE_LAYER_PROPS = "update_layer_props"
    REPLACE_SOURCE_REF = "replace_source_ref"
    REPLACE_MASK_REF = "replace_mask_ref"
    SET_LAYER_TEXT = "set_layer_text"
    SET_LAYER_TRANSFORM = "set_layer_transform"
    SET_LAYER_FILTERS = "set_layer_filters"
    SET_DOCUMENT_SELECTION = "set_document_selection"
    APPEND_TEXT_BLOCKS = "append_text_blocks"
    SET_STAGE_META = "set_stage_meta"
    ATTACH_ARTIFACT = "attach_artifact"
    DETACH_ARTIFACT = "detach_artifact"


@dataclass
class PatchOperation:
    op: Union[PatchOp, str]
    target: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.op, PatchOp):
            self.op = PatchOp(self.op)

    def apply(self, document: DocumentIR) -> None:
        apply_patch(document, self)


def apply_patches(document: DocumentIR, patches: list[PatchOperation]) -> DocumentIR:
    for patch in patches:
        patch.apply(document)
    return document


def apply_patch(document: DocumentIR, patch: PatchOperation) -> None:
    op = patch.op

    if op is PatchOp.ADD_LAYER:
        layer_payload = patch.payload["layer"]
        layer = layer_from_mapping(layer_payload) if isinstance(layer_payload, dict) else layer_payload
        document.layers.append(layer)
        return

    if op is PatchOp.REMOVE_LAYER:
        document.remove_layer(str(patch.target["layer_id"]))
        return

    if op is PatchOp.UPDATE_LAYER_PROPS:
        layer = document.require_layer(str(patch.target["layer_id"]))
        allowed = {"name", "left", "top", "width", "height", "visible", "transparent", "type"}
        for key, value in patch.payload.items():
            if key not in allowed:
                raise ValueError(f"Unsupported property for update_layer_props: {key}")
            setattr(layer, key, value)
        return

    if op is PatchOp.REPLACE_SOURCE_REF:
        layer = document.require_layer(str(patch.target["layer_id"]))
        layer.source_ref = patch.payload["source_ref"]
        return

    if op is PatchOp.REPLACE_MASK_REF:
        layer = document.require_layer(str(patch.target["layer_id"]))
        layer.mask_ref = patch.payload["mask_ref"]
        return

    if op is PatchOp.SET_LAYER_TEXT:
        layer = document.require_layer(str(patch.target["layer_id"]))
        payload = patch.payload["text"]
        layer.text = TextStyle(
            value=str(payload.get("value", "")),
            font=str(payload.get("font", "")),
            size=float(payload.get("size", 0.0)),
            unit=str(payload.get("unit", "px")),
            line_height=float(payload.get("line_height", payload.get("lineHeight", 1.0))),
            spacing=float(payload.get("spacing", 0.0)),
            color=str(payload.get("color", "#000000")),
        )
        return

    if op is PatchOp.SET_LAYER_TRANSFORM:
        layer = document.require_layer(str(patch.target["layer_id"]))
        payload = patch.payload["transform"]
        layer.transform = Transform(
            scale=float(payload.get("scale", 1.0)),
            rotation=float(payload.get("rotation", 0.0)),
            mirror_x=bool(payload.get("mirror_x", payload.get("mirrorX", False))),
            mirror_y=bool(payload.get("mirror_y", payload.get("mirrorY", False))),
        )
        return

    if op is PatchOp.SET_LAYER_FILTERS:
        layer = document.require_layer(str(patch.target["layer_id"]))
        payload = patch.payload["filters"]
        layer.filters = FilterSettings(
            enabled=bool(payload.get("enabled", False)),
            blend_mode=str(payload.get("blend_mode", payload.get("blendMode", "normal"))),
            opacity=float(payload.get("opacity", 1.0)),
            gamma=float(payload.get("gamma", 1.0)),
            brightness=float(payload.get("brightness", 0.0)),
            contrast=float(payload.get("contrast", 0.0)),
            vibrance=float(payload.get("vibrance", 0.0)),
            threshold=float(payload.get("threshold", 0.0)),
            desaturate=bool(payload.get("desaturate", False)),
            invert=bool(payload.get("invert", False)),
            duotone_enabled=bool(payload.get("duotone_enabled", payload.get("duotoneEnabled", False))),
            duotone_color_1=payload.get("duotone_color_1", payload.get("duotoneColor1")),
            duotone_color_2=payload.get("duotone_color_2", payload.get("duotoneColor2")),
        )
        return

    if op is PatchOp.SET_DOCUMENT_SELECTION:
        selections = patch.payload.get("selections", document.selections)
        active_selection = patch.payload.get("active_selection", patch.payload.get("activeSelection"))
        invert_selection = patch.payload.get("invert_selection", patch.payload.get("invertSelection"))
        document.selections = selections
        if active_selection is not None:
            document.active_selection = active_selection
        if invert_selection is not None:
            document.invert_selection = bool(invert_selection)
        return

    if op is PatchOp.APPEND_TEXT_BLOCKS:
        blocks = patch.payload.get("text_blocks", [])
        for block in blocks:
            normalized = text_block_from_mapping(block) if isinstance(block, dict) else block
            document.text_blocks.append(normalized)
        return

    if op is PatchOp.SET_STAGE_META:
        meta_key = str(patch.payload["key"])
        document.stage_meta[meta_key] = patch.payload.get("value")
        return

    if op is PatchOp.ATTACH_ARTIFACT:
        attachments = document.stage_meta.setdefault("attached_artifacts", {})
        attachments[str(patch.payload["name"])] = patch.payload["artifact_ref"]
        return

    if op is PatchOp.DETACH_ARTIFACT:
        attachments = document.stage_meta.setdefault("attached_artifacts", {})
        name = str(patch.payload["name"])
        attachments.pop(name, None)
        return

    raise ValueError(f"Unsupported patch op: {op}")
