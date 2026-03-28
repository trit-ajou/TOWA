from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.builtin_models.craft_text_detection import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    register_craft_text_detection_model,
    run_craft_text_detection,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import (
    ExecutionMode,
    StageRequest,
    StageRuntimeContext,
    StageStatus,
)
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage


class CraftTextDetectionTests(unittest.TestCase):
    def test_run_craft_text_detection_writes_text_regions_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = _write_sample_image(Path(tmpdir) / "page.png")
            request = _stage_request(Path(tmpdir), image_path)

            response = run_craft_text_detection(
                request,
                detect_text_fn=_fake_detect_text,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("craft", response.stage_report.metrics["detector"])
            self.assertEqual(2, response.stage_report.metrics["region_count"])
            self.assertEqual(1, len(response.artifacts))
            artifact = next(iter(response.artifacts.values()))
            self.assertEqual("text_regions", artifact.kind)
            artifact_path = Path(artifact.uri.removeprefix("file://"))
            self.assertIn(
                "/transactions/pipe_craft_test/text_detection/pipe_craft_test_text_detection_1/",
                artifact_path.as_posix(),
            )
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("craft", payload["detector"])
            self.assertEqual(2, len(payload["regions"]))
            self.assertEqual(
                "artifact://sample/input_bitmap",
                payload["source_artifact_ref"],
            )
            self.assertEqual(
                {"engine": "craft", "artifact_ref": artifact.artifact_ref, "region_count": 2},
                response.patches[0].payload["value"],
            )

    def test_registry_runs_builtin_craft_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = _write_sample_image(Path(tmpdir) / "page.png")
            registry = ModelRegistry()
            register_craft_text_detection_model(registry)
            stage = AdapterBackedStage(
                "text_detection",
                stage_kind=StageKind.TEXT_DETECTION,
                registry=registry,
                preferred_model_id=CRAFT_TEXT_DETECTION_MODEL_ID,
                config={
                    "input_artifact_ref": "artifact://sample/input_bitmap",
                },
            )

            with patch(
                "model_engine.builtin_models.craft_text_detection._detect_with_craft",
                side_effect=_fake_detect_text,
            ):
                response = stage.run(_stage_request(Path(tmpdir), image_path))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(CRAFT_TEXT_DETECTION_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual(
                "preferred_model_id=builtin.craft.text_detection",
                response.stage_report.metrics["selection_reason"],
            )
            artifact = next(iter(response.artifacts.values()))
            artifact_path = Path(artifact.uri.removeprefix("file://"))
            self.assertIn("/transactions/pipe_craft_test/text_detection/", artifact_path.as_posix())


def _stage_request(workspace_dir: Path, image_path: Path) -> StageRequest:
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_craft_test",
        job_id="job_craft_test",
        stage_name="text_detection",
        stage_run_id="pipe_craft_test:text_detection:1",
        document=DocumentIR(id="doc_craft_test", name="craft-test", width=32, height=24),
        artifacts={
            "artifact://sample/input_bitmap": ArtifactDescriptor(
                artifact_ref="artifact://sample/input_bitmap",
                kind="bitmap",
                media_type="image/png",
                uri=image_path.resolve().as_uri(),
                width=32,
                height=24,
            )
        },
        stage_config={"input_artifact_ref": "artifact://sample/input_bitmap"},
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _write_sample_image(path: Path) -> Path:
    image = Image.new("RGB", (32, 24), color=(255, 255, 255))
    image.save(path)
    return path


def _fake_detect_text(image_path: str, config: dict[str, object]) -> dict[str, object]:
    _ = image_path
    _ = config
    return {
        "polys": [
            [[1, 1], [10, 1], [10, 6], [1, 6]],
            [[12, 10], [24, 10], [24, 18], [12, 18]],
        ],
        "scores": [0.98, 0.91],
    }


if __name__ == "__main__":
    unittest.main()
