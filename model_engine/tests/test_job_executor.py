from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.api.jobs import (
    JobExecutionRequest,
    ModelJobManager,
    ModelJobStatus,
    OrchestratedJobExecutor,
    PlaceholderJobExecutor,
    submission_from_api_payload,
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

    def test_translate_job_runs_detection_then_ocr_before_openai_compatible_translation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _job_request(Path(tmpdir), operation_kind="translate")
            executor = OrchestratedJobExecutor()

            with patch(
                "model_engine.builtin_models.craft_text_detection._detect_with_craft",
                side_effect=_fake_detect_text,
            ), patch(
                "model_engine.builtin_models.manga_ocr._recognize_with_manga_ocr",
                side_effect=_fake_recognize_text,
            ), patch(
                "model_engine.builtin_models.openai_compatible_translation._translate_blocks_with_openai_compatible",
                side_effect=_fake_translate_blocks,
            ):
                result = executor.execute(request)

            self.assertEqual(ModelJobStatus.SUCCEEDED, result.status)
            self.assertEqual(
                ["text_detection", "ocr", "translation"],
                [report.stage_name for report in result.stage_reports],
            )
            self.assertEqual(1, len(result.document.text_blocks))
            self.assertEqual("縦書きテキスト", result.document.text_blocks[0].source_lang_text)
            self.assertEqual("세로쓰기 텍스트", result.document.text_blocks[0].translated_text)
            self.assertEqual("manga_ocr", result.document.stage_meta["ocr"]["engine"])
            self.assertEqual(
                "openai_compatible_translation",
                result.document.stage_meta["translation"]["engine"],
            )

    def test_model_job_manager_defaults_to_orchestrated_executor(self) -> None:
        manager = ModelJobManager()
        self.assertIsInstance(manager._executor, OrchestratedJobExecutor)

    def test_saas_job_persists_service_session_key_for_background_billing(self) -> None:
        service_client = _RecordingServiceClient()
        manager = ModelJobManager(
            executor=PlaceholderJobExecutor(sleep_seconds=0.0),
            service_client_factory=lambda: service_client,
        )
        submission = submission_from_api_payload(
            _payload_object(_job_payload(operation_kind="translate", mode="saas"))
        )

        status_code, response = manager.create_job(
            submission,
            authorization="Bearer demo-session",
        )

        self.assertEqual(202, status_code)
        record = manager._jobs_by_id[response["job_id"]]
        self.assertEqual("demo-session", record.runtime_context.service_session_key)
        self.assertEqual("Bearer demo-session", service_client.calls[0]["authorization"])


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
            session_provider_secrets={
                "translation_provider": "test-translation-key",
                "nanobanana": "test-nanobanana-key",
            },
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


def _fake_translate_blocks(blocks, config: dict[str, object], api_key: str) -> list[dict[str, str]]:
    _ = config
    _ = api_key
    return [{"block_id": block.block_id, "translated_text": "세로쓰기 텍스트"} for block in blocks]


class _RecordingServiceClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        path: str,
        *,
        body: dict[str, object] | None = None,
        authorization: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "path": path,
                "body": dict(body or {}),
                "authorization": authorization,
            }
        )
        if path == "/usage/jobs":
            return {
                "job_id": "svc_job_1",
                "status": "authorized",
                "reserved_units": 20,
                "hold_expires_at": "2026-03-25T01:00:00Z",
            }
        return {"status": "ok"}


def _job_payload(*, operation_kind: str, mode: str) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "idempotency_key": f"project:proj-1:page:001:op:{operation_kind}:v:1",
        "operation_kind": operation_kind,
        "request_ref": "project/proj-1/page/001",
        "document": {
            "id": "doc_page_001",
            "name": "page-001",
            "width": 800,
            "height": 1200,
            "layers": [
                {
                    "id": "layer_original",
                    "name": "Original",
                    "type": "graphic",
                    "left": 0,
                    "top": 0,
                    "width": 800,
                    "height": 1200,
                    "source_ref": "artifact://page-original",
                }
            ],
            "text_blocks": [],
            "stage_meta": {},
        },
        "artifacts": {
            "artifact://page-original": {
                "artifact_ref": "artifact://page-original",
                "kind": "bitmap",
                "media_type": "image/png",
                "uri": "https://storage.example.test/page-001.png",
            }
        },
        "runtime_context": {
            "mode": mode,
            "workspace_uri": "workspace://project/proj-1/page/001",
            "requested_by": "user@example.com",
            "target_regions": [],
            "selected_layer_ids": [],
        },
    }


def _payload_object(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=payload["schema_version"],
        idempotency_key=payload["idempotency_key"],
        operation_kind=payload["operation_kind"],
        request_ref=payload["request_ref"],
        document=payload["document"],
        artifacts=payload["artifacts"],
        runtime_context=payload["runtime_context"],
    )


if __name__ == "__main__":
    unittest.main()
