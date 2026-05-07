from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model_engine.builtin_models.openai_compatible_translation import (
    OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
    _chat_completions_url,
    _chat_completion_response_text,
    _normalize_translation_entries,
    register_openai_compatible_translation_model,
    run_openai_compatible_translation,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR, TextBlock
from model_engine.contracts.models import StageKind
from model_engine.contracts.patches import apply_patches
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageRuntimeContext, StageStatus
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage


class OpenAICompatibleTranslationTests(unittest.TestCase):
    def test_run_openai_compatible_translation_does_not_require_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _stage_request(Path(tmpdir))

            response = run_openai_compatible_translation(
                request,
                translate_blocks_fn=_fake_translate_blocks,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("openai_compatible_translation", response.stage_report.metrics["engine"])
            self.assertEqual(2, response.stage_report.metrics["translated_count"])
            artifact = next(iter(response.artifacts.values()))
            payload = json.loads(Path(artifact.uri.removeprefix("file://")).read_text(encoding="utf-8"))
            self.assertEqual("openai_compatible_translation", payload["engine"])
            self.assertEqual("안녕", payload["blocks"][0]["translated_text"])

            document = request.document.clone()
            apply_patches(document, response.patches)
            self.assertEqual("세계", document.text_blocks[1].translated_text)

    def test_registry_runs_builtin_openai_compatible_translation_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry()
            register_openai_compatible_translation_model(registry)
            stage = AdapterBackedStage(
                "translation",
                stage_kind=StageKind.TRANSLATION,
                registry=registry,
                preferred_model_id=OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
                config={
                    "skip_provider_resolution": True,
                    "source_language": "Japanese",
                    "target_language": "Korean",
                },
            )

            with patch(
                "model_engine.builtin_models.openai_compatible_translation._translate_blocks_with_openai_compatible",
                side_effect=_fake_translate_blocks,
            ):
                response = stage.run(_stage_request(Path(tmpdir)))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(
                OPENAI_COMPATIBLE_TRANSLATION_MODEL_ID,
                response.stage_report.metrics["model_id"],
            )

    def test_chat_completion_helpers_accept_common_shapes(self) -> None:
        self.assertEqual(
            "http://127.0.0.1:1234/v1/chat/completions",
            _chat_completions_url("http://127.0.0.1:1234/v1"),
        )
        self.assertEqual(
            "hello",
            _chat_completion_response_text({"choices": [{"message": {"content": "hello"}}]}),
        )
        self.assertEqual(
            [{"block_id": "b1", "translated_text": "안녕"}],
            _normalize_translation_entries(
                {"translations": [{"block_id": "b1", "translated_text": "안녕"}]}
            ),
        )


def _stage_request(workspace_dir: Path) -> StageRequest:
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_openai_compatible_translation_test",
        job_id="job_openai_compatible_translation_test",
        stage_name="translation",
        stage_run_id="pipe_openai_compatible_translation_test:translation:1",
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
            "skip_provider_resolution": True,
            "base_url": "http://127.0.0.1:1234/v1",
            "source_language": "Japanese",
            "target_language": "Korean",
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _fake_translate_blocks(
    blocks: list[TextBlock],
    config: dict[str, object],
    api_key: str | None,
) -> list[dict[str, str]]:
    _ = config
    _ = api_key
    return [
        {"block_id": blocks[0].block_id, "translated_text": "안녕"},
        {"block_id": blocks[1].block_id, "translated_text": "세계"},
    ]


if __name__ == "__main__":
    unittest.main()
