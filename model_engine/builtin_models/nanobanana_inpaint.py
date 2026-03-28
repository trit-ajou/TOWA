from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from PIL import Image

from ..adapters.callable import CallableModelAdapter
from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.models import ResourceProfile, StageKind, StageManifest
from ..contracts.patches import PatchOperation
from ..contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageStatus,
)
from ..contracts.inpaint_tasks import inpaint_tasks_payload_from_mapping
from ..models.registry import ModelRegistry


NANOBANANA_INPAINT_MODEL_ID = "builtin.nanobanana.inpaint"
NANOBANANA_IMAGE_MODEL = "gemini-2.5-flash-image"
NANOBANANA_DEFAULT_PROMPT = (
    "Use image 1 as the original manga page and image 2 as the edit guide. "
    "White areas in image 2 mark regions to edit, black areas must remain unchanged. "
    "Remove all visible source text, speech balloon text, and sound effects only inside the "
    "white regions. Reconstruct the underlying manga background, lineart, screentones, and "
    "balloon interiors naturally. Do not add any new text. Preserve composition, character art, "
    "panel borders, and all pixels outside the mask as faithfully as possible."
)


def build_nanobanana_inpaint_manifest() -> StageManifest:
    from ..contracts.credentials import BillingMode, CredentialSource

    return StageManifest(
        model_id=NANOBANANA_INPAINT_MODEL_ID,
        adapter_id="adapter.builtin.nanobanana.inpaint",
        stage_kind=StageKind.INPAINT,
        required_artifact_kinds=["bitmap", "inpaint_tasks"],
        produced_artifact_kinds=["bitmap"],
        supported_modes=[ExecutionMode.LOCAL, ExecutionMode.SAAS],
        allowed_credential_sources=[
            CredentialSource.USER_PERSONAL_PERSISTED,
            CredentialSource.USER_PERSONAL_SESSION,
            CredentialSource.PLATFORM_MANAGED,
        ],
        billing_modes=[BillingMode.USER_DIRECT, BillingMode.PLATFORM_CREDIT],
        resource_profile=ResourceProfile(
            cpu_threads=1,
            memory_mb=1024,
            gpu_required=False,
            latency_tier="network",
        ),
        custom_model=False,
        priority=50,
        display_name="Nanobanana Inpaint",
        tags=["builtin", "nanobanana", "inpaint", "vertexai"],
    )


def build_nanobanana_inpaint_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_nanobanana_inpaint_manifest(),
        import_path="model_engine.builtin_models.nanobanana_inpaint:nanobanana_inpaint_handler",
    )


def register_nanobanana_inpaint_model(registry: ModelRegistry) -> str:
    registry.register(build_nanobanana_inpaint_adapter())
    return NANOBANANA_INPAINT_MODEL_ID


def nanobanana_inpaint_handler(request: StageRequest) -> StageResponse:
    return run_nanobanana_inpaint(request)


def run_nanobanana_inpaint(
    request: StageRequest,
    *,
    generate_edit_fn: Optional[
        Callable[[bytes, str, bytes, str, str], bytes]
    ] = None,
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    tasks_artifact = _resolve_inpaint_tasks_artifact(request)
    tasks_payload = inpaint_tasks_payload_from_mapping(
        json.loads(_file_path_from_uri(tasks_artifact.uri).read_text(encoding="utf-8"))
    )
    if not tasks_payload.tasks:
        raise ValueError("Nanobanana inpaint requires at least one inpaint task")

    target_layer_id = tasks_payload.target_layer_id
    if target_layer_id != "layer_inpainting":
        raise ValueError("Nanobanana inpaint can only target layer_inpainting")

    base_artifact = request.artifacts[tasks_payload.source_artifact_ref]
    base_image = Image.open(_file_path_from_uri(base_artifact.uri)).convert("RGBA")
    edited_image = base_image.copy()

    generate_edit_fn = generate_edit_fn or _generate_with_nanobanana_vertex
    request_provider = request.resolved_credentials.get("primary_provider")
    if request_provider is None:
        raise RuntimeError("Nanobanana inpaint requires primary_provider credentials")
    api_key = request_provider.secret("api_key")
    if not api_key:
        raise RuntimeError("Nanobanana inpaint requires an API key")

    prompt_override = request.stage_config.get("prompt")
    model_name = str(request.stage_config.get("model_name", NANOBANANA_IMAGE_MODEL))
    prompt = str(prompt_override or NANOBANANA_DEFAULT_PROMPT)

    for task in tasks_payload.tasks:
        if task.target_layer_id != "layer_inpainting":
            raise ValueError("Nanobanana inpaint task attempted to target a non-inpainting layer")
        expanded_bbox = task.expanded_bbox
        crop_box = (
            expanded_bbox["x"],
            expanded_bbox["y"],
            expanded_bbox["x"] + expanded_bbox["width"],
            expanded_bbox["y"] + expanded_bbox["height"],
        )
        crop_image = edited_image.crop(crop_box)
        crop_bytes = _image_to_bytes(crop_image, format_hint="PNG")
        mask_artifact = request.artifacts[task.mask_artifact_ref]
        mask_path = _file_path_from_uri(mask_artifact.uri)
        mask_bytes = mask_path.read_bytes()
        generated_bytes = generate_edit_fn(crop_bytes, "image/png", mask_bytes, prompt, model_name, api_key)
        generated_crop = Image.open(BytesIO(generated_bytes)).convert("RGBA")
        edited_image.paste(generated_crop, (expanded_bbox["x"], expanded_bbox["y"]))

    output_artifact = _write_inpainted_bitmap(request, edited_image, target_layer_id)
    patches = _patches_for_inpainting_layer(request, output_artifact.artifact_ref, target_layer_id)
    finished_at = datetime.now(timezone.utc)
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[output_artifact.artifact_ref],
        warnings=[],
        metrics={
            "provider": "nanobanana",
            "model_name": model_name,
            "task_count": len(tasks_payload.tasks),
            "target_layer_id": target_layer_id,
        },
        provider=request.credential_bindings.get("primary_provider"),
        started_at=started_at,
        finished_at=finished_at,
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        patches=patches,
        artifacts={output_artifact.artifact_ref: output_artifact},
        stage_report=report,
    )


def _resolve_inpaint_tasks_artifact(request: StageRequest) -> ArtifactDescriptor:
    preferred_ref = request.stage_config.get("inpaint_tasks_ref")
    if isinstance(preferred_ref, str):
        artifact = request.artifacts.get(preferred_ref)
        if artifact is None:
            raise KeyError(f"Configured inpaint_tasks_ref not found: {preferred_ref}")
        return artifact
    for artifact in request.artifacts.values():
        if artifact.kind == "inpaint_tasks":
            return artifact
    raise ValueError("Nanobanana inpaint requires an inpaint_tasks artifact")


def _file_path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise RuntimeError("Nanobanana inpaint currently supports only file:// artifacts")
    return Path(parsed.path)


def _image_to_bytes(image: Image.Image, *, format_hint: str) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=format_hint)
    return buffer.getvalue()


def _generate_with_nanobanana_vertex(
    crop_bytes: bytes,
    crop_mime_type: str,
    mask_bytes: bytes,
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Add it to the local environment or Docker image before running nanobanana inpaint."
        ) from exc

    client = genai.Client(vertexai=True, api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=crop_bytes, mime_type=crop_mime_type),
            types.Part.from_bytes(data=mask_bytes, mime_type="image/png"),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in _iter_response_parts(response):
        if getattr(part, "inline_data", None):
            image = part.as_image()
            return _image_to_bytes(image.convert("RGBA"), format_hint="PNG")
    raise RuntimeError("Nanobanana Vertex AI response did not include an image")


def _iter_response_parts(response: object) -> list[object]:
    direct_parts = getattr(response, "parts", None)
    if direct_parts:
        return list(direct_parts)

    parts: list[object] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if content and getattr(content, "parts", None):
            parts.extend(list(content.parts))
    return parts


def _write_inpainted_bitmap(
    request: StageRequest,
    image: Image.Image,
    target_layer_id: str,
) -> ArtifactDescriptor:
    workspace_dir = _workspace_path(request)
    stage_dir = workspace_dir / request.pipeline_id / request.stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    output_path = stage_dir / f"{request.stage_run_id.replace(':', '_')}_inpainting.png"
    image.save(output_path)
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/"
        f"{request.stage_run_id.replace(':', '_')}/inpainting_bitmap"
    )
    return ArtifactDescriptor(
        artifact_ref=artifact_ref,
        kind="bitmap",
        media_type="image/png",
        uri=output_path.resolve().as_uri(),
        width=image.width,
        height=image.height,
        byte_size=output_path.stat().st_size,
        producer_stage=request.stage_name,
        metadata={"target_layer_id": target_layer_id, "role": "inpainting_layer_bitmap"},
    )


def _patches_for_inpainting_layer(
    request: StageRequest,
    artifact_ref: str,
    target_layer_id: str,
) -> list[PatchOperation]:
    existing_layer = request.document.get_layer(target_layer_id)
    if existing_layer is None:
        return [
            PatchOperation(
                op="add_layer",
                payload={
                    "layer": {
                        "id": target_layer_id,
                        "name": "Inpainting Layer",
                        "type": "graphic",
                        "left": 0,
                        "top": 0,
                        "width": request.document.width,
                        "height": request.document.height,
                        "visible": True,
                        "transparent": True,
                        "source_ref": artifact_ref,
                        "props": {"role": "inpainting_layer"},
                    }
                },
            ),
            PatchOperation(
                op="set_stage_meta",
                payload={
                    "key": "inpaint",
                    "value": {
                        "engine": "nanobanana_vertex",
                        "target_layer_id": target_layer_id,
                        "artifact_ref": artifact_ref,
                    },
                },
            ),
        ]
    return [
        PatchOperation(
            op="replace_source_ref",
            target={"layer_id": target_layer_id},
            payload={"source_ref": artifact_ref},
        ),
        PatchOperation(
            op="set_stage_meta",
            payload={
                "key": "inpaint",
                "value": {
                    "engine": "nanobanana_vertex",
                    "target_layer_id": target_layer_id,
                    "artifact_ref": artifact_ref,
                },
            },
        ),
    ]


def _workspace_path(request: StageRequest) -> Path:
    if request.runtime_context is None:
        return Path("/tmp/towa/workspace")
    parsed = urlparse(request.runtime_context.workspace_uri)
    if parsed.scheme != "file":
        raise RuntimeError("Nanobanana inpaint requires file:// workspace_uri")
    return Path(parsed.path)
