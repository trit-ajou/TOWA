from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Callable, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

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
)
from .translation_common import resolve_source_blocks


OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID = "builtin.openai_compatible.translation"
OPENAI_COMPATIBLE_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
OPENAI_COMPATIBLE_DEFAULT_MODEL = "local-model"


def build_openai_compatible_translation_manifest() -> StageManifest:
    return StageManifest(
        model_id=OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
        adapter_id="adapter.builtin.openai_compatible.translation",
        stage_kind=StageKind.TRANSLATION,
        required_artifact_kinds=[],
        produced_artifact_kinds=["translated_text_blocks"],
        allowed_credential_sources=[
            CredentialSource.NONE,
            CredentialSource.USER_PERSONAL_PERSISTED,
            CredentialSource.USER_PERSONAL_SESSION,
            CredentialSource.PLATFORM_MANAGED,
        ],
        billing_modes=[
            BillingMode.NONE,
            BillingMode.USER_DIRECT,
            BillingMode.PLATFORM_CREDIT,
        ],
        resource_profile=ResourceProfile(
            cpu_threads=1,
            memory_mb=512,
            gpu_required=False,
            latency_tier="network",
        ),
        custom_model=False,
        priority=45,
        display_name="OpenAI-compatible Translation",
        tags=["builtin", "openai-compatible", "lmstudio", "ollama", "custom-proxy", "translation"],
    )


def build_openai_compatible_translation_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_openai_compatible_translation_manifest(),
        import_path=(
            "model_engine.builtin_models.openai_compatible_translation:"
            "openai_compatible_translation_handler"
        ),
    )


def register_openai_compatible_translation_model(registry: ModelRegistry) -> str:
    registry.register(build_openai_compatible_translation_adapter())
    return OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID


def openai_compatible_translation_handler(request: StageRequest) -> StageResponse:
    return run_openai_compatible_translation(request)


def run_openai_compatible_translation(
    request: StageRequest,
    *,
    translate_blocks_fn: Optional[
        Callable[[list[TextBlock], dict[str, object], Optional[str]], object]
    ] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    source_blocks = resolve_source_blocks(request, engine_name="OpenAI-compatible translation")
    stage_config = dict(request.stage_config)
    model_name = str(stage_config.get("model_name") or OPENAI_COMPATIBLE_DEFAULT_MODEL)
    source_language = str(stage_config.get("source_language", "Japanese"))
    target_language = str(stage_config.get("target_language", "Korean"))
    api_key = _optional_api_key(request)
    if not api_key:
        config_api_key = stage_config.get("api_key")
        if config_api_key:
            api_key = str(config_api_key)

    translate_blocks_fn = translate_blocks_fn or _translate_blocks_with_openai_compatible
    try:
        raw_translations = translate_blocks_fn(source_blocks, stage_config, api_key)
        translated_blocks, warnings, metrics = apply_translations(
            source_blocks,
            raw_translations,
            engine="openai_compatible_translation",
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
        )
    except Exception as exc:
        return build_failed_translation_response(
            request,
            engine="openai_compatible_translation",
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
        engine="openai_compatible_translation",
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        translated_blocks=translated_blocks,
        warnings=warnings,
        metrics=metrics,
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
    )


def _optional_api_key(request: StageRequest) -> Optional[str]:
    provider = request.resolved_credentials.get("primary_provider")
    if provider is None:
        return None
    api_key = provider.secret("api_key")
    return api_key if api_key else None


def _translate_blocks_with_openai_compatible(
    blocks: list[TextBlock],
    config: dict[str, object],
    api_key: Optional[str],
) -> list[dict[str, str]]:
    model_name = str(config.get("model_name") or OPENAI_COMPATIBLE_DEFAULT_MODEL)
    base_url = str(config.get("base_url") or OPENAI_COMPATIBLE_DEFAULT_BASE_URL)
    source_language = str(config.get("source_language", "Japanese"))
    target_language = str(config.get("target_language", "Korean"))
    temperature = float(config.get("temperature", 0.1))
    timeout_seconds = float(config.get("timeout_seconds", 300))

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
    body: dict[str, object] = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You translate manga OCR text blocks. Return JSON only, with the exact "
                    "shape {\"translations\": [{\"block_id\": \"...\", \"translated_text\": \"...\"}]}. "
                    "Preserve block_id values. Do not omit blocks. Do not add markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Source language: {source_language}\n"
                    f"Target language: {target_language}\n\n"
                    f"Input:\n{json.dumps(request_payload, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
        "temperature": temperature,
    }
    if "max_tokens" in config:
        body["max_tokens"] = int(config["max_tokens"])  # OpenAI-compatible common field.
    if bool(config.get("response_format_json")):
        body["response_format"] = {"type": "json_object"}

    response_payload = _post_chat_completions(
        base_url=base_url,
        body=body,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    response_text = _chat_completion_response_text(response_payload)
    parsed = _parse_json_text(response_text)
    return _normalize_translation_entries(parsed)


def _post_chat_completions(
    *,
    base_url: str,
    body: dict[str, object],
    api_key: Optional[str],
    timeout_seconds: float,
) -> object:
    endpoint = _chat_completions_url(base_url)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urlrequest.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI-compatible translation request failed: status={exc.code} body={detail}"
        ) from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"OpenAI-compatible translation endpoint unavailable: {exc}") from exc
    return json.loads(response_body)


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _chat_completion_response_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("OpenAI-compatible response must be a JSON object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible response must include choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("OpenAI-compatible choice must be a JSON object")
    message = choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    text = choice.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise RuntimeError("OpenAI-compatible response did not include text output")


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
        raise ValueError("OpenAI-compatible response must contain a list of translation entries")

    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("OpenAI-compatible translation entries must be JSON objects")
        normalized.append(
            {
                "block_id": str(item.get("block_id", "")).strip(),
                "translated_text": str(
                    item.get("translated_text", item.get("text", ""))
                ).strip(),
            }
        )
    return normalized
