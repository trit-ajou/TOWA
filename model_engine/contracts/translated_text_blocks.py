from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .document_ir import TextBlock, text_block_from_mapping


JsonValue = Any


@dataclass
class TranslatedTextBlocksPayload:
    schema_version: str
    engine: str
    model_name: str
    source_language: str
    target_language: str
    blocks: list[TextBlock] = field(default_factory=list)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


def translated_text_blocks_payload_from_mapping(
    payload: dict[str, JsonValue]
) -> TranslatedTextBlocksPayload:
    return TranslatedTextBlocksPayload(
        schema_version=str(payload.get("schema_version", "v1")),
        engine=str(payload["engine"]),
        model_name=str(payload["model_name"]),
        source_language=str(payload["source_language"]),
        target_language=str(payload["target_language"]),
        blocks=[text_block_from_mapping(item) for item in payload.get("blocks", [])],
        metadata=dict(payload.get("metadata", {})),
    )
