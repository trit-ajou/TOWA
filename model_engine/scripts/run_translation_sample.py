from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from model_engine.builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    MANGA_OCR_MODEL_ID,
    VERTEX_TRANSLATION_MODEL_ID,
    register_craft_text_detection_model,
    register_manga_ocr_model,
    register_vertex_translation_model,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage, Stage


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run built-in CRAFT -> manga-ocr -> Vertex translation on a sample image."
    )
    parser.add_argument(
        "--image",
        default="model_engine/samples/images/sample_page.webp",
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
        default="gemini-2.5-flash",
        help="Vertex Gemini model name.",
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

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
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
                "region_padding": 0,
            },
        ),
        AdapterBackedStage(
            "translation",
            stage_kind=StageKind.TRANSLATION,
            registry=registry,
            preferred_model_id=VERTEX_TRANSLATION_MODEL_ID,
            config={
                "provider": "translation_provider",
                "model_name": args.model_name,
                "source_language": args.source_language,
                "target_language": args.target_language,
            },
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
            session_provider_secrets={"translation_provider": api_key},
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


if __name__ == "__main__":
    raise SystemExit(main())
