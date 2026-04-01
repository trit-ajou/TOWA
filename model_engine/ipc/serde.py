from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..contracts.artifacts import ArtifactDescriptor, ArtifactStatus
from ..contracts.credentials import BillingMode, CredentialBinding, CredentialSource
from ..contracts.document_ir import (
    DocumentIR,
    FilterSettings,
    LayerIR,
    Point,
    TextBlock,
    TextStyle,
    Transform,
)
from ..contracts.patches import PatchOperation
from ..contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageRuntimeContext,
    StageStatus,
)


def stage_request_to_data(request: StageRequest) -> dict[str, Any]:
    return {
        "schema_version": request.schema_version,
        "pipeline_id": request.pipeline_id,
        "job_id": request.job_id,
        "stage_name": request.stage_name,
        "stage_run_id": request.stage_run_id,
        "document": document_to_data(request.document),
        "artifacts": {
            artifact_ref: artifact_to_data(descriptor)
            for artifact_ref, descriptor in request.artifacts.items()
        },
        "patches_applied": [patch_to_data(patch) for patch in request.patches_applied],
        "stage_config": dict(request.stage_config),
        "credential_bindings": {
            alias: credential_binding_to_data(binding)
            for alias, binding in request.credential_bindings.items()
        },
        "runtime_context": runtime_context_to_data(request.runtime_context),
    }


def stage_request_from_data(payload: dict[str, Any]) -> StageRequest:
    return StageRequest(
        schema_version=str(payload["schema_version"]),
        pipeline_id=str(payload["pipeline_id"]),
        job_id=str(payload["job_id"]),
        stage_name=str(payload["stage_name"]),
        stage_run_id=str(payload["stage_run_id"]),
        document=document_from_data(payload["document"]),
        artifacts={
            artifact_ref: artifact_from_data(descriptor)
            for artifact_ref, descriptor in payload.get("artifacts", {}).items()
        },
        patches_applied=[patch_from_data(item) for item in payload.get("patches_applied", [])],
        stage_config=dict(payload.get("stage_config", {})),
        credential_bindings={
            alias: credential_binding_from_data(item)
            for alias, item in payload.get("credential_bindings", {}).items()
        },
        runtime_context=runtime_context_from_data(payload.get("runtime_context")),
    )


def stage_response_to_data(response: StageResponse) -> dict[str, Any]:
    return {
        "schema_version": response.schema_version,
        "stage_name": response.stage_name,
        "stage_run_id": response.stage_run_id,
        "status": response.status.value,
        "patches": [patch_to_data(patch) for patch in response.patches],
        "artifacts": {
            artifact_ref: artifact_to_data(descriptor)
            for artifact_ref, descriptor in response.artifacts.items()
        },
        "stage_report": stage_report_to_data(response.stage_report),
    }


def stage_response_from_data(payload: dict[str, Any]) -> StageResponse:
    return StageResponse(
        schema_version=str(payload["schema_version"]),
        stage_name=str(payload["stage_name"]),
        stage_run_id=str(payload["stage_run_id"]),
        status=StageStatus(payload["status"]),
        patches=[patch_from_data(item) for item in payload.get("patches", [])],
        artifacts={
            artifact_ref: artifact_from_data(descriptor)
            for artifact_ref, descriptor in payload.get("artifacts", {}).items()
        },
        stage_report=stage_report_from_data(payload["stage_report"]),
    )


def runtime_context_to_data(context: Optional[StageRuntimeContext]) -> Optional[dict[str, Any]]:
    if context is None:
        return None
    return {
        "mode": context.mode.value,
        "workspace_uri": context.workspace_uri,
        "requested_by": context.requested_by,
        "cancellation_token": context.cancellation_token,
        "target_regions": list(context.target_regions),
        "selected_layer_ids": list(context.selected_layer_ids),
        "session_provider_secrets": dict(context.session_provider_secrets),
        "service_session_key": context.service_session_key,
        "service_base_url": context.service_base_url,
        "service_request_ref": context.service_request_ref,
    }


def runtime_context_from_data(payload: Optional[dict[str, Any]]) -> Optional[StageRuntimeContext]:
    if payload is None:
        return None
    return StageRuntimeContext(
        mode=ExecutionMode(payload["mode"]),
        workspace_uri=str(payload["workspace_uri"]),
        requested_by=payload.get("requested_by"),
        cancellation_token=payload.get("cancellation_token"),
        target_regions=list(payload.get("target_regions", [])),
        selected_layer_ids=list(payload.get("selected_layer_ids", [])),
        session_provider_secrets=dict(payload.get("session_provider_secrets", {})),
        service_session_key=payload.get("service_session_key"),
        service_base_url=payload.get("service_base_url"),
        service_request_ref=payload.get("service_request_ref"),
    )


def stage_report_to_data(report: StageReport) -> dict[str, Any]:
    return {
        "stage_name": report.stage_name,
        "stage_run_id": report.stage_run_id,
        "status": report.status.value,
        "input_refs": list(report.input_refs),
        "output_refs": list(report.output_refs),
        "warnings": list(report.warnings),
        "metrics": dict(report.metrics),
        "provider": credential_binding_to_data(report.provider) if report.provider else None,
        "error_code": report.error_code,
        "error_message": report.error_message,
        "started_at": report.started_at.isoformat(),
        "finished_at": report.finished_at.isoformat(),
    }


def stage_report_from_data(payload: dict[str, Any]) -> StageReport:
    return StageReport(
        stage_name=str(payload["stage_name"]),
        stage_run_id=str(payload["stage_run_id"]),
        status=StageStatus(payload["status"]),
        input_refs=list(payload.get("input_refs", [])),
        output_refs=list(payload.get("output_refs", [])),
        warnings=list(payload.get("warnings", [])),
        metrics=dict(payload.get("metrics", {})),
        provider=credential_binding_from_data(payload["provider"]) if payload.get("provider") else None,
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        started_at=datetime.fromisoformat(payload["started_at"]),
        finished_at=datetime.fromisoformat(payload["finished_at"]),
    )


def credential_binding_to_data(binding: CredentialBinding) -> dict[str, Any]:
    return {
        "provider": binding.provider,
        "credential_source": binding.credential_source.value,
        "credential_id": binding.credential_id,
        "credential_version": binding.credential_version,
        "billing_mode": binding.billing_mode.value,
    }


def credential_binding_from_data(payload: dict[str, Any]) -> CredentialBinding:
    return CredentialBinding(
        provider=str(payload["provider"]),
        credential_source=CredentialSource(payload["credential_source"]),
        credential_id=str(payload["credential_id"]),
        credential_version=str(payload["credential_version"]),
        billing_mode=BillingMode(payload["billing_mode"]),
    )


def patch_to_data(patch: PatchOperation) -> dict[str, Any]:
    return {
        "op": patch.op.value,
        "target": dict(patch.target),
        "payload": dict(patch.payload),
    }


def patch_from_data(payload: dict[str, Any]) -> PatchOperation:
    return PatchOperation(
        op=str(payload["op"]),
        target=dict(payload.get("target", {})),
        payload=dict(payload.get("payload", {})),
    )


def artifact_to_data(descriptor: ArtifactDescriptor) -> dict[str, Any]:
    return {
        "artifact_ref": descriptor.artifact_ref,
        "kind": descriptor.kind,
        "media_type": descriptor.media_type,
        "uri": descriptor.uri,
        "width": descriptor.width,
        "height": descriptor.height,
        "byte_size": descriptor.byte_size,
        "checksum": descriptor.checksum,
        "version": descriptor.version,
        "producer_stage": descriptor.producer_stage,
        "status": descriptor.status.value,
        "created_at": descriptor.created_at.isoformat(),
        "expires_at": descriptor.expires_at.isoformat() if descriptor.expires_at else None,
        "metadata": dict(descriptor.metadata),
    }


def artifact_from_data(payload: dict[str, Any]) -> ArtifactDescriptor:
    return ArtifactDescriptor(
        artifact_ref=str(payload["artifact_ref"]),
        kind=str(payload["kind"]),
        media_type=str(payload["media_type"]),
        uri=str(payload["uri"]),
        width=payload.get("width"),
        height=payload.get("height"),
        byte_size=payload.get("byte_size"),
        checksum=payload.get("checksum"),
        version=int(payload.get("version", 1)),
        producer_stage=payload.get("producer_stage"),
        status=ArtifactStatus(payload.get("status", ArtifactStatus.READY.value)),
        created_at=datetime.fromisoformat(payload["created_at"]),
        expires_at=datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
        metadata=dict(payload.get("metadata", {})),
    )


def document_to_data(document: DocumentIR) -> dict[str, Any]:
    return {
        "id": document.id,
        "name": document.name,
        "width": document.width,
        "height": document.height,
        "layers": [layer_to_data(layer) for layer in document.layers],
        "selections": selections_to_data(document.selections),
        "active_selection": selection_to_data(document.active_selection),
        "invert_selection": document.invert_selection,
        "text_blocks": [text_block_to_data(block) for block in document.text_blocks],
        "stage_meta": dict(document.stage_meta),
    }


def document_from_data(payload: dict[str, Any]) -> DocumentIR:
    return DocumentIR(
        id=str(payload["id"]),
        name=str(payload["name"]),
        width=int(payload["width"]),
        height=int(payload["height"]),
        layers=[layer_from_data(item) for item in payload.get("layers", [])],
        selections=selections_from_data(payload.get("selections", {})),
        active_selection=selection_from_data(payload.get("active_selection", [])),
        invert_selection=bool(payload.get("invert_selection", False)),
        text_blocks=[text_block_from_data(item) for item in payload.get("text_blocks", [])],
        stage_meta=dict(payload.get("stage_meta", {})),
    )


def layer_to_data(layer: LayerIR) -> dict[str, Any]:
    return {
        "id": layer.id,
        "name": layer.name,
        "type": layer.type,
        "left": layer.left,
        "top": layer.top,
        "width": layer.width,
        "height": layer.height,
        "visible": layer.visible,
        "transparent": layer.transparent,
        "source_ref": layer.source_ref,
        "mask_ref": layer.mask_ref,
        "transform": transform_to_data(layer.transform),
        "filters": filters_to_data(layer.filters),
        "text": text_style_to_data(layer.text),
        "props": dict(layer.props),
    }


def layer_from_data(payload: dict[str, Any]) -> LayerIR:
    return LayerIR(
        id=str(payload["id"]),
        name=str(payload["name"]),
        type=str(payload["type"]),
        left=float(payload.get("left", 0)),
        top=float(payload.get("top", 0)),
        width=float(payload["width"]),
        height=float(payload["height"]),
        visible=bool(payload.get("visible", True)),
        transparent=bool(payload.get("transparent", True)),
        source_ref=payload.get("source_ref"),
        mask_ref=payload.get("mask_ref"),
        transform=transform_from_data(payload.get("transform", {})),
        filters=filters_from_data(payload.get("filters", {})),
        text=text_style_from_data(payload.get("text", {})),
        props=dict(payload.get("props", {})),
    )


def transform_to_data(transform: Transform) -> dict[str, Any]:
    return {
        "scale": transform.scale,
        "rotation": transform.rotation,
        "mirror_x": transform.mirror_x,
        "mirror_y": transform.mirror_y,
    }


def transform_from_data(payload: dict[str, Any]) -> Transform:
    return Transform(
        scale=float(payload.get("scale", 1.0)),
        rotation=float(payload.get("rotation", 0.0)),
        mirror_x=bool(payload.get("mirror_x", False)),
        mirror_y=bool(payload.get("mirror_y", False)),
    )


def filters_to_data(filters: FilterSettings) -> dict[str, Any]:
    return {
        "enabled": filters.enabled,
        "blend_mode": filters.blend_mode,
        "opacity": filters.opacity,
        "gamma": filters.gamma,
        "brightness": filters.brightness,
        "contrast": filters.contrast,
        "vibrance": filters.vibrance,
        "threshold": filters.threshold,
        "desaturate": filters.desaturate,
        "invert": filters.invert,
        "duotone_enabled": filters.duotone_enabled,
        "duotone_color_1": filters.duotone_color_1,
        "duotone_color_2": filters.duotone_color_2,
    }


def filters_from_data(payload: dict[str, Any]) -> FilterSettings:
    return FilterSettings(
        enabled=bool(payload.get("enabled", False)),
        blend_mode=str(payload.get("blend_mode", "normal")),
        opacity=float(payload.get("opacity", 1.0)),
        gamma=float(payload.get("gamma", 1.0)),
        brightness=float(payload.get("brightness", 0.0)),
        contrast=float(payload.get("contrast", 0.0)),
        vibrance=float(payload.get("vibrance", 0.0)),
        threshold=float(payload.get("threshold", 0.0)),
        desaturate=bool(payload.get("desaturate", False)),
        invert=bool(payload.get("invert", False)),
        duotone_enabled=bool(payload.get("duotone_enabled", False)),
        duotone_color_1=payload.get("duotone_color_1"),
        duotone_color_2=payload.get("duotone_color_2"),
    )


def text_style_to_data(text: TextStyle) -> dict[str, Any]:
    return {
        "value": text.value,
        "font": text.font,
        "size": text.size,
        "unit": text.unit,
        "line_height": text.line_height,
        "spacing": text.spacing,
        "color": text.color,
    }


def text_style_from_data(payload: dict[str, Any]) -> TextStyle:
    return TextStyle(
        value=str(payload.get("value", "")),
        font=str(payload.get("font", "")),
        size=float(payload.get("size", 0.0)),
        unit=str(payload.get("unit", "px")),
        line_height=float(payload.get("line_height", 1.0)),
        spacing=float(payload.get("spacing", 0.0)),
        color=str(payload.get("color", "#000000")),
    )


def text_block_to_data(block: TextBlock) -> dict[str, Any]:
    return {
        "block_id": block.block_id,
        "source_lang_text": block.source_lang_text,
        "translated_text": block.translated_text,
        "polygon": points_to_data(block.polygon),
        "bbox": dict(block.bbox),
        "reading_order": block.reading_order,
        "speaker": block.speaker,
        "style_hint": dict(block.style_hint),
        "font_hint": dict(block.font_hint),
        "writing_mode": block.writing_mode,
        "source_region_ref": block.source_region_ref,
    }


def text_block_from_data(payload: dict[str, Any]) -> TextBlock:
    return TextBlock(
        block_id=str(payload["block_id"]),
        source_lang_text=str(payload.get("source_lang_text", "")),
        translated_text=str(payload.get("translated_text", "")),
        polygon=points_from_data(payload.get("polygon", [])),
        bbox=dict(payload.get("bbox", {})),
        reading_order=payload.get("reading_order"),
        speaker=payload.get("speaker"),
        style_hint=dict(payload.get("style_hint", {})),
        font_hint=dict(payload.get("font_hint", {})),
        writing_mode=str(payload.get("writing_mode", "horizontal")),
        source_region_ref=payload.get("source_region_ref"),
    )


def selections_to_data(selections: dict[str, Any]) -> dict[str, Any]:
    return {
        name: selection_to_data(selection)
        for name, selection in selections.items()
    }


def selections_from_data(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        name: selection_from_data(selection)
        for name, selection in payload.items()
    }


def selection_to_data(selection: list[list[Point]]) -> list[list[dict[str, float]]]:
    return [points_to_data(shape) for shape in selection]


def selection_from_data(payload: list[list[dict[str, Any]]]) -> list[list[Point]]:
    return [points_from_data(shape) for shape in payload]


def points_to_data(points: list[Point]) -> list[dict[str, float]]:
    return [{"x": point.x, "y": point.y} for point in points]


def points_from_data(payload: list[dict[str, Any]]) -> list[Point]:
    return [Point(x=float(item["x"]), y=float(item["y"])) for item in payload]
