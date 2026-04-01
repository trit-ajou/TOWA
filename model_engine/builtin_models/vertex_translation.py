from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Any, Callable, Optional

from ..adapters.callable import CallableModelAdapter
from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.credentials import BillingMode, CredentialSource
from ..contracts.document_ir import TextBlock
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus
from ..contracts.translated_text_blocks import TranslatedTextBlocksPayload
from ..models.registry import ModelRegistry
from ..storage import stage_run_slug, stage_transaction_dir


VERTEX_TRANSLATION_MODEL_ID = "builtin.vertex.translation"
VERTEX_TRANSLATION_DEFAULT_MODEL = "gemini-2.5-flash"
_TRANSLATED_TEXT_BLOCKS_MEDIA_TYPE = "application/json"


def build_vertex_translation_manifest() -> StageManifest:
    return StageManifest(
        model_id=VERTEX_TRANSLATION_MODEL_ID,
        adapter_id="adapter.builtin.vertex.translation",
        stage_kind=StageKind.TRANSLATION,
        required_artifact_kinds=[],
        produced_artifact_kinds=["translated_text_blocks"],
        allowed_credential_sources=[
            CredentialSource.USER_PERSONAL_PERSISTED,
            CredentialSource.USER_PERSONAL_SESSION,
            CredentialSource.PLATFORM_MANAGED,
        ],
        billing_modes=[BillingMode.USER_DIRECT, BillingMode.PLATFORM_CREDIT],
        resource_profile=ResourceProfile(
            cpu_threads=1,
            memory_mb=1024,
            gpu_required=False,
            latency_tier="network",
        ),
        custom_model=False,
        priority=50,
        display_name="Vertex Translation",
        tags=["builtin", "vertexai", "gemini", "translation"],
    )


def build_vertex_translation_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_vertex_translation_manifest(),
        import_path="model_engine.builtin_models.vertex_translation:vertex_translation_handler",
    )


def register_vertex_translation_model(registry: ModelRegistry) -> str:
    registry.register(build_vertex_translation_adapter())
    return VERTEX_TRANSLATION_MODEL_ID


def vertex_translation_handler(request: StageRequest) -> StageResponse:
    return run_vertex_translation(request)


def run_vertex_translation(
    request: StageRequest,
    *,
    translate_blocks_fn: Optional[
        Callable[[list[TextBlock], dict[str, object], str], object]
    ] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    source_blocks = _resolve_source_blocks(request)
    stage_config = dict(request.stage_config)
    model_name = str(stage_config.get("model_name", VERTEX_TRANSLATION_DEFAULT_MODEL))
    source_language = str(stage_config.get("source_language", "Japanese"))
    target_language = str(stage_config.get("target_language", "Korean"))

    request_provider = request.resolved_credentials.get("primary_provider")
    if request_provider is None:
        raise RuntimeError("Vertex translation requires primary_provider credentials")
    api_key = request_provider.secret("api_key")
    if not api_key:
        raise RuntimeError("Vertex translation requires an API key")

    translate_blocks_fn = translate_blocks_fn or _translate_blocks_with_vertex
    try:
        raw_translations = translate_blocks_fn(source_blocks, stage_config, api_key)
        translated_blocks, warnings, metrics = _apply_translations(
            source_blocks,
            raw_translations,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
        )
    except Exception as exc:
        return _failed_response(
            request,
            started_at=started_at,
            source_blocks=source_blocks,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            error=exc,
        )

    payload = TranslatedTextBlocksPayload(
        schema_version=request.schema_version,
        engine="vertex_gemini_translation",
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        blocks=translated_blocks,
        metadata=metrics,
    )
    artifact_descriptor = _write_translated_text_blocks_artifact(request, payload)
    status = (
        StageStatus.SUCCEEDED
        if metrics["missing_count"] == 0
        else StageStatus.PARTIAL
    )
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[artifact_descriptor.artifact_ref],
        warnings=warnings,
        metrics={
            "engine": payload.engine,
            "model_name": model_name,
            "source_language": source_language,
            "target_language": target_language,
            "source_block_count": metrics["source_block_count"],
            "translated_count": metrics["translated_count"],
            "missing_count": metrics["missing_count"],
        },
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=status,
        patches=[
            PatchOperation(
                op="replace_text_blocks",
                payload={"text_blocks": [asdict(block) for block in translated_blocks]},
            ),
            PatchOperation(
                op="set_stage_meta",
                payload={
                    "key": "translation",
                    "value": {
                        "engine": payload.engine,
                        "model_name": model_name,
                        "artifact_ref": artifact_descriptor.artifact_ref,
                        "source_language": source_language,
                        "target_language": target_language,
                        "translated_count": metrics["translated_count"],
                        "missing_count": metrics["missing_count"],
                    },
                },
            ),
        ],
        artifacts={artifact_descriptor.artifact_ref: artifact_descriptor},
        stage_report=report,
    )


def _resolve_source_blocks(request: StageRequest) -> list[TextBlock]:
    if not request.document.text_blocks:
        raise ValueError("Vertex translation requires at least one text block")
    return [block for block in request.document.text_blocks]


def _translate_blocks_with_vertex(
    blocks: list[TextBlock],
    config: dict[str, object],
    api_key: str,
) -> list[dict[str, str]]:
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Add it to the local environment or Docker image before running translation."
        ) from exc

    model_name = str(config.get("model_name", VERTEX_TRANSLATION_DEFAULT_MODEL))
    source_language = str(config.get("source_language", "Japanese"))
    target_language = str(config.get("target_language", "Korean"))
    temperature = float(config.get("temperature", 0.1))
    request_payload = {
        "source_language": source_language,
        "target_language": target_language,
        "blocks": [
            {
                "block_id": block.block_id,
                "source_lang_text": block.source_lang_text,
                "writing_mode": block.writing_mode,
                "speaker": block.speaker or "",
            }
            for block in blocks
        ],
    }
    prompt = (
        "Translate the following manga OCR text blocks. "
        "Return JSON only. "
        "Use the exact shape {\"translations\": [{\"block_id\": \"...\", \"translated_text\": \"...\"}]}. "
        "Do not omit blocks. Do not add explanations or markdown. "
        f"Source language: {source_language}. "
        f"Target language: {target_language}.\n\n"
        f"Input:\n{json.dumps(request_payload, ensure_ascii=False, indent=2)}"
    )

    client = genai.Client(vertexai=True, api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            "temperature": temperature,
            "response_mime_type": "application/json",
        },
    )
    response_text = _response_text(response)
    parsed = _parse_json_text(response_text)
    return _normalize_translation_entries(parsed)


def _response_text(response: object) -> str:
    direct_text = getattr(response, "text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    parts: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    if parts:
        return "\n".join(parts)
    raise RuntimeError("Vertex translation response did not include text output")


def _parse_json_text(raw_text: str) -> object:
    normalized = raw_text.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.removeprefix("json").strip()
    return json.loads(normalized)


def _normalize_translation_entries(payload: object) -> list[dict[str, str]]:
    items: object
    if isinstance(payload, dict):
        items = (
            payload.get("translations")
            or payload.get("blocks")
            or payload.get("results")
            or payload.get("items")
        )
    else:
        items = payload

    if not isinstance(items, list):
        raise ValueError("Vertex translation response must contain a list of translation entries")

    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Vertex translation entries must be JSON objects")
        normalized.append(
            {
                "block_id": str(item.get("block_id", "")).strip(),
                "translated_text": str(
                    item.get("translated_text", item.get("text", ""))
                ).strip(),
            }
        )
    return normalized


def _apply_translations(
    source_blocks: list[TextBlock],
    translation_entries: list[dict[str, str]],
    *,
    model_name: str,
    source_language: str,
    target_language: str,
) -> tuple[list[TextBlock], list[str], dict[str, Any]]:
    warnings: list[str] = []
    by_block_id = {
        entry["block_id"]: entry["translated_text"]
        for entry in translation_entries
        if entry["block_id"]
    }
    translated_blocks: list[TextBlock] = []
    translated_count = 0
    missing_count = 0
    used_positional_alignment = False

    for index, block in enumerate(source_blocks):
        translated_text = by_block_id.get(block.block_id, "")
        if not translated_text and index < len(translation_entries):
            positional_text = translation_entries[index]["translated_text"]
            if positional_text:
                translated_text = positional_text
                used_positional_alignment = True

        if translated_text:
            translated_count += 1
        else:
            missing_count += 1

        translated_blocks.append(
            TextBlock(
                block_id=block.block_id,
                source_lang_text=block.source_lang_text,
                translated_text=translated_text,
                polygon=list(block.polygon),
                bbox=dict(block.bbox),
                reading_order=block.reading_order,
                speaker=block.speaker,
                style_hint=dict(block.style_hint),
                font_hint=dict(block.font_hint),
                writing_mode=block.writing_mode,
                source_region_ref=block.source_region_ref,
            )
        )

    if used_positional_alignment:
        warnings.append("translation_result_positionally_aligned")
    if missing_count:
        warnings.append(f"translation_missing_count={missing_count}")

    return translated_blocks, warnings, {
        "engine": "vertex_gemini_translation",
        "model_name": model_name,
        "source_language": source_language,
        "target_language": target_language,
        "source_block_count": len(source_blocks),
        "translated_count": translated_count,
        "missing_count": missing_count,
    }


def _write_translated_text_blocks_artifact(
    request: StageRequest,
    payload: TranslatedTextBlocksPayload,
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    artifact_path = stage_dir / f"{run_slug}_translated_text_blocks.json"
    artifact_path.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/translated_text_blocks"
    )
    return ArtifactDescriptor(
        artifact_ref=artifact_ref,
        kind="translated_text_blocks",
        media_type=_TRANSLATED_TEXT_BLOCKS_MEDIA_TYPE,
        uri=artifact_path.resolve().as_uri(),
        byte_size=artifact_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={
            "engine": payload.engine,
            "model_name": payload.model_name,
            "source_language": payload.source_language,
            "target_language": payload.target_language,
            "translated_count": payload.metadata.get("translated_count", 0),
            "missing_count": payload.metadata.get("missing_count", 0),
        },
    )


def _failed_response(
    request: StageRequest,
    *,
    started_at: datetime,
    source_blocks: list[TextBlock],
    model_name: str,
    source_language: str,
    target_language: str,
    error: Exception,
) -> StageResponse:
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[],
        warnings=[],
        metrics={
            "engine": "vertex_gemini_translation",
            "model_name": model_name,
            "source_language": source_language,
            "target_language": target_language,
            "source_block_count": len(source_blocks),
        },
        provider=request.credential_bindings.get("primary_provider"),
        error_code=_error_code_for_exception(error),
        error_message=str(error),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        patches=[],
        artifacts={},
        stage_report=report,
    )


def _error_code_for_exception(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "provider_timeout"
    if isinstance(error, ValueError):
        return "translation_invalid_output"
    return "translation_provider_error"
