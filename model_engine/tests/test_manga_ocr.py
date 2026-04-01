from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.builtin_models.manga_ocr import (
    MANGA_OCR_MODEL_ID,
    register_manga_ocr_model,
    run_manga_ocr,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.patches import apply_patches
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageRuntimeContext, StageStatus
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage


class MangaOcrTests(unittest.TestCase):
    def test_run_manga_ocr_writes_text_blocks_artifact_and_replace_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = _write_sample_image(Path(tmpdir) / "page.png")
            text_regions_path = _write_text_regions(Path(tmpdir) / "text_regions.json")
            request = _stage_request(Path(tmpdir), image_path, text_regions_path)

            response = run_manga_ocr(
                request,
                recognize_region_fn=_fake_recognize_region,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("manga_ocr", response.stage_report.metrics["engine"])
            self.assertEqual(2, response.stage_report.metrics["recognized_count"])
            self.assertEqual(1, len(response.artifacts))
            artifact = next(iter(response.artifacts.values()))
            self.assertEqual("ocr_text_blocks", artifact.kind)
            artifact_path = Path(artifact.uri.removeprefix("file://"))
            self.assertIn("/transactions/pipe_manga_ocr_test/ocr/", artifact_path.as_posix())
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("manga_ocr", payload["engine"])
            self.assertEqual(2, len(payload["blocks"]))
            self.assertEqual("block_0001", payload["blocks"][0]["block_id"])
            self.assertEqual("replace_text_blocks", response.patches[0].op.value)

            document = request.document.clone()
            apply_patches(document, response.patches)
            self.assertEqual(["block_0001", "block_0002"], [block.block_id for block in document.text_blocks])
            self.assertEqual("こんにちは", document.text_blocks[0].source_lang_text)
            self.assertEqual("vertical", document.text_blocks[1].writing_mode)

    def test_registry_runs_builtin_manga_ocr_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = _write_sample_image(Path(tmpdir) / "page.png")
            text_regions_path = _write_text_regions(Path(tmpdir) / "text_regions.json")
            registry = ModelRegistry()
            register_manga_ocr_model(registry)
            stage = AdapterBackedStage(
                "ocr",
                stage_kind=StageKind.OCR,
                registry=registry,
                preferred_model_id=MANGA_OCR_MODEL_ID,
                config={
                    "input_artifact_ref": "artifact://sample/input_bitmap",
                    "text_regions_artifact_ref": "artifact://sample/text_regions",
                    "writing_mode_hint": "vertical",
                },
            )

            with patch(
                "model_engine.builtin_models.manga_ocr._recognize_with_manga_ocr",
                side_effect=_fake_recognize_region,
            ):
                response = stage.run(_stage_request(Path(tmpdir), image_path, text_regions_path))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(MANGA_OCR_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual(
                "preferred_model_id=builtin.manga_ocr.recognizer",
                response.stage_report.metrics["selection_reason"],
            )


def _stage_request(workspace_dir: Path, image_path: Path, text_regions_path: Path) -> StageRequest:
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_manga_ocr_test",
        job_id="job_manga_ocr_test",
        stage_name="ocr",
        stage_run_id="pipe_manga_ocr_test:ocr:1",
        document=DocumentIR(id="doc_manga_ocr_test", name="ocr-test", width=64, height=32),
        artifacts={
            "artifact://sample/input_bitmap": ArtifactDescriptor(
                artifact_ref="artifact://sample/input_bitmap",
                kind="bitmap",
                media_type="image/png",
                uri=image_path.resolve().as_uri(),
                width=64,
                height=32,
            ),
            "artifact://sample/text_regions": ArtifactDescriptor(
                artifact_ref="artifact://sample/text_regions",
                kind="text_regions",
                media_type="application/json",
                uri=text_regions_path.resolve().as_uri(),
            ),
        },
        stage_config={
            "input_artifact_ref": "artifact://sample/input_bitmap",
            "text_regions_artifact_ref": "artifact://sample/text_regions",
            "writing_mode_hint": "vertical",
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _write_sample_image(path: Path) -> Path:
    image = Image.new("RGB", (64, 32), color=(255, 255, 255))
    image.save(path)
    return path


def _write_text_regions(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "detector": "craft",
                "source_artifact_ref": "artifact://sample/input_bitmap",
                "image_width": 64,
                "image_height": 32,
                "regions": [
                    {
                        "region_id": "region_0001",
                        "polygon": [
                            {"x": 2, "y": 2},
                            {"x": 18, "y": 2},
                            {"x": 18, "y": 14},
                            {"x": 2, "y": 14},
                        ],
                        "bbox": {"x": 2, "y": 2, "width": 16, "height": 12},
                        "confidence": 0.98,
                        "reading_order": 0,
                        "source_artifact_ref": "artifact://sample/input_bitmap",
                        "metadata": {},
                    },
                    {
                        "region_id": "region_0002",
                        "polygon": [
                            {"x": 24, "y": 4},
                            {"x": 44, "y": 4},
                            {"x": 44, "y": 18},
                            {"x": 24, "y": 18},
                        ],
                        "bbox": {"x": 24, "y": 4, "width": 20, "height": 14},
                        "confidence": 0.92,
                        "reading_order": 1,
                        "source_artifact_ref": "artifact://sample/input_bitmap",
                        "metadata": {},
                    },
                ],
                "metadata": {},
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _fake_recognize_region(image: Image.Image, config: dict[str, object]) -> dict[str, object]:
    width, _height = image.size
    if width <= 16:
        return {"text": "こんにちは", "confidence": 0.97, "writing_mode": "vertical"}
    return {
        "text": "世界",
        "confidence": 0.91,
        "writing_mode": str(config.get("writing_mode_hint", "vertical")),
    }


if __name__ == "__main__":
    unittest.main()
