from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.api.jobs import (
    JobExecutionRequest,
    ModelJobManager,
    ModelJobStatus,
    OrchestratedJobExecutor,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext


class OrchestratedJobExecutorTests(unittest.TestCase):
    def test_detect_job_runs_real_text_detection_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _job_request(Path(tmpdir), operation_kind="detect")
            executor = OrchestratedJobExecutor()

            with patch(
                "model_engine.builtin_models.craft_text_detection._detect_with_craft",
                side_effect=_fake_detect_text,
            ):
                result = executor.execute(request)

            self.assertEqual(ModelJobStatus.SUCCEEDED, result.status)
            self.assertEqual(["text_detection"], [report.stage_name for report in result.stage_reports])
            self.assertEqual("craft", result.document.stage_meta["text_detection"]["engine"])

    def test_translate_job_runs_detection_then_ocr_before_placeholder_translation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _job_request(Path(tmpdir), operation_kind="translate")
            executor = OrchestratedJobExecutor()

            with patch(
                "model_engine.builtin_models.craft_text_detection._detect_with_craft",
                side_effect=_fake_detect_text,
            ), patch(
                "model_engine.builtin_models.manga_ocr._recognize_with_manga_ocr",
                side_effect=_fake_recognize_text,
            ):
                result = executor.execute(request)

            self.assertEqual(ModelJobStatus.SUCCEEDED, result.status)
            self.assertEqual(
                ["text_detection", "ocr", "translation"],
                [report.stage_name for report in result.stage_reports],
            )
            self.assertEqual(1, len(result.document.text_blocks))
            self.assertEqual("縦書きテキスト", result.document.text_blocks[0].source_lang_text)
            self.assertEqual("manga_ocr", result.document.stage_meta["ocr"]["engine"])
            self.assertEqual("placeholder", result.document.stage_meta["translation"]["executor"])

    def test_model_job_manager_defaults_to_orchestrated_executor(self) -> None:
        manager = ModelJobManager()
        self.assertIsInstance(manager._executor, OrchestratedJobExecutor)


def _job_request(workspace_dir: Path, *, operation_kind: str) -> JobExecutionRequest:
    image_path = _write_sample_image(workspace_dir / "page.png")
    document = DocumentIR(id=f"doc_{operation_kind}", name="page.png", width=48, height=32)
    artifact = ArtifactDescriptor(
        artifact_ref="artifact://sample/input_bitmap",
        kind="bitmap",
        media_type="image/png",
        uri=image_path.resolve().as_uri(),
        width=48,
        height=32,
        metadata={"role": "input_page"},
    )
    return JobExecutionRequest(
        job_id=f"job_{operation_kind}",
        pipeline_id=f"pipe_{operation_kind}",
        schema_version="v1",
        operation_kind=operation_kind,
        request_ref=f"req_{operation_kind}",
        document=document,
        artifacts={artifact.artifact_ref: artifact},
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
            requested_by="test_job_executor",
        ),
    )


def _write_sample_image(path: Path) -> Path:
    image = Image.new("RGB", (48, 32), color=(255, 255, 255))
    image.save(path)
    return path


def _fake_detect_text(image_path: str, config: dict[str, object]) -> dict[str, object]:
    _ = image_path
    _ = config
    return {
        "polys": [
            [[4, 4], [20, 4], [20, 24], [4, 24]],
        ],
        "scores": [0.97],
    }


def _fake_recognize_text(image, config: dict[str, object]) -> str:
    _ = image
    _ = config
    return "縦書きテキスト"


if __name__ == "__main__":
    unittest.main()
