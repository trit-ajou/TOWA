from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.credentials import CredentialSource
from model_engine.contracts.document_ir import DocumentIR, LayerIR
from model_engine.contracts.patches import PatchOp, PatchOperation
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext, StageStatus
from model_engine.credentials import DefaultCredentialResolver
from model_engine.orchestrator import PipelineOrchestrator
from model_engine.stages.base import StaticStage


class OrchestratorTests(unittest.TestCase):
    def test_orchestrator_runs_sequential_stages_and_applies_patches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = PipelineOrchestrator(
                credential_resolver=DefaultCredentialResolver(
                    credentials_file=_write_local_credentials(tmpdir, provider="nanobanana", api_key="local-secret"),
                    environ={},
                )
            )
            document = DocumentIR(
                id="doc_1",
                name="page-1",
                width=100,
                height=100,
                layers=[
                    LayerIR(
                        id="layer_base",
                        name="Base",
                        type="graphic",
                        left=0,
                        top=0,
                        width=100,
                        height=100,
                        source_ref="artifact://base-v1",
                    )
                ],
            )
            runtime_context = StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri="file:///tmp/towa/run-001",
                requested_by="tester",
            )
            stages = [
                StaticStage(
                    "text_detection",
                    patches=[
                        PatchOperation(
                            op=PatchOp.APPEND_TEXT_BLOCKS,
                            payload={"text_blocks": [{"block_id": "block-1", "source_lang_text": "원문"}]},
                        )
                    ],
                    metrics={"latency_ms": 12},
                ),
                StaticStage(
                    "inpaint",
                    patches=[
                        PatchOperation(
                            op=PatchOp.REPLACE_SOURCE_REF,
                            target={"layer_id": "layer_base"},
                            payload={"source_ref": "artifact://base-v2"},
                        )
                    ],
                    artifacts={
                        "artifact://base-v2": ArtifactDescriptor(
                            artifact_ref="artifact://base-v2",
                            kind="bitmap",
                            media_type="image/png",
                            uri="file:///tmp/towa/base-v2.png",
                            producer_stage="inpaint",
                        )
                    },
                    metrics={"latency_ms": 33},
                ),
            ]

            result = orchestrator.run(document=document, stages=stages, runtime_context=runtime_context)

            self.assertEqual(StageStatus.SUCCEEDED, result.status)
            self.assertEqual("artifact://base-v2", result.document.require_layer("layer_base").source_ref)
            self.assertEqual(1, len(result.document.text_blocks))
            self.assertEqual(2, len(result.stage_reports))
            self.assertIn("artifact://base-v2", result.artifacts)
            self.assertEqual("nanobanana", result.stage_reports[1].provider.provider)
            self.assertEqual(CredentialSource.USER_PERSONAL_PERSISTED, result.stage_reports[1].provider.credential_source)

    def test_failure_stops_later_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = PipelineOrchestrator(
                credential_resolver=DefaultCredentialResolver(
                    credentials_file=_write_local_credentials(tmpdir, provider="nanobanana", api_key="local-secret"),
                    environ={},
                )
            )
            document = DocumentIR(id="doc_2", name="page-2", width=10, height=10)
            runtime_context = StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri="file:///tmp/towa/run-002",
            )
            stages = [
                StaticStage("text_detection"),
                StaticStage(
                    "inpaint",
                    status=StageStatus.FAILED,
                    error_code="provider_timeout",
                    error_message="nanobanana timeout",
                ),
                StaticStage(
                    "translation",
                    patches=[
                        PatchOperation(
                            op=PatchOp.SET_STAGE_META,
                            payload={"key": "translation", "value": {"should_not_run": True}},
                        )
                    ],
                    config={"provider": "translation_provider"},
                ),
            ]

            with self.assertLogs("model_engine.orchestrator", level="ERROR") as captured:
                result = orchestrator.run(document=document, stages=stages, runtime_context=runtime_context)

            self.assertEqual(StageStatus.FAILED, result.status)
            self.assertEqual(2, len(result.stage_reports))
            self.assertNotIn("translation", result.document.stage_meta)
            logs = "\n".join(captured.output)
            self.assertIn("model_stage_finished", logs)
            self.assertIn('"stage_name":"inpaint"', logs)
            self.assertIn('"status":"failed"', logs)
            self.assertIn('"error_code":"provider_timeout"', logs)
            self.assertNotIn("local-secret", logs)

    def test_stage_artifact_dump_writes_redacted_stage_boundary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            input_path = workspace / "input.png"
            output_path = workspace / "output.png"
            input_path.write_bytes(b"input-image")
            output_path.write_bytes(b"output-image")
            input_ref = "artifact://input/primary_bitmap"
            output_ref = "artifact://output/text_regions"
            orchestrator = PipelineOrchestrator(
                credential_resolver=DefaultCredentialResolver(environ={})
            )
            document = DocumentIR(id="doc_dump", name="page", width=10, height=10)
            runtime_context = StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri=workspace.resolve().as_uri(),
                session_provider_secrets={"nanobanana": "runtime-secret"},
                metadata={"stage_artifact_dump": True},
            )
            stage = StaticStage(
                "text_detection",
                artifacts={
                    output_ref: ArtifactDescriptor(
                        artifact_ref=output_ref,
                        kind="text_regions",
                        media_type="application/json",
                        uri=output_path.resolve().as_uri(),
                        producer_stage="text_detection",
                    )
                },
                config={"api_key": "stage-secret"},
            )

            result = orchestrator.run(
                document=document,
                stages=[stage],
                runtime_context=runtime_context,
                initial_artifacts={
                    input_ref: ArtifactDescriptor(
                        artifact_ref=input_ref,
                        kind="bitmap",
                        media_type="image/png",
                        uri=input_path.resolve().as_uri(),
                    )
                },
                job_id="job_dump",
                pipeline_id="pipe_dump",
            )

            self.assertEqual(StageStatus.SUCCEEDED, result.status)
            dump_dir = (
                workspace
                / "transactions"
                / "pipe_dump"
                / "text_detection"
                / "pipe_dump_text_detection_1"
                / "stage_artifact_dump"
            )
            self.assertTrue((dump_dir / "stage_request.json").is_file())
            self.assertTrue((dump_dir / "stage_response.json").is_file())
            self.assertTrue((dump_dir / "artifacts_before.json").is_file())
            self.assertTrue((dump_dir / "artifacts_after.json").is_file())
            self.assertTrue((dump_dir / "document_after.json").is_file())

            request_dump = (dump_dir / "stage_request.json").read_text(encoding="utf-8")
            self.assertNotIn("runtime-secret", request_dump)
            self.assertNotIn("stage-secret", request_dump)
            self.assertIn("[redacted]", request_dump)

            artifacts_after = json.loads((dump_dir / "artifacts_after.json").read_text(encoding="utf-8"))
            self.assertIn(input_ref, artifacts_after)
            self.assertIn(output_ref, artifacts_after)
            copied_input = json.loads((dump_dir / "copied_input_files.json").read_text(encoding="utf-8"))
            copied_output = json.loads((dump_dir / "copied_output_files.json").read_text(encoding="utf-8"))
            self.assertTrue(Path(copied_input[0]["dump_path"]).is_file())
            self.assertTrue(Path(copied_output[0]["dump_path"]).is_file())


def _write_local_credentials(tmpdir: str, *, provider: str, api_key: str) -> str:
    path = Path(tmpdir) / "credentials.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    provider: {
                        "api_key": api_key,
                        "updated_at": "2026-03-27T00:00:00Z",
                    }
                }
            }
        )
    )
    return str(path)


if __name__ == "__main__":
    unittest.main()
