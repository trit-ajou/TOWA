from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Callable, Optional
from urllib import error, request
from urllib.parse import urlparse

from PIL import Image

from ..adapters.callable import CallableModelAdapter
from ..contracts.artifacts import ArtifactDescriptor, ArtifactStatus
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
from ..storage import stage_run_slug, stage_transaction_dir


NANOBANANA_INPAINT_MODEL_ID = "builtin.nanobanana.inpaint"
NANOBANANA_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
MINDLOGIC_INPAINT_MODEL_ID = "builtin.mindlogic.inpaint"
MINDLOGIC_IMAGE_MODEL = "imagen-3.0-capability-001"
MINDLOGIC_IMAGE_EDIT_BASE_URL = "https://factchat-cloud.mindlogic.ai/v1/api/google"
MINDLOGIC_IMAGE_EDIT_PATH = "/models/edit-image"
MINDLOGIC_IMAGE_EDIT_MODE = "EDIT_MODE_DEFAULT"
NANOBANANA_DEFAULT_PROMPT = (
    "Use the provided manga page as the source image. "
    "Remove all visible source text, speech balloon text, and sound effects from the page. "
    "Reconstruct the underlying manga background, lineart, screentones, and balloon interiors naturally. "
    "Do not add any new text. Preserve composition, character art, panel borders, and the rest of the page "
    "as faithfully as possible."
)


def build_nanobanana_inpaint_manifest() -> StageManifest:
    from ..contracts.credentials import BillingMode, CredentialSource

    return StageManifest(
        model_id=NANOBANANA_INPAINT_MODEL_ID,
        adapter_id="adapter.builtin.nanobanana.inpaint",
        stage_kind=StageKind.INPAINT,
        required_artifact_kinds=["bitmap"],
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


def build_mindlogic_inpaint_manifest() -> StageManifest:
    from ..contracts.credentials import BillingMode, CredentialSource

    return StageManifest(
        model_id=MINDLOGIC_INPAINT_MODEL_ID,
        adapter_id="adapter.builtin.mindlogic.inpaint",
        stage_kind=StageKind.INPAINT,
        required_artifact_kinds=["bitmap"],
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
        display_name="Mindlogic Image Edit Inpaint",
        tags=["builtin", "mindlogic", "inpaint", "google-edit"],
    )


def build_nanobanana_inpaint_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_nanobanana_inpaint_manifest(),
        import_path="model_engine.builtin_models.nanobanana_inpaint:nanobanana_inpaint_handler",
    )


def build_mindlogic_inpaint_adapter() -> CallableModelAdapter:
    return CallableModelAdapter.from_import_path(
        build_mindlogic_inpaint_manifest(),
        import_path="model_engine.builtin_models.nanobanana_inpaint:mindlogic_inpaint_handler",
    )


def register_nanobanana_inpaint_model(registry: ModelRegistry) -> str:
    registry.register(build_nanobanana_inpaint_adapter())
    return NANOBANANA_INPAINT_MODEL_ID


def register_mindlogic_inpaint_model(registry: ModelRegistry) -> str:
    registry.register(build_mindlogic_inpaint_adapter())
    return MINDLOGIC_INPAINT_MODEL_ID


def nanobanana_inpaint_handler(request: StageRequest) -> StageResponse:
    return run_nanobanana_inpaint(request)


def mindlogic_inpaint_handler(request: StageRequest) -> StageResponse:
    return run_nanobanana_inpaint(
        request,
        generate_edit_fn=_generate_with_mindlogic_google_edit,
        default_model_name=MINDLOGIC_IMAGE_MODEL,
        provider_name="mindlogic",
        engine_name="mindlogic_google_edit",
    )


def run_nanobanana_inpaint(
    request: StageRequest,
    *,
    generate_edit_fn: Optional[
        Callable[[bytes, str, str, str, str], bytes]
    ] = None,
    default_model_name: str = NANOBANANA_IMAGE_MODEL,
    provider_name: str = "nanobanana",
    engine_name: str = "nanobanana_vertex",
) -> StageResponse:
    started_at = datetime.now(timezone.utc)
    target_layer_id = str(request.stage_config.get("target_layer_id", "layer_inpainting"))

    tasks_payload = _try_resolve_inpaint_tasks(request)
    use_mask = tasks_payload is not None and len(tasks_payload.tasks) > 0

    if use_mask:
        base_artifact = request.artifacts[tasks_payload.source_artifact_ref]
    else:
        input_ref = str(request.stage_config.get("input_artifact_ref", ""))
        if input_ref and input_ref in request.artifacts:
            base_artifact = request.artifacts[input_ref]
        else:
            base_artifact = _resolve_first_bitmap_artifact(request)

    base_image = Image.open(_file_path_from_uri(base_artifact.uri)).convert("RGBA")

    generate_edit_fn = generate_edit_fn or _generate_with_nanobanana_vertex
    request_provider = request.resolved_credentials.get("primary_provider")
    if request_provider is None:
        raise RuntimeError("Nanobanana inpaint requires primary_provider credentials")
    api_key = request_provider.secret("api_key")
    if not api_key:
        raise RuntimeError("Nanobanana inpaint requires an API key")

    prompt_override = request.stage_config.get("prompt")
    model_name = str(request.stage_config.get("model_name", default_model_name))
    prompt = str(prompt_override or NANOBANANA_DEFAULT_PROMPT)
    warnings: list[str] = []

    try:
        page_bytes = _image_to_bytes(base_image, format_hint="PNG")
        generated_bytes = generate_edit_fn(
            page_bytes,
            "image/png",
            prompt,
            model_name,
            api_key,
        )
        generated_page = Image.open(BytesIO(generated_bytes)).convert("RGBA")
        generated_page, resize_warning = _normalize_generated_page_size(generated_page, base_image.size)
        if resize_warning is not None:
            warnings.append(resize_warning)
        provider_output_artifact = _write_provider_output_bitmap(
            request,
            generated_page,
            provider_name,
        )

        if use_mask:
            edited_image = _initial_inpainting_canvas(request, base_image, target_layer_id)
            composite_mask = _build_composite_mask(request, tasks_payload, base_image.size)
            edited_image.paste(generated_page, (0, 0), composite_mask)
        else:
            edited_image = generated_page
    except Exception as exc:
        return _failed_response(
            request,
            started_at=started_at,
            edited_image=Image.new("RGBA", base_image.size, color=(0, 0, 0, 0)),
            tasks_payload=tasks_payload,
            model_name=model_name,
            provider_name=provider_name,
            error=exc,
        )

    output_artifact = _write_inpainted_bitmap(request, edited_image, target_layer_id)
    patches = _patches_for_inpainting_layer(
        request,
        output_artifact.artifact_ref,
        target_layer_id,
        engine_name,
    )
    finished_at = datetime.now(timezone.utc)
    task_count = len(tasks_payload.tasks) if tasks_payload else 0
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.SUCCEEDED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=[provider_output_artifact.artifact_ref, output_artifact.artifact_ref],
        warnings=warnings,
        metrics={
            "provider": provider_name,
            "model_name": model_name,
            "task_count": task_count,
            "target_layer_id": target_layer_id,
            "provider_call_mode": "full_page_single_call",
            "composite_mask_mode": "local_mask_only" if use_mask else "none",
            "provider_output_size": f"{generated_page.width}x{generated_page.height}",
            "base_image_size": f"{base_image.width}x{base_image.height}",
            "provider_output_resized": "yes" if resize_warning is not None else "no",
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
        artifacts={
            provider_output_artifact.artifact_ref: provider_output_artifact,
            output_artifact.artifact_ref: output_artifact,
        },
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


def _try_resolve_inpaint_tasks(request: StageRequest) -> Optional[object]:
    """Resolve inpaint_tasks artifact if available, return None otherwise."""
    try:
        tasks_artifact = _resolve_inpaint_tasks_artifact(request)
    except (ValueError, KeyError):
        return None
    return inpaint_tasks_payload_from_mapping(
        json.loads(_file_path_from_uri(tasks_artifact.uri).read_text(encoding="utf-8"))
    )


def _resolve_first_bitmap_artifact(request: StageRequest) -> ArtifactDescriptor:
    for artifact in request.artifacts.values():
        if artifact.kind == "bitmap":
            return artifact
    raise ValueError("Inpaint requires at least one bitmap artifact")


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
    source_image_bytes: bytes,
    source_mime_type: str,
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
            types.Part.from_bytes(data=source_image_bytes, mime_type=source_mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    response_texts: list[str] = []
    for part in _iter_response_parts(response):
        text = getattr(part, "text", None)
        if isinstance(text, str) and text.strip():
            response_texts.append(text.strip())
        if getattr(part, "inline_data", None):
            return _image_part_to_png_bytes(part)
    raise RuntimeError(_missing_image_error(response, response_texts))


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


def _image_part_to_png_bytes(part: object) -> bytes:
    inline_data = getattr(part, "inline_data", None)
    raw_bytes = getattr(inline_data, "data", None)
    if isinstance(raw_bytes, (bytes, bytearray)) and raw_bytes:
        return bytes(raw_bytes)

    as_image = getattr(part, "as_image", None)
    if callable(as_image):
        image_object = as_image()
        if hasattr(image_object, "convert"):
            return _image_to_bytes(image_object.convert("RGBA"), format_hint="PNG")
        pil_image = getattr(image_object, "_pil_image", None)
        if pil_image is not None and hasattr(pil_image, "convert"):
            return _image_to_bytes(pil_image.convert("RGBA"), format_hint="PNG")

    raise RuntimeError("Nanobanana image part could not be converted into PNG bytes")


def _generate_with_mindlogic_google_edit(
    source_image_bytes: bytes,
    source_mime_type: str,
    prompt: str,
    model_name: str,
    api_key: str,
) -> bytes:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "reference_images": [
            {
                "reference_id": 1,
                "reference_type": "REFERENCE_TYPE_RAW",
                "reference_image": {
                    "image_bytes": base64.b64encode(source_image_bytes).decode("ascii"),
                    "mime_type": source_mime_type,
                },
            }
        ],
        "config": {
            "edit_mode": MINDLOGIC_IMAGE_EDIT_MODE,
            "number_of_images": 1,
            "output_mime_type": "image/png",
        },
    }
    endpoint = MINDLOGIC_IMAGE_EDIT_BASE_URL.rstrip("/") + MINDLOGIC_IMAGE_EDIT_PATH
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(endpoint, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "curl/8.7.1")
    try:
        with request.urlopen(req, timeout=180.0) as resp:
            response_payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Mindlogic image edit failed: HTTP {exc.code}: {raw}") from exc

    image_bytes = _extract_mindlogic_image_bytes(response_payload)
    if image_bytes is None:
        keys = sorted(response_payload.keys()) if isinstance(response_payload, dict) else []
        raise RuntimeError(f"Mindlogic image edit response did not include an image: keys={keys}")
    return image_bytes


def _extract_mindlogic_image_bytes(payload: Any) -> Optional[bytes]:
    if isinstance(payload, str):
        return _decode_mindlogic_image_value(payload)
    if isinstance(payload, list):
        for item in payload:
            image_bytes = _extract_mindlogic_image_bytes(item)
            if image_bytes is not None:
                return image_bytes
        return None
    if not isinstance(payload, dict):
        return None

    for key in (
        "generated_images",
        "data",
        "images",
        "output",
        "image",
        "image_bytes",
        "url",
        "b64_json",
        "base64",
        "image_url",
    ):
        value = payload.get(key)
        image_bytes = _extract_mindlogic_image_bytes(value)
        if image_bytes is not None:
            return image_bytes
    return None


def _decode_mindlogic_image_value(value: str) -> Optional[bytes]:
    if value.startswith("data:image/"):
        _, encoded = value.split(",", 1)
        return base64.b64decode(encoded)
    if value.startswith("http://") or value.startswith("https://"):
        with request.urlopen(value, timeout=180.0) as resp:
            return resp.read()
    try:
        return base64.b64decode(value, validate=True)
    except Exception:
        return None


def _build_composite_mask(
    request: StageRequest,
    tasks_payload: object,
    image_size: tuple[int, int],
) -> Image.Image:
    composite_mask = Image.new("L", image_size, color=0)
    for task in getattr(tasks_payload, "tasks", []) or []:
        mask_artifact = request.artifacts[task.mask_artifact_ref]
        mask_path = _file_path_from_uri(mask_artifact.uri)
        region_mask = Image.open(mask_path).convert("L")
        position = (task.expanded_bbox["x"], task.expanded_bbox["y"])
        composite_mask.paste(region_mask, position, region_mask)
    return composite_mask


def _normalize_generated_page_size(
    generated_page: Image.Image,
    expected_size: tuple[int, int],
) -> tuple[Image.Image, Optional[str]]:
    if generated_page.size == expected_size:
        return generated_page, None

    resampling = getattr(Image, "Resampling", Image)
    resized = generated_page.resize(expected_size, resampling.LANCZOS)
    warning = (
        "provider_output_resized: "
        f"expected={expected_size} actual={generated_page.size}"
    )
    return resized, warning


def _missing_image_error(response: object, response_texts: list[str]) -> str:
    details: list[str] = ["Nanobanana Vertex AI response did not include an image"]
    finish_reasons: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is not None:
            finish_reasons.append(str(finish_reason))

    if finish_reasons:
        details.append(f"finish_reasons={','.join(finish_reasons)}")

    if response_texts:
        joined = " | ".join(response_texts[:3])
        details.append(f"text_response={joined}")

    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback is not None:
        details.append(f"prompt_feedback={prompt_feedback}")

    return ". ".join(details)


def _write_inpainted_bitmap(
    request: StageRequest,
    image: Image.Image,
    target_layer_id: str,
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    output_path = stage_dir / f"{run_slug}_inpainting.png"
    image.save(output_path)
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/"
        f"{run_slug}/inpainting_bitmap"
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


def _write_provider_output_bitmap(
    request: StageRequest,
    image: Image.Image,
    provider_name: str = "nanobanana",
) -> ArtifactDescriptor:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    output_path = stage_dir / f"{run_slug}_provider_output.png"
    image.save(output_path)
    artifact_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/"
        f"{run_slug}/provider_output_bitmap"
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
        metadata={"role": "provider_output_bitmap", "provider": provider_name},
    )


def _patches_for_inpainting_layer(
    request: StageRequest,
    artifact_ref: str,
    target_layer_id: str,
    engine_name: str,
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
                        "engine": engine_name,
                        "target_layer_id": target_layer_id,
                        "artifact_ref": artifact_ref,
                        "provider_output_role": "provider_output_bitmap",
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
                    "engine": engine_name,
                    "target_layer_id": target_layer_id,
                    "artifact_ref": artifact_ref,
                    "provider_output_role": "provider_output_bitmap",
                },
            },
        ),
    ]
def _failed_response(
    request: StageRequest,
    *,
    started_at: datetime,
    edited_image: Image.Image,
    tasks_payload: object,
    model_name: str,
    provider_name: str,
    error: Exception,
) -> StageResponse:
    snapshot_artifacts = _write_failure_snapshot(
        request,
        edited_image=edited_image,
        tasks_payload=tasks_payload,
        model_name=model_name,
        error=error,
    )
    report = StageReport(
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        input_refs=sorted(request.artifacts.keys()),
        output_refs=sorted(snapshot_artifacts.keys()),
        warnings=[],
        metrics={
            "provider": provider_name,
            "model_name": model_name,
            "task_count": len(getattr(tasks_payload, "tasks", []) or []),
            "snapshot_retained": "yes",
        },
        provider=request.credential_bindings.get("primary_provider"),
        error_code=_error_code_for_exception(error),
        error_message=str(error),
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
    )
    return StageResponse(
        schema_version=request.schema_version,
        stage_name=request.stage_name,
        stage_run_id=request.stage_run_id,
        status=StageStatus.FAILED,
        patches=[],
        artifacts=snapshot_artifacts,
        stage_report=report,
    )


def _write_failure_snapshot(
    request: StageRequest,
    *,
    edited_image: Image.Image,
    tasks_payload: object,
    model_name: str,
    error: Exception,
) -> dict[str, ArtifactDescriptor]:
    stage_dir = stage_transaction_dir(request)
    run_slug = stage_run_slug(request.stage_run_id)
    partial_bitmap_path = stage_dir / f"{run_slug}_partial_inpainting.png"
    edited_image.save(partial_bitmap_path)
    partial_bitmap_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/partial_inpainting_bitmap"
    )
    snapshot_path = stage_dir / f"{run_slug}_failure_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": request.schema_version,
                "stage_name": request.stage_name,
                "stage_run_id": request.stage_run_id,
                "model_name": model_name,
                "error_code": _error_code_for_exception(error),
                "error_message": str(error),
                "target_layer_id": getattr(tasks_payload, "target_layer_id", "layer_inpainting"),
                "task_count": len(getattr(tasks_payload, "tasks", []) or []),
                "partial_bitmap_ref": partial_bitmap_ref,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    snapshot_ref = (
        f"artifact://{request.pipeline_id}/{request.stage_name}/{run_slug}/failure_snapshot"
    )
    return {
        partial_bitmap_ref: ArtifactDescriptor(
            artifact_ref=partial_bitmap_ref,
            kind="bitmap",
            media_type="image/png",
            uri=partial_bitmap_path.resolve().as_uri(),
            width=edited_image.width,
            height=edited_image.height,
            byte_size=partial_bitmap_path.stat().st_size,
            producer_stage=request.stage_name,
            status=ArtifactStatus.FAILED,
            metadata={"role": "partial_inpainting_snapshot"},
        ),
        snapshot_ref: ArtifactDescriptor(
            artifact_ref=snapshot_ref,
            kind="stage_snapshot",
            media_type="application/json",
            uri=snapshot_path.resolve().as_uri(),
            byte_size=snapshot_path.stat().st_size,
            producer_stage=request.stage_name,
            metadata={"role": "failure_snapshot"},
        ),
    }


def _error_code_for_exception(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "provider_timeout"
    return "provider_error"


def _initial_inpainting_canvas(
    request: StageRequest,
    base_image: Image.Image,
    target_layer_id: str,
) -> Image.Image:
    existing_layer = request.document.get_layer(target_layer_id)
    if existing_layer and existing_layer.source_ref:
        descriptor = request.artifacts.get(existing_layer.source_ref)
        if descriptor is not None:
            return Image.open(_file_path_from_uri(descriptor.uri)).convert("RGBA")
    return Image.new("RGBA", base_image.size, color=(0, 0, 0, 0))
