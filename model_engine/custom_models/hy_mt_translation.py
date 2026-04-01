from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ..contracts.stages import StageRequest, StageResponse
from ..builtin_models.translation_common import (
    apply_translations,
    build_failed_translation_response,
    build_translation_success_response,
    resolve_source_blocks,
)


HY_MT_TRANSLATION_DEFAULT_MODEL = "tencent/HY-MT1.5-1.8B"

_MODEL_CACHE: dict[str, tuple[object, object]] = {}


def hy_mt_translation_handler(request: StageRequest) -> StageResponse:
    return run_hy_mt_translation(request)


def preload_hy_mt_model(
    *,
    model_name_or_path: str = HY_MT_TRANSLATION_DEFAULT_MODEL,
) -> None:
    _load_model_bundle(model_name_or_path)


def run_hy_mt_translation(
    request: StageRequest,
    *,
    translate_blocks_fn: Optional[
        Callable[[list[object], dict[str, object]], list[dict[str, str]]]
    ] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    source_blocks = resolve_source_blocks(request, engine_name="HY-MT translation")
    stage_config = dict(request.stage_config)
    model_name = str(stage_config.get("model_name", HY_MT_TRANSLATION_DEFAULT_MODEL))
    source_language = str(stage_config.get("source_language", "Japanese"))
    target_language = str(stage_config.get("target_language", "Korean"))

    translate_blocks_fn = translate_blocks_fn or _translate_blocks_with_hy_mt
    try:
        raw_translations = translate_blocks_fn(source_blocks, stage_config)
        translated_blocks, warnings, metrics = apply_translations(
            source_blocks,
            raw_translations,
            engine="hy_mt_translation",
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
        )
    except Exception as exc:
        return build_failed_translation_response(
            request,
            engine="hy_mt_translation",
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            source_blocks=source_blocks,
            provider=request.credential_bindings.get("primary_provider"),
            started_at=started_at,
            error=exc,
        )

    return build_translation_success_response(
        request,
        engine="hy_mt_translation",
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        translated_blocks=translated_blocks,
        warnings=warnings,
        metrics=metrics,
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
    )


def _translate_blocks_with_hy_mt(
    blocks: list[object],
    config: dict[str, object],
) -> list[dict[str, str]]:
    model_name = str(config.get("model_name", HY_MT_TRANSLATION_DEFAULT_MODEL))
    max_new_tokens = int(config.get("max_new_tokens", 256))
    temperature = float(config.get("temperature", 0.0))
    top_p = float(config.get("top_p", 0.9))
    top_k = int(config.get("top_k", 20))
    repetition_penalty = float(config.get("repetition_penalty", 1.05))

    model, tokenizer = _load_model_bundle(model_name)
    device = getattr(model, "device", None)
    results: list[dict[str, str]] = []

    for block in blocks:
        prompt = _build_translation_prompt(
            source_text=str(block.source_lang_text),
            source_language=str(config.get("source_language", "Japanese")),
            target_language=str(config.get("target_language", "Korean")),
            writing_mode=str(block.writing_mode or ""),
        )
        input_ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=True,
            add_generation_prompt=False,
            return_tensors="pt",
        )
        if device is not None and hasattr(input_ids, "to"):
            input_ids = input_ids.to(device)

        generate_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": temperature > 0,
            "temperature": max(temperature, 1e-5),
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "pad_token_id": getattr(tokenizer, "pad_token_id", None)
            or getattr(tokenizer, "eos_token_id", None),
            "eos_token_id": getattr(tokenizer, "eos_token_id", None),
        }
        output_ids = model.generate(input_ids, **generate_kwargs)
        generated_ids = output_ids[0][input_ids.shape[-1] :]
        translated_text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        results.append(
            {
                "block_id": str(block.block_id),
                "translated_text": _normalize_translation_text(translated_text),
            }
        )
    return results


def _load_model_bundle(model_name_or_path: str) -> tuple[object, object]:
    cached = _MODEL_CACHE.get(model_name_or_path)
    if cached is not None:
        return cached

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "transformers is not installed in the HY-MT runtime image."
        ) from exc

    local_only = _looks_like_local_path(model_name_or_path)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name_or_path,
        trust_remote_code=False,
        local_files_only=local_only,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        trust_remote_code=False,
        device_map="auto",
        torch_dtype="auto",
        local_files_only=local_only,
    )
    if getattr(tokenizer, "pad_token_id", None) is None:
        tokenizer.pad_token_id = getattr(tokenizer, "eos_token_id", None)

    bundle = (model, tokenizer)
    _MODEL_CACHE[model_name_or_path] = bundle
    return bundle


def _build_translation_prompt(
    *,
    source_text: str,
    source_language: str,
    target_language: str,
    writing_mode: str,
) -> str:
    return (
        "You are a manga translation assistant.\n"
        f"Translate the following {source_language} text into natural {target_language}.\n"
        "Return the translation only.\n"
        "Do not add notes, quotes, explanations, or romanization.\n"
        f"Writing mode hint: {writing_mode or 'unknown'}.\n\n"
        f"Source:\n{source_text}"
    )


def _normalize_translation_text(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith('"') and normalized.endswith('"') and len(normalized) >= 2:
        normalized = normalized[1:-1].strip()
    return normalized


def _looks_like_local_path(model_name_or_path: str) -> bool:
    return Path(model_name_or_path).exists()
