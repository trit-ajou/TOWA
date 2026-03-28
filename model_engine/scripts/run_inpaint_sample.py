from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Callable, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from model_engine.builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    NANOBANANA_INPAINT_MODEL_ID,
    register_craft_text_detection_model,
    register_nanobanana_inpaint_model,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageRuntimeContext, StageResponse
from model_engine.models import ModelRegistry
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages import AdapterBackedStage, Stage, run_mask_or_erase_planning


class FunctionStage(Stage):
    """Wrap a stage function so the sample runner can compose it with the orchestrator."""

    def __init__(
        self,
        stage_name: str,
        handler: Callable[[StageRequest], StageResponse],
        *,
        config: Optional[dict[str, object]] = None,
    ) -> None:
        self._stage_name = stage_name
        self._handler = handler
        self._config = dict(config or {})

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        return dict(self._config)

    def run(self, request: StageRequest) -> StageResponse:
        return self._handler(request)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run built-in CRAFT -> planner -> nanobanana inpaint on a sample image."
    )
    parser.add_argument(
        "--image",
        default="model_engine/samples/images/sample_page.webp",
        help="Path to the input manga page image.",
    )
    parser.add_argument(
        "--workspace",
        default="model_engine/.runtime",
        help="Directory used for generated transaction artifacts.",
    )
    parser.add_argument(
        "--api-key-env",
        default="TOWA_NANOBANANA_API_KEY",
        help="Environment variable that contains the nanobanana API key.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=12,
        help="Pixel padding added around each detected text region before inpaint.",
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
        "--model-name",
        default="gemini-2.5-flash-image",
        help="Nanobanana image model name.",
    )
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Missing nanobanana API key. Set the environment variable {args.api_key_env} before running."
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
    register_nanobanana_inpaint_model(registry)

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
        FunctionStage(
            "mask_or_erase_planning",
            run_mask_or_erase_planning,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "padding": args.padding,
                "target_layer_id": "layer_inpainting",
            },
        ),
        AdapterBackedStage(
            "inpaint",
            stage_kind=StageKind.INPAINT,
            registry=registry,
            preferred_model_id=NANOBANANA_INPAINT_MODEL_ID,
            config={
                "input_artifact_ref": input_artifact.artifact_ref,
                "model_name": args.model_name,
                "target_layer_id": "layer_inpainting",
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
            requested_by="run_inpaint_sample",
            session_provider_secrets={"nanobanana": api_key},
        ),
        initial_artifacts={input_artifact.artifact_ref: input_artifact},
        job_id="job_inpaint_sample",
        pipeline_id="pipe_inpaint_sample",
    )

    summary = {
        "status": result.status.value,
        "document_layers": [
            {
                "id": layer.id,
                "name": layer.name,
                "source_ref": layer.source_ref,
                "props": layer.props,
            }
            for layer in result.document.layers
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
                "status": artifact.status.value,
                "metadata": artifact.metadata,
            }
            for artifact_ref, artifact in result.artifacts.items()
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if result.status.value == "succeeded" else 1


def _media_type_for_suffix(suffix: str) -> str:
    normalized = suffix.lower()
    if normalized in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if normalized == ".webp":
        return "image/webp"
    return "image/png"


if __name__ == "__main__":
    raise SystemExit(main())
