from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from model_engine.builtin_models.nanobanana_inpaint import (
    MINDLOGIC_IMAGE_MODEL,
    MINDLOGIC_INPAINT_MODEL_ID,
    NANOBANANA_DEFAULT_PROMPT,
    NANOBANANA_IMAGE_MODEL,
    NANOBANANA_INPAINT_MODEL_ID,
    _generate_with_mindlogic_gateway_image,
    _missing_image_error,
    _image_part_to_png_bytes,
    register_mindlogic_inpaint_model,
    register_nanobanana_inpaint_model,
    run_nanobanana_inpaint,
)
from model_engine.contracts.artifacts import ArtifactDescriptor, ArtifactStatus
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
    def test_mindlogic_inpaint_defaults_to_stable_gateway_edit_model(self) -> None:
        self.assertEqual("gemini-2.5-flash-image", MINDLOGIC_IMAGE_MODEL)
        self.assertNotEqual(NANOBANANA_IMAGE_MODEL, MINDLOGIC_IMAGE_MODEL)

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
            task_path = Path(task_artifacts[0].uri.removeprefix("file://"))
            self.assertIn(
                "/transactions/pipe_inpaint/mask_or_erase_planning/pipe_inpaint_mask_or_erase_planning_1/",
                task_path.as_posix(),
            )

    def test_nanobanana_inpaint_composites_only_task_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            inpaint_request = _inpaint_request(Path(tmpdir), planning_response.artifacts)

            response = run_nanobanana_inpaint(
                inpaint_request,
                generate_edit_fn=_fake_generate_edit,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(2, len(response.artifacts))
            bitmap_artifact = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "inpainting_layer_bitmap"
            )
            provider_artifact = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "provider_output_bitmap"
            )
            output_image = Image.open(Path(bitmap_artifact.uri.removeprefix("file://"))).convert("RGBA")
            self.assertEqual((0, 255, 0, 255), output_image.getpixel((5, 5)))
            self.assertEqual((0, 0, 0, 0), output_image.getpixel((0, 0)))
            self.assertEqual("add_layer", response.patches[0].op.value)
            self.assertEqual(
                "full_page_single_call",
                response.stage_report.metrics["provider_call_mode"],
            )
            provider_image = Image.open(Path(provider_artifact.uri.removeprefix("file://"))).convert("RGBA")
            self.assertEqual((0, 255, 0, 255), provider_image.getpixel((0, 0)))
            output_path = Path(bitmap_artifact.uri.removeprefix("file://"))
            self.assertIn(
                "/transactions/pipe_inpaint/inpaint/pipe_inpaint_inpaint_1/",
                output_path.as_posix(),
            )

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

    def test_registry_runs_mindlogic_inpaint_with_shared_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            registry = ModelRegistry()
            register_mindlogic_inpaint_model(registry)
            stage = AdapterBackedStage(
                "inpaint",
                stage_kind=StageKind.INPAINT,
                registry=registry,
                preferred_model_id=MINDLOGIC_INPAINT_MODEL_ID,
                config={"provider": "mindlogic"},
            )
            captured: dict[str, str] = {}

            def _capture_generate_edit(
                reference_images: list[tuple[bytes, str]],
                prompt: str,
                model_name: str,
                api_key: str,
            ) -> bytes:
                captured["reference_count"] = str(len(reference_images))
                captured["source_mime_type"] = reference_images[0][1]
                captured["prompt"] = prompt
                captured["model_name"] = model_name
                captured["api_key"] = api_key
                return _fake_generate_edit(
                    reference_images,
                    prompt,
                    model_name,
                    api_key,
                )

            with patch(
                "model_engine.builtin_models.nanobanana_inpaint._generate_with_mindlogic_gateway_image",
                side_effect=_capture_generate_edit,
            ):
                response = stage.run(
                    _inpaint_request(
                        Path(tmpdir),
                        planning_response.artifacts,
                        provider="mindlogic",
                    )
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertIn(NANOBANANA_DEFAULT_PROMPT, captured["prompt"])
            self.assertIn("exactly 10x10 pixels", captured["prompt"])
            self.assertIn("Do not crop, pad, rotate, stretch, zoom", captured["prompt"])
            self.assertEqual(MINDLOGIC_IMAGE_MODEL, captured["model_name"])
            self.assertEqual("1", captured["reference_count"])
            self.assertEqual("image/png", captured["source_mime_type"])
            self.assertEqual("test-key", captured["api_key"])
            self.assertEqual("mindlogic", response.stage_report.metrics["provider"])
            self.assertEqual("10x10", response.stage_report.metrics["prompt_output_size"])
            self.assertEqual(1, response.stage_report.metrics["provider_reference_image_count"])
            self.assertEqual("no", response.stage_report.metrics["provider_mask_guide"])
            self.assertEqual(MINDLOGIC_INPAINT_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual("mindlogic_gateway_nanobanana", response.patches[1].payload["value"]["engine"])

    def test_registry_runs_mindlogic_inpaint_with_bitmap_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            _write_base_image(workspace_dir / "page.png")
            registry = ModelRegistry()
            register_mindlogic_inpaint_model(registry)
            stage = AdapterBackedStage(
                "inpaint",
                stage_kind=StageKind.INPAINT,
                registry=registry,
                preferred_model_id=MINDLOGIC_INPAINT_MODEL_ID,
                config={"provider": "mindlogic"},
            )

            with patch(
                "model_engine.builtin_models.nanobanana_inpaint._generate_with_mindlogic_gateway_image",
                side_effect=_fake_generate_edit,
            ):
                response = stage.run(
                    _inpaint_request(
                        workspace_dir,
                        {},
                        provider="mindlogic",
                    )
                )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual(MINDLOGIC_INPAINT_MODEL_ID, response.stage_report.metrics["model_id"])
            self.assertEqual("0", str(response.stage_report.metrics["task_count"]))
            self.assertEqual("full_page", response.stage_report.metrics["composite_mask_mode"])
            self.assertEqual("mindlogic_gateway_nanobanana", response.patches[1].payload["value"]["engine"])

    def test_mindlogic_gateway_uses_nanobanana_image_route(self) -> None:
        source_image = Image.new("RGBA", (2, 2), color=(1, 2, 3, 255))
        source_buffer = BytesIO()
        source_image.save(source_buffer, format="PNG")
        output_buffer = BytesIO()
        Image.new("RGBA", (2, 2), color=(4, 5, 6, 255)).save(output_buffer, format="PNG")
        output_url = "data:image/png;base64," + base64.b64encode(output_buffer.getvalue()).decode("ascii")
        captured: dict[str, object] = {}

        def _fake_post(url: str, *, payload: dict[str, object], api_key: str, timeout: float) -> dict[str, object]:
            captured["url"] = url
            captured["payload"] = payload
            captured["api_key"] = api_key
            captured["timeout"] = timeout
            return {"data": [{"url": output_url}]}

        with patch(
            "model_engine.builtin_models.nanobanana_inpaint._post_mindlogic_json",
            side_effect=_fake_post,
        ):
            generated = _generate_with_mindlogic_gateway_image(
                [(source_buffer.getvalue(), "image/png")],
                "remove text",
                MINDLOGIC_IMAGE_MODEL,
                "test-key",
            )

        self.assertEqual(output_buffer.getvalue(), generated)
        self.assertTrue(str(captured["url"]).endswith("/images/generate/"))
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(MINDLOGIC_IMAGE_MODEL, payload["model"])
        self.assertEqual("remove text", payload["prompt"])
        self.assertEqual(1, payload["number_of_images"])
        self.assertTrue(str(payload["image"]).startswith("data:image/png;base64,"))
        self.assertEqual("test-key", captured["api_key"])

    def test_bitmap_only_inpaint_writes_full_provider_output_for_ui_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            _write_base_image(workspace_dir / "page.png")

            response = run_nanobanana_inpaint(
                _inpaint_request(workspace_dir, {}),
                generate_edit_fn=_fake_generate_edit_partial,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("full_page", response.stage_report.metrics["composite_mask_mode"])
            bitmap_artifact = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "inpainting_layer_bitmap"
            )
            provider_artifact = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "provider_output_bitmap"
            )
            output_image = Image.open(Path(bitmap_artifact.uri.removeprefix("file://"))).convert("RGBA")
            provider_image = Image.open(Path(provider_artifact.uri.removeprefix("file://"))).convert("RGBA")
            self.assertEqual((0, 0, 255, 255), output_image.getpixel((0, 0)))
            self.assertEqual((0, 255, 0, 255), output_image.getpixel((5, 5)))
            self.assertEqual((0, 0, 255, 255), provider_image.getpixel((0, 0)))
            self.assertEqual((0, 255, 0, 255), provider_image.getpixel((5, 5)))

    def test_nanobanana_inpaint_resizes_provider_output_to_base_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            inpaint_request = _inpaint_request(Path(tmpdir), planning_response.artifacts)

            response = run_nanobanana_inpaint(
                inpaint_request,
                generate_edit_fn=_fake_generate_edit_resized,
            )

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("yes", response.stage_report.metrics["provider_output_resized"])
            self.assertTrue(response.stage_report.warnings)
            bitmap_artifact = next(iter(response.artifacts.values()))
            output_image = Image.open(Path(bitmap_artifact.uri.removeprefix("file://"))).convert("RGBA")
            self.assertEqual((10, 200, 20, 255), output_image.getpixel((5, 5)))
            self.assertEqual((10, 10), output_image.size)

    def test_nanobanana_inpaint_retains_failure_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            planning_response = run_mask_or_erase_planning(_planning_request(Path(tmpdir)))
            inpaint_request = _inpaint_request(Path(tmpdir), planning_response.artifacts)

            response = run_nanobanana_inpaint(
                inpaint_request,
                generate_edit_fn=_failing_generate_edit,
            )

            self.assertEqual(StageStatus.FAILED, response.status)
            self.assertEqual("provider_timeout", response.stage_report.error_code)
            self.assertEqual("yes", response.stage_report.metrics["snapshot_retained"])
            self.assertEqual(2, len(response.artifacts))

            partial_bitmap = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "partial_inpainting_snapshot"
            )
            self.assertEqual(ArtifactStatus.FAILED, partial_bitmap.status)
            partial_bitmap_image = Image.open(
                Path(partial_bitmap.uri.removeprefix("file://"))
            ).convert("RGBA")
            self.assertEqual((0, 0, 0, 0), partial_bitmap_image.getpixel((0, 0)))

            failure_snapshot = next(
                descriptor
                for descriptor in response.artifacts.values()
                if descriptor.metadata.get("role") == "failure_snapshot"
            )
            snapshot_payload = json.loads(
                Path(failure_snapshot.uri.removeprefix("file://")).read_text(encoding="utf-8")
            )
            self.assertEqual("provider_timeout", snapshot_payload["error_code"])
            self.assertEqual(partial_bitmap.artifact_ref, snapshot_payload["partial_bitmap_ref"])

    def test_image_part_to_png_bytes_prefers_inline_data(self) -> None:
        image = Image.new("RGBA", (2, 2), color=(12, 34, 56, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        payload = buffer.getvalue()

        class _InlineData:
            def __init__(self, data: bytes) -> None:
                self.data = data

        class _Part:
            def __init__(self, data: bytes) -> None:
                self.inline_data = _InlineData(data)

        converted = _image_part_to_png_bytes(_Part(payload))
        self.assertEqual(payload, converted)

    def test_missing_image_error_includes_text_and_finish_reason(self) -> None:
        class _Part:
            def __init__(self, text: str) -> None:
                self.text = text

        class _Content:
            def __init__(self, parts: list[object]) -> None:
                self.parts = parts

        class _Candidate:
            def __init__(self) -> None:
                self.finish_reason = "STOP"
                self.content = _Content([_Part("image generation blocked")])

        class _Response:
            def __init__(self) -> None:
                self.candidates = [_Candidate()]
                self.prompt_feedback = "safety_check_passed"

        error_message = _missing_image_error(_Response(), ["image generation blocked"])
        self.assertIn("did not include an image", error_message)
        self.assertIn("finish_reasons=STOP", error_message)
        self.assertIn("text_response=image generation blocked", error_message)


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
    *,
    provider: str = "nanobanana",
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
        provider=provider,
        credential_source=CredentialSource.USER_PERSONAL_SESSION,
        credential_id=f"session/{provider}/active",
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
    reference_images: list[tuple[bytes, str]],
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    _ = prompt
    _ = model_name
    _ = api_key
    source_image_bytes, _source_mime_type = reference_images[0]
    source_image = Image.open(BytesIO(source_image_bytes)).convert("RGBA")
    edited = Image.new("RGBA", source_image.size, color=(0, 255, 0, 255))
    buffer = BytesIO()
    edited.save(buffer, format="PNG")
    return buffer.getvalue()


def _fake_generate_edit_partial(
    reference_images: list[tuple[bytes, str]],
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    _ = prompt
    _ = model_name
    _ = api_key
    source_image_bytes, _source_mime_type = reference_images[0]
    edited = Image.open(BytesIO(source_image_bytes)).convert("RGBA")
    edited.putpixel((5, 5), (0, 255, 0, 255))
    buffer = BytesIO()
    edited.save(buffer, format="PNG")
    return buffer.getvalue()


def _failing_generate_edit(
    reference_images: list[tuple[bytes, str]],
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    _ = reference_images
    _ = prompt
    _ = model_name
    _ = api_key
    raise TimeoutError("provider stalled")


def _fake_generate_edit_resized(
    reference_images: list[tuple[bytes, str]],
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    _ = reference_images
    _ = prompt
    _ = model_name
    _ = api_key
    edited = Image.new("RGBA", (8, 8), color=(10, 200, 20, 255))
    buffer = BytesIO()
    edited.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
