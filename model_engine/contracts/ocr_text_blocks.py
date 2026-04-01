from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .document_ir import TextBlock, text_block_from_mapping


JsonValue = Any


@dataclass
class OcrTextBlocksPayload:
    schema_version: str
    engine: str
    source_artifact_ref: str
    text_regions_artifact_ref: str
    blocks: list[TextBlock] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


def ocr_text_blocks_payload_from_mapping(payload: dict[str, JsonValue]) -> OcrTextBlocksPayload:
    return OcrTextBlocksPayload(
        schema_version=str(payload.get("schema_version", "v1")),
        engine=str(payload["engine"]),
        source_artifact_ref=str(payload["source_artifact_ref"]),
        text_regions_artifact_ref=str(payload["text_regions_artifact_ref"]),
        blocks=[text_block_from_mapping(item) for item in payload.get("blocks", [])],
        metadata=dict(payload.get("metadata", {})),
    )
