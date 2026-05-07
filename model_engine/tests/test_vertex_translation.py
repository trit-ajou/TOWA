from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model_engine.builtin_models.vertex_translation import (
    VERTEX_TRANSLATION_MODEL_ID,
    register_vertex_translation_model,
    run_vertex_translation,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.credentials import (
    BillingMode,
    CredentialBinding,
    CredentialSource,
    ResolvedCredential,
)
from model_engine.contracts.document_ir import DocumentIR, TextBlock
from model_engine.contracts.models import StageKind
from model_engine.contracts.patches import apply_patches
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageRuntimeContext, StageStatus
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage


class VertexTranslationTests(unittest.TestCase):
    def test_run_vertex_translation_writes_translated_blocks_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _stage_request(Path(tmpdir))

            response = run_vertex_translation(
                request,
                translate_blocks_fn=_fake_translate_blocks,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("vertex_gemini_translation", response.stage_report.metrics["engine"])
            self.assertEqual(2, response.stage_report.metrics["translated_count"])
            self.assertEqual(1, len(response.artifacts))
            artifact = next(iter(response.artifacts.values()))
            self.assertEqual("translated_text_blocks", artifact.kind)
            artifact_path = Path(artifact.uri.removeprefix("file://"))
            self.assertIn("/transactions/pipe_translation_test/translation/", artifact_path.as_posix())
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("vertex_gemini_translation", payload["engine"])
            self.assertEqual("Korean", payload["target_language"])
            self.assertEqual("안녕", payload["blocks"][0]["translated_text"])
            self.assertEqual("replace_text_blocks", response.patches[0].op.value)

            document = request.document.clone()
            apply_patches(document, response.patches)
            self.assertEqual("안녕", document.text_blocks[0].translated_text)
            self.assertEqual("세계", document.text_blocks[1].translated_text)
            self.assertEqual("vertex_gemini_translation", document.stage_meta["translation"]["engine"])

    def test_registry_runs_builtin_vertex_translation_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry()
            register_vertex_translation_model(registry)
            stage = AdapterBackedStage(
                "translation",
                stage_kind=StageKind.TRANSLATION,
                registry=registry,
                preferred_model_id=VERTEX_TRANSLATION_MODEL_ID,
                config={
                    "provider": "translation_provider",
                    "source_language": "Japanese",
                    "target_language": "Korean",
                },
            )

            with patch(
                "model_engine.builtin_models.vertex_translation._translate_blocks_with_vertex",
                side_effect=_fake_translate_blocks,
            ):
                response = stage.run(_stage_request(Path(tmpdir)))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(VERTEX_TRANSLATION_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual(
                "preferred_model_id=builtin.vertex.translation",
                response.stage_report.metrics["selection_reason"],
            )


def _stage_request(workspace_dir: Path) -> StageRequest:
    binding = CredentialBinding(
        provider="translation_provider",
        credential_source=CredentialSource.USER_PERSONAL_SESSION,
        credential_id="session/translation_provider/active",
        credential_version="session",
        billing_mode=BillingMode.USER_DIRECT,
    )
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_translation_test",
        job_id="job_translation_test",
        stage_name="translation",
        stage_run_id="pipe_translation_test:translation:1",
        document=DocumentIR(
            id="doc_translation_test",
            name="translation-test",
            width=64,
            height=32,
            text_blocks=[
                TextBlock(
                    block_id="block_0001",
                    source_lang_text="こんにちは",
                    translated_text="",
                    bbox={"x": 2, "y": 2, "width": 10, "height": 8},
                    writing_mode="vertical",
                    source_region_ref="region_0001",
                ),
                TextBlock(
                    block_id="block_0002",
                    source_lang_text="世界",
                    translated_text="",
                    bbox={"x": 16, "y": 4, "width": 8, "height": 8},
                    writing_mode="vertical",
                    source_region_ref="region_0002",
                ),
            ],
        ),
        artifacts={
            "artifact://sample/input_bitmap": ArtifactDescriptor(
                artifact_ref="artifact://sample/input_bitmap",
                kind="bitmap",
                media_type="image/png",
                uri=(workspace_dir / "page.png").resolve().as_uri(),
                width=64,
                height=32,
            )
        },
        stage_config={
            "provider": "translation_provider",
            "source_language": "Japanese",
            "target_language": "Korean",
        },
        credential_bindings={"primary_provider": binding},
        resolved_credentials={
            "primary_provider": ResolvedCredential(binding=binding, secrets={"api_key": "test-key"})
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
            session_provider_secrets={"translation_provider": "test-key"},
        ),
    )


def _fake_translate_blocks(
    blocks: list[TextBlock],
    config: dict[str, object],
    api_key: str,
) -> list[dict[str, str]]:
    _ = config
    _ = api_key
    return [
        {"block_id": blocks[0].block_id, "translated_text": "안녕"},
        {"block_id": blocks[1].block_id, "translated_text": "세계"},
    ]


if __name__ == "__main__":
    unittest.main()
