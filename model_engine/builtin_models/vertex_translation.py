from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Callable, Optional

from ..adapters.callable import CallableModelAdapter
from ..contracts.credentials import BillingMode, CredentialSource
from ..contracts.document_ir import TextBlock
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.stages import StageRequest, StageResponse
from ..models.registry import ModelRegistry
from .translation_common import (
    apply_translations,
    build_failed_translation_response,
    build_translation_success_response,
    resolve_source_blocks,
)


VERTEX_TRANSLATION_MODEL_ID = "builtin.vertex.translation"
VERTEX_TRANSLATION_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"


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
    source_blocks = resolve_source_blocks(request, engine_name="Vertex translation")
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
        translated_blocks, warnings, metrics = apply_translations(
            source_blocks,
            raw_translations,
            engine="vertex_gemini_translation",
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
        )
    except Exception as exc:
        return build_failed_translation_response(
            request,
            engine="vertex_gemini_translation",
            started_at=started_at,
            source_blocks=source_blocks,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            provider=request.credential_bindings.get("primary_provider"),
            error=exc,
        )

    return build_translation_success_response(
        request,
        engine="vertex_gemini_translation",
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        translated_blocks=translated_blocks,
        warnings=warnings,
        metrics=metrics,
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
    )


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
