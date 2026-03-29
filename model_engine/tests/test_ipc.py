from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext, StageStatus
from model_engine.credentials import DefaultCredentialResolver
from model_engine.ipc.process_stage import ProcessStage
from model_engine.orchestrator import PipelineOrchestrator


class IpcStageTests(unittest.TestCase):
    def test_process_stage_runs_over_subprocess_ipc(self) -> None:
        orchestrator = PipelineOrchestrator()
        document = DocumentIR(id="doc_ipc", name="ipc", width=100, height=100)
        runtime_context = StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri="file:///tmp/towa/ipc-run",
            requested_by="tester",
        )
        stages = [
            ProcessStage(
                "text_detection",
                handler="model_engine.stages.ipc_demo:append_demo_text_block",
            )
        ]

        result = orchestrator.run(document=document, stages=stages, runtime_context=runtime_context)

        self.assertEqual(StageStatus.SUCCEEDED, result.status)
        self.assertEqual(1, len(result.document.text_blocks))
        self.assertEqual("text_detection-block", result.document.text_blocks[0].block_id)
        self.assertEqual("subprocess_json", result.stage_reports[0].metrics["transport"])

    def test_process_stage_failure_stops_pipeline(self) -> None:
        orchestrator = PipelineOrchestrator()
        document = DocumentIR(id="doc_ipc_fail", name="ipc-fail", width=100, height=100)
        runtime_context = StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri="file:///tmp/towa/ipc-run-fail",
        )
        stages = [
            ProcessStage(
                "text_detection",
                handler="model_engine.stages.ipc_demo:fail_demo_stage",
            ),
            ProcessStage(
                "ocr",
                handler="model_engine.stages.ipc_demo:append_demo_text_block",
            ),
        ]

        result = orchestrator.run(document=document, stages=stages, runtime_context=runtime_context)

        self.assertEqual(StageStatus.FAILED, result.status)
        self.assertEqual(1, len(result.stage_reports))
        self.assertEqual("demo_failure", result.stage_reports[0].error_code)
        self.assertEqual(0, len(result.document.text_blocks))

    def test_process_stage_receives_credential_env_from_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = DefaultCredentialResolver(
                credentials_file=_write_local_credentials(tmpdir, provider="nanobanana", api_key="local-secret"),
                environ={},
            )
            orchestrator = PipelineOrchestrator(credential_resolver=resolver)
            document = DocumentIR(id="doc_ipc_env", name="ipc-env", width=100, height=100)
            runtime_context = StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri="file:///tmp/towa/ipc-env",
            )
            stages = [
                ProcessStage(
                    "inpaint",
                    handler="model_engine.stages.ipc_demo:echo_provider_env",
                )
            ]

            result = orchestrator.run(document=document, stages=stages, runtime_context=runtime_context)

            self.assertEqual(StageStatus.SUCCEEDED, result.status)
            self.assertEqual("nanobanana", result.stage_reports[0].metrics["provider_name"])
            self.assertEqual("yes", result.stage_reports[0].metrics["secret_present"])
            self.assertEqual("user_personal_persisted", result.stage_reports[0].metrics["credential_source"])


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
