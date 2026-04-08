from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from model_engine.builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    MANGA_OCR_MODEL_ID,
    OPENAI_COMPATIBLE_DEFAULT_BASE_URL,
    OPENAI_COMPATIBLE_DEFAULT_MODEL,
    OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
    VERTEX_TRANSLATION_MODEL_ID,
    register_craft_text_detection_model,
    register_manga_ocr_model,
    register_openai_compatible_translation_model,
    register_vertex_translation_model,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.config.runtime_config import load_runtime_config, runtime_config_value
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage, Stage


def main() -> int:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(
        description="Run built-in CRAFT -> manga-ocr -> translation on a sample image."
    )
    parser.add_argument(
        "--image",
        default="model_engine/samples/dlsite/sample.jpg",
        help="Path to the input image file.",
    )
    parser.add_argument(
        "--workspace",
        default="model_engine/.runtime",
        help="Directory used for generated stage artifacts.",
    )
    parser.add_argument(
        "--api-key-env",
        default="TOWA_TRANSLATION_PROVIDER_API_KEY",
        help="Environment variable that contains the Vertex translation API key.",
    )
    parser.add_argument(
        "--translation-backend",
        choices=("openai_compatible", "vertex"),
        default=runtime_config_value(
            runtime_config,
            "TOWA_TRANSLATION_BACKEND",
            aliases=("translation_backend", "translation.backend"),
            default="openai_compatible",
        ),
        help="Translation backend used in the sample.",
    )
    parser.add_argument(
        "--openai-compatible-api-key-env",
        default="TOWA_OPENAI_COMPATIBLE_API_KEY",
        help="Optional environment variable that contains the OpenAI-compatible API key.",
    )
    parser.add_argument(
        "--openai-compatible-base-url",
        default=runtime_config_value(
            runtime_config,
            "TOWA_OPENAI_COMPATIBLE_BASE_URL",
            aliases=("openai_compatible_base_url", "translation.openai_compatible_base_url"),
            default=OPENAI_COMPATIBLE_DEFAULT_BASE_URL,
        ),
        help="OpenAI-compatible /v1 base URL for local LLM servers or custom proxies.",
    )
    parser.add_argument(
        "--source-language",
        default="Japanese",
        help="Source language label passed to the translation stage.",
    )
    parser.add_argument(
        "--target-language",
        default="Korean",
        help="Target language label passed to the translation stage.",
    )
    parser.add_argument(
        "--model-name",
        default=runtime_config_value(
            runtime_config,
            "TOWA_TRANSLATION_MODEL_NAME",
            aliases=("translation_model_name", "translation.model_name"),
        ),
        help="Backend model name. Defaults to backend-specific model if omitted.",
    )
    parser.add_argument(
        "--text-threshold",
        type=float,
        default=0.7,
        help="CRAFT text threshold.",
    )
    parser.add_argument(
        "--link-threshold",
        type=float,
        default=0.4,
        help="CRAFT link threshold.",
    )
    parser.add_argument(
        "--low-text",
        type=float,
        default=0.4,
        help="CRAFT low text threshold.",
    )
    parser.add_argument(
        "--writing-mode-hint",
        default="vertical",
        help="Default writing mode hint passed to the OCR stage.",
    )
    args = parser.parse_args()

    api_key = runtime_config_value(
        runtime_config,
        args.api_key_env,
        aliases=("translation_provider_api_key", "translation.vertex_api_key"),
    )
    openai_compatible_api_key = runtime_config_value(
        runtime_config,
        args.openai_compatible_api_key_env,
        aliases=("openai_compatible_api_key", "translation.openai_compatible_api_key"),
    )
    if args.translation_backend == "vertex" and not api_key:
        raise RuntimeError(
            f"Missing translation API key. Set the environment variable {args.api_key_env} before running."
        )

    image_path = Path(args.image).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    workspace_path = Path(args.workspace).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as image:
        width, height = image.size

    document = DocumentIR(
        id="sample_document",
        name=image_path.name,
        width=int(width),
        height=int(height),
    )
    input_artifact = ArtifactDescriptor(
        artifact_ref="artifact://sample/input_bitmap",
        kind="bitmap",
        media_type=_media_type_for_suffix(image_path.suffix),
        uri=image_path.as_uri(),
        width=int(width),
        height=int(height),
        metadata={"role": "input_page"},
    )

    registry = ModelRegistry()
    register_craft_text_detection_model(registry)
    register_manga_ocr_model(registry)
    register_vertex_translation_model(registry)
    register_openai_compatible_translation_model(registry)

    stages: list[Stage] = [
        AdapterBackedStage(
            "text_detection",
            stage_kind=StageKind.TEXT_DETECTION,
            registry=registry,
            preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "text_threshold": args.text_threshold,
                "link_threshold": args.link_threshold,
                "low_text": args.low_text,
            },
        ),
        AdapterBackedStage(
            "ocr",
            stage_kind=StageKind.OCR,
            registry=registry,
            preferred_model_id=MANGA_OCR_MODEL_ID,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "writing_mode_hint": args.writing_mode_hint,
                "region_padding": 12,
                "merge_regions": True,
                "merge_gap_px": 24,
                "merge_min_overlap_ratio": 0.25,
                "reading_order_mode": "vertical_rtl",
                "min_ocr_region_area_px": 160,
                "min_ocr_region_area_ratio": 0.00015,
                "max_text_density_per_1000_px2": 1.5,
                "small_region_long_text_area_px": 6000,
                "small_region_long_text_area_ratio": 0.004,
                "small_region_long_text_min_chars": 16,
                "hallucination_action": "mark",
            },
        ),
        AdapterBackedStage(
            "translation",
            stage_kind=StageKind.TRANSLATION,
            registry=registry,
            preferred_model_id=(
                OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID
                if args.translation_backend == "openai_compatible"
                else VERTEX_TRANSLATION_MODEL_ID
            ),
            config=_translation_stage_config(
                backend=args.translation_backend,
                model_name=args.model_name,
                source_language=args.source_language,
                target_language=args.target_language,
                openai_compatible_base_url=args.openai_compatible_base_url,
                openai_compatible_api_key_present=bool(openai_compatible_api_key),
            ),
        ),
    ]

    orchestrator = PipelineOrchestrator()
    result = orchestrator.run(
        document=document,
        stages=stages,
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_path.as_uri(),
            requested_by="run_translation_sample",
            session_provider_secrets=_session_provider_secrets(
                backend=args.translation_backend,
                vertex_api_key=api_key,
                openai_compatible_api_key=openai_compatible_api_key,
            ),
        ),
        initial_artifacts={input_artifact.artifact_ref: input_artifact},
        job_id="job_translation_sample",
        pipeline_id="pipe_translation_sample",
    )
    summary = {
        "status": result.status.value,
        "text_blocks": [
            {
                "block_id": block.block_id,
                "source_lang_text": block.source_lang_text,
                "translated_text": block.translated_text,
                "reading_order": block.reading_order,
                "writing_mode": block.writing_mode,
                "source_region_ref": block.source_region_ref,
            }
            for block in result.document.text_blocks
        ],
        "stage_meta": result.document.stage_meta,
        "stage_reports": [
            {
                "stage_name": report.stage_name,
                "status": report.status.value,
                "metrics": report.metrics,
                "error_code": report.error_code,
                "error_message": report.error_message,
                "output_refs": report.output_refs,
            }
            for report in result.stage_reports
        ],
        "artifacts": {
            artifact_ref: {
                "kind": artifact.kind,
                "uri": artifact.uri,
                "metadata": artifact.metadata,
            }
            for artifact_ref, artifact in result.artifacts.items()
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if result.status.value in {"succeeded", "partial"} else 1


def _media_type_for_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".webp":
        return "image/webp"
    return "image/png"


def _translation_stage_config(
    *,
    backend: str,
    model_name: str,
    source_language: str,
    target_language: str,
    openai_compatible_base_url: str,
    openai_compatible_api_key_present: bool,
) -> dict[str, object]:
    if backend == "openai_compatible":
        config: dict[str, object] = {
            "base_url": openai_compatible_base_url,
            "model_name": model_name or OPENAI_COMPATIBLE_DEFAULT_MODEL,
            "source_language": source_language,
            "target_language": target_language,
        }
        if openai_compatible_api_key_present:
            config["provider"] = "openai_compatible"
        else:
            config["skip_provider_resolution"] = True
        return config
    return {
        "provider": "translation_provider",
        "model_name": model_name or "gemini-3.1-flash-lite-preview",
        "source_language": source_language,
        "target_language": target_language,
    }


def _session_provider_secrets(
    *,
    backend: str,
    vertex_api_key: Optional[str],
    openai_compatible_api_key: Optional[str],
) -> dict[str, str]:
    if backend == "openai_compatible":
        return {"openai_compatible": openai_compatible_api_key} if openai_compatible_api_key else {}
    return {"translation_provider": vertex_api_key} if vertex_api_key else {}


if __name__ == "__main__":
    raise SystemExit(main())
