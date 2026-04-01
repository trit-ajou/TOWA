from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from model_engine.builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    MANGA_OCR_MODEL_ID,
    register_craft_text_detection_model,
    register_manga_ocr_model,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage, Stage


HY_MT_TRANSLATION_MODEL_ID = "custom.tencent.hy_mt_1_8b.translation"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run built-in CRAFT -> manga-ocr -> HY-MT translation on a sample image."
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
        "--custom-model-dir",
        default="model_engine/custom_model_specs",
        help="Directory that contains custom model manifests.",
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
        default="tencent/HY-MT1.5-1.8B",
        help="HY-MT model id or local path used inside the worker runtime.",
    )
    parser.add_argument(
        "--writing-mode-hint",
        default="vertical",
        help="Default writing mode hint passed to the OCR stage.",
    )
    args = parser.parse_args()

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
    registry.load_custom_model_directory(str(Path(args.custom_model_dir).resolve()))

    stages: list[Stage] = [
        AdapterBackedStage(
            "text_detection",
            stage_kind=StageKind.TEXT_DETECTION,
            registry=registry,
            preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "text_threshold": 0.7,
                "link_threshold": 0.4,
                "low_text": 0.4,
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
            preferred_model_id=HY_MT_TRANSLATION_MODEL_ID,
            config={
                "skip_provider_resolution": True,
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
            requested_by="run_hy_mt_translation_sample",
        ),
        initial_artifacts={input_artifact.artifact_ref: input_artifact},
        job_id="job_hy_mt_translation_sample",
        pipeline_id="pipe_hy_mt_translation_sample",
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
