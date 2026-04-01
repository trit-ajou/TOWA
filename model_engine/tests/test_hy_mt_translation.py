from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.document_ir import DocumentIR, TextBlock
from model_engine.contracts.patches import apply_patches
from model_engine.contracts.stages import ExecutionMode, StageRequest, StageRuntimeContext, StageStatus
from model_engine.custom_models.hy_mt_translation import run_hy_mt_translation


class HyMtTranslationTests(unittest.TestCase):
    def test_run_hy_mt_translation_writes_translated_blocks_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _stage_request(Path(tmpdir))

            response = run_hy_mt_translation(
                request,
                translate_blocks_fn=_fake_translate_blocks,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("hy_mt_translation", response.stage_report.metrics["engine"])
            self.assertEqual(2, response.stage_report.metrics["translated_count"])
            self.assertEqual(1, len(response.artifacts))
            artifact = next(iter(response.artifacts.values()))
            self.assertEqual("translated_text_blocks", artifact.kind)
            artifact_path = Path(artifact.uri.removeprefix("file://"))
            self.assertIn("/transactions/pipe_hy_mt_test/translation/", artifact_path.as_posix())
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual("hy_mt_translation", payload["engine"])
            self.assertEqual("Korean", payload["target_language"])
            self.assertEqual("안녕", payload["blocks"][0]["translated_text"])

            document = request.document.clone()
            apply_patches(document, response.patches)
            self.assertEqual("안녕", document.text_blocks[0].translated_text)
            self.assertEqual("세계", document.text_blocks[1].translated_text)
            self.assertEqual("hy_mt_translation", document.stage_meta["translation"]["engine"])


def _stage_request(workspace_dir: Path) -> StageRequest:
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_hy_mt_test",
        job_id="job_hy_mt_test",
        stage_name="translation",
        stage_run_id="pipe_hy_mt_test:translation:1",
        document=DocumentIR(
            id="doc_hy_mt_test",
            name="hy-mt-test",
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
            "source_language": "Japanese",
            "target_language": "Korean",
            "model_name": "tencent/HY-MT1.5-1.8B",
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _fake_translate_blocks(
    blocks: list[object],
    config: dict[str, object],
) -> list[dict[str, str]]:
    _ = config
    return [
        {"block_id": str(blocks[0].block_id), "translated_text": "안녕"},
        {"block_id": str(blocks[1].block_id), "translated_text": "세계"},
    ]


if __name__ == "__main__":
    unittest.main()
