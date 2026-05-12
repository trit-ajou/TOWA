from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.api.jobs import (
    JobExecutionRequest,
    JobExecutionResult,
    JobExecutor,
    ModelJobManager,
    ModelJobStatus,
    OrchestratedJobExecutor,
    PlaceholderJobExecutor,
    UploadedBinaryPart,
    submission_from_api_payload,
    submission_from_multipart_payload,
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
            self.assertEqual(1, len(result.document.text_blocks))
            self.assertEqual("block_0001", result.document.text_blocks[0].block_id)
            self.assertEqual("", result.document.text_blocks[0].source_lang_text)
            self.assertEqual("region_0001", result.document.text_blocks[0].source_region_ref)
            self.assertEqual(
                ["replace_text_blocks", "set_stage_meta"],
                [patch.op.value for patch in result.document_patch],
            )

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
            text_block_patches = [
                patch for patch in result.document_patch if patch.op.value == "replace_text_blocks"
            ]
            self.assertEqual(2, len(text_block_patches))
            self.assertEqual(
                ["縦書きテキスト", "縦書きテキスト"],
                [
                    patch.payload["text_blocks"][0]["source_lang_text"]
                    for patch in text_block_patches
                ],
            )
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

    def test_multipart_submission_materializes_primary_bitmap_and_updates_fingerprint(self) -> None:
        payload = _job_payload(operation_kind="translate", mode="local")
        payload["artifacts"] = {
            "artifact://input/primary_bitmap": {
                "artifact_ref": "artifact://input/primary_bitmap",
                "kind": "bitmap",
                "media_type": "image/png",
                "uri": "upload://primary_bitmap",
            }
        }
        first = submission_from_multipart_payload(
            _payload_object(payload),
            primary_bitmap=UploadedBinaryPart(
                part_name="primary_bitmap",
                filename="page.png",
                media_type="image/png",
                content=b"first-image",
            ),
        )
        second = submission_from_multipart_payload(
            _payload_object(payload),
            primary_bitmap=UploadedBinaryPart(
                part_name="primary_bitmap",
                filename="page.png",
                media_type="image/png",
                content=b"second-image",
            ),
        )

        first_artifact = first.artifacts["artifact://input/primary_bitmap"]
        self.assertTrue(first_artifact.uri.startswith("file://"))
        self.assertEqual(
            f"sha256:{hashlib.sha256(b'first-image').hexdigest()}",
            first_artifact.checksum,
        )
        self.assertEqual(len(b"first-image"), first_artifact.byte_size)
        self.assertNotEqual(first.request_fingerprint, second.request_fingerprint)

    def test_job_detail_response_includes_document_patch(self) -> None:
        manager = ModelJobManager(
            executor=PlaceholderJobExecutor(sleep_seconds=0.0),
        )
        submission = submission_from_api_payload(
            _payload_object(_job_payload(operation_kind="detect", mode="local"))
        )

        _, response = manager.create_job(submission)
        detail = _wait_for_terminal_job(manager, response["job_id"])

        self.assertEqual("succeeded", detail["status"])
        self.assertIn("document_patch", detail)
        self.assertEqual("set_stage_meta", detail["document_patch"]["patches"][0]["op"])

    def test_manager_uses_server_file_workspace_for_logical_api_workspace(self) -> None:
        executor = _CapturingExecutor()
        manager = ModelJobManager(executor=executor)
        submission = submission_from_api_payload(
            _payload_object(_job_payload(operation_kind="detect", mode="local"))
        )

        _, response = manager.create_job(submission)
        detail = _wait_for_terminal_job(manager, response["job_id"])

        self.assertEqual("succeeded", detail["status"])
        self.assertEqual(1, len(executor.requests))
        execution_context = executor.requests[0].runtime_context
        self.assertTrue(execution_context.workspace_uri.startswith("file://"))
        self.assertEqual(
            "workspace://project/proj-1/page/001",
            execution_context.metadata["client_workspace_uri"],
        )

    def test_background_executor_exception_is_logged_with_job_context(self) -> None:
        manager = ModelJobManager(executor=_ExplodingExecutor())
        submission = submission_from_api_payload(
            _payload_object(_job_payload(operation_kind="detect", mode="local"))
        )

        with self.assertLogs("model_engine.api.jobs", level="ERROR") as captured:
            _, response = manager.create_job(submission)
            detail = _wait_for_terminal_job(manager, response["job_id"])

        logs = "\n".join(captured.output)
        self.assertEqual("failed", detail["status"])
        self.assertIn("model_job_exception", logs)
        self.assertIn(response["job_id"], logs)
        self.assertIn("pipe_", logs)
        self.assertIn("RuntimeError: executor boom", logs)


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


class _CapturingExecutor(JobExecutor):
    def __init__(self) -> None:
        self.requests: list[JobExecutionRequest] = []

    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        self.requests.append(request)
        return JobExecutionResult(
            status=ModelJobStatus.SUCCEEDED,
            document=request.document,
            artifacts=dict(request.artifacts),
            document_patch=[],
            stage_reports=[],
        )


class _ExplodingExecutor(JobExecutor):
    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        _ = request
        raise RuntimeError("executor boom")


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


def _wait_for_terminal_job(manager: ModelJobManager, job_id: str) -> dict[str, object]:
    deadline = time.time() + 2.0
    while time.time() < deadline:
        detail = manager.get_job(job_id)
        if detail["status"] in {"succeeded", "failed", "partial"}:
            return detail
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for job {job_id} to finish")


if __name__ == "__main__":
    unittest.main()
