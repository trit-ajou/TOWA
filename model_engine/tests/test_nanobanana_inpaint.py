from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.builtin_models.nanobanana_inpaint import (
    NANOBANANA_INPAINT_MODEL_ID,
    register_nanobanana_inpaint_model,
    run_nanobanana_inpaint,
)
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.credentials import (
    BillingMode,
    CredentialBinding,
    CredentialSource,
    ResolvedCredential,
)
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import StageKind
from model_engine.contracts.stages import (
    ExecutionMode,
    StageRequest,
    StageRuntimeContext,
    StageStatus,
)
from model_engine.contracts.text_regions import TextRegion, TextRegionsPayload
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage, run_mask_or_erase_planning


class NanobananaInpaintTests(unittest.TestCase):
    def test_mask_or_erase_planning_creates_tasks_and_masks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request = _planning_request(Path(tmpdir))

            response = run_mask_or_erase_planning(request)

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            task_artifacts = [
                descriptor for descriptor in response.artifacts.values() if descriptor.kind == "inpaint_tasks"
            ]
            mask_artifacts = [
                descriptor for descriptor in response.artifacts.values() if descriptor.kind == "erase_mask"
            ]
            self.assertEqual(1, len(task_artifacts))
            self.assertEqual(1, len(mask_artifacts))
            payload = json.loads(
                Path(task_artifacts[0].uri.removeprefix("file://")).read_text(encoding="utf-8")
            )
            self.assertEqual("layer_inpainting", payload["target_layer_id"])
            self.assertEqual(1, len(payload["tasks"]))

    def test_nanobanana_inpaint_composites_only_task_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            inpaint_request = _inpaint_request(Path(tmpdir), planning_response.artifacts)

            response = run_nanobanana_inpaint(
                inpaint_request,
                generate_edit_fn=_fake_generate_edit,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            bitmap_artifact = next(iter(response.artifacts.values()))
            output_image = Image.open(Path(bitmap_artifact.uri.removeprefix("file://"))).convert("RGBA")
            self.assertEqual((0, 255, 0, 255), output_image.getpixel((5, 5)))
            self.assertEqual((0, 0, 255, 255), output_image.getpixel((0, 0)))
            self.assertEqual("add_layer", response.patches[0].op.value)

    def test_registry_runs_nanobanana_inpaint_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            registry = ModelRegistry()
            register_nanobanana_inpaint_model(registry)
            stage = AdapterBackedStage(
                "inpaint",
                stage_kind=StageKind.INPAINT,
                registry=registry,
                preferred_model_id=NANOBANANA_INPAINT_MODEL_ID,
            )

            with patch(
                "model_engine.builtin_models.nanobanana_inpaint._generate_with_nanobanana_vertex",
                side_effect=_fake_generate_edit,
            ):
                response = stage.run(_inpaint_request(Path(tmpdir), planning_response.artifacts))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(NANOBANANA_INPAINT_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual(
                "preferred_model_id=builtin.nanobanana.inpaint",
                response.stage_report.metrics["selection_reason"],
            )


def _planning_request(workspace_dir: Path) -> StageRequest:
    image_path = workspace_dir / "page.png"
    _write_base_image(image_path)
    text_regions_path = workspace_dir / "text_regions.json"
    text_regions_path.write_text(
        json.dumps(
            TextRegionsPayload(
                schema_version="v1",
                detector="craft",
                source_artifact_ref="artifact://sample/input_bitmap",
                image_width=10,
                image_height=10,
                regions=[
                    TextRegion(
                        region_id="region_0001",
                        polygon=[],
                        bbox={"x": 4, "y": 4, "width": 2, "height": 2},
                        confidence=0.99,
                    )
                ],
                metadata={},
            ).to_dict(),
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_inpaint",
        job_id="job_inpaint",
        stage_name="mask_or_erase_planning",
        stage_run_id="pipe_inpaint:mask_or_erase_planning:1",
        document=DocumentIR(id="doc_inpaint", name="inpaint", width=10, height=10),
        artifacts={
            "artifact://sample/input_bitmap": ArtifactDescriptor(
                artifact_ref="artifact://sample/input_bitmap",
                kind="bitmap",
                media_type="image/png",
                uri=image_path.resolve().as_uri(),
                width=10,
                height=10,
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
            "padding": 0,
            "target_layer_id": "layer_inpainting",
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _inpaint_request(
    workspace_dir: Path,
    planning_artifacts: dict[str, ArtifactDescriptor],
) -> StageRequest:
    artifacts = dict(planning_artifacts)
    image_path = workspace_dir / "page.png"
    artifacts["artifact://sample/input_bitmap"] = ArtifactDescriptor(
        artifact_ref="artifact://sample/input_bitmap",
        kind="bitmap",
        media_type="image/png",
        uri=image_path.resolve().as_uri(),
        width=10,
        height=10,
    )
    binding = CredentialBinding(
        provider="nanobanana",
        credential_source=CredentialSource.USER_PERSONAL_SESSION,
        credential_id="session/nanobanana/active",
        credential_version="session",
        billing_mode=BillingMode.USER_DIRECT,
    )
    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_inpaint",
        job_id="job_inpaint",
        stage_name="inpaint",
        stage_run_id="pipe_inpaint:inpaint:1",
        document=DocumentIR(id="doc_inpaint", name="inpaint", width=10, height=10),
        artifacts=artifacts,
        credential_bindings={"primary_provider": binding},
        resolved_credentials={
            "primary_provider": ResolvedCredential(binding=binding, secrets={"api_key": "test-key"})
        },
        runtime_context=StageRuntimeContext(
            mode=ExecutionMode.LOCAL,
            workspace_uri=workspace_dir.resolve().as_uri(),
        ),
    )


def _write_base_image(path: Path) -> None:
    Image.new("RGBA", (10, 10), color=(0, 0, 255, 255)).save(path)


def _fake_generate_edit(
    crop_bytes: bytes,
    crop_mime_type: str,
    mask_bytes: bytes,
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    _ = crop_mime_type
    _ = mask_bytes
    _ = prompt
    _ = model_name
    _ = api_key
    crop = Image.open(BytesIO(crop_bytes)).convert("RGBA")
    edited = Image.new("RGBA", crop.size, color=(0, 255, 0, 255))
    buffer = BytesIO()
    edited.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
