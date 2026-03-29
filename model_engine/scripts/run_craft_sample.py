from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from model_engine.builtin_models import register_craft_text_detection_model
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage


def main() -> int:
    parser = argparse.ArgumentParser(description="Run built-in CRAFT text detection on a sample image.")
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

    stage = AdapterBackedStage(
        "text_detection",
        stage_kind=StageKind.TEXT_DETECTION,
        registry=registry,
        preferred_model_id="builtin.craft.text_detection",
        config={
            "input_artifact_ref": input_artifact.artifact_ref,
            "text_threshold": args.text_threshold,
            "link_threshold": args.link_threshold,
            "low_text": args.low_text,
        },
    )
    orchestrator = PipelineOrchestrator()
    result = orchestrator.run(
        document=document,
        stages=[stage],
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_path.as_uri(),
            requested_by="run_craft_sample",
        ),
        initial_artifacts={input_artifact.artifact_ref: input_artifact},
        job_id="job_craft_sample",
        pipeline_id="pipe_craft_sample",
    )
    summary = {
        "status": result.status.value,
        "stage_reports": [
            {
                "stage_name": report.stage_name,
                "status": report.status.value,
                "metrics": report.metrics,
                "output_refs": report.output_refs,
            }
            for report in result.stage_reports
        ],
        "text_detection_meta": result.document.stage_meta.get("text_detection", {}),
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
    return 0


def _media_type_for_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".webp":
        return "image/webp"
    return "image/png"


if __name__ == "__main__":
    raise SystemExit(main())
