"""Core contracts and orchestration primitives for the model engine."""

from importlib import import_module

from .adapters import CallableModelAdapter, HttpApiModelAdapter, ModelAdapter
from .contracts.artifacts import ArtifactDescriptor, ArtifactRegistry, ArtifactStatus, InMemoryArtifactRegistry
from .contracts.credentials import BillingMode, CredentialBinding, CredentialSource, ResolvedCredential
from .contracts.document_ir import DocumentIR, LayerIR, TextBlock, TextStyle, Transform
from .contracts.models import ResourceProfile, StageKind, StageManifest
from .contracts.patches import PatchOp, PatchOperation, apply_patches
from .contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageStatus,
    StageRuntimeContext,
)
from .contracts.inpaint_tasks import InpaintTask, InpaintTasksPayload
from .contracts.ocr_text_blocks import OcrTextBlocksPayload, ocr_text_blocks_payload_from_mapping
from .contracts.text_regions import TextRegion, TextRegionsPayload
from .credentials import CredentialResolutionError, CredentialResolver, DefaultCredentialResolver
from .custom_models import CustomModelLoader, load_custom_models_into_registry
from .ipc.process_stage import ProcessStage
from .models.registry import ModelRegistry, ModelSelection, ModelSelectionError
from .orchestrator import PipelineOrchestrator, PipelineRunResult, ServiceBackedPipelineRunner
from .service_engine import (
    CurrentUserPayload,
    ServiceEngineAuthError,
    ServiceEngineClient,
    ServiceEngineConflictError,
    ServiceEngineCreditError,
    ServiceEngineError,
    ServiceEngineNotFoundError,
    ServiceEngineTransportError,
    UsageJobCreatePayload,
    UsageJobPayload,
)
from .stages.adapter_stage import AdapterBackedStage
from .stages.base import Stage, StaticStage

_OPTIONAL_BUILTIN_EXPORTS = {
    "CRAFT_TEXT_DETECTION_MODEL_ID": "CRAFT_TEXT_DETECTION_MODEL_ID",
    "MANGA_OCR_MODEL_ID": "MANGA_OCR_MODEL_ID",
    "NANOBANANA_DEFAULT_PROMPT": "NANOBANANA_DEFAULT_PROMPT",
    "NANOBANANA_IMAGE_MODEL": "NANOBANANA_IMAGE_MODEL",
    "NANOBANANA_INPAINT_MODEL_ID": "NANOBANANA_INPAINT_MODEL_ID",
    "build_craft_text_detection_adapter": "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest": "build_craft_text_detection_manifest",
    "build_manga_ocr_adapter": "build_manga_ocr_adapter",
    "build_manga_ocr_manifest": "build_manga_ocr_manifest",
    "build_nanobanana_inpaint_adapter": "build_nanobanana_inpaint_adapter",
    "build_nanobanana_inpaint_manifest": "build_nanobanana_inpaint_manifest",
    "craft_text_detection_handler": "craft_text_detection_handler",
    "manga_ocr_handler": "manga_ocr_handler",
    "nanobanana_inpaint_handler": "nanobanana_inpaint_handler",
    "register_craft_text_detection_model": "register_craft_text_detection_model",
    "register_manga_ocr_model": "register_manga_ocr_model",
    "register_nanobanana_inpaint_model": "register_nanobanana_inpaint_model",
}
_OPTIONAL_STAGE_EXPORTS = {
    "run_mask_or_erase_planning": "run_mask_or_erase_planning",
}


def __getattr__(name: str):
    if name in _OPTIONAL_BUILTIN_EXPORTS:
        module = import_module("model_engine.builtin_models")
        value = getattr(module, _OPTIONAL_BUILTIN_EXPORTS[name])
    elif name in _OPTIONAL_STAGE_EXPORTS:
        module = import_module("model_engine.stages.mask_or_erase_planning")
        value = getattr(module, _OPTIONAL_STAGE_EXPORTS[name])
    else:
        raise AttributeError(f"module 'model_engine' has no attribute {name!r}")

    globals()[name] = value
    return value

__all__ = [
    "CallableModelAdapter",
    "CRAFT_TEXT_DETECTION_MODEL_ID",
    "MANGA_OCR_MODEL_ID",
    "NANOBANANA_DEFAULT_PROMPT",
    "NANOBANANA_IMAGE_MODEL",
    "NANOBANANA_INPAINT_MODEL_ID",
    "CustomModelLoader",
    "HttpApiModelAdapter",
    "ModelAdapter",
    "ArtifactDescriptor",
    "ArtifactRegistry",
    "ArtifactStatus",
    "InMemoryArtifactRegistry",
    "BillingMode",
    "CredentialBinding",
    "CredentialSource",
    "ResolvedCredential",
    "ResourceProfile",
    "DocumentIR",
    "InpaintTask",
    "InpaintTasksPayload",
    "OcrTextBlocksPayload",
    "LayerIR",
    "StageKind",
    "StageManifest",
    "TextBlock",
    "TextRegion",
    "TextRegionsPayload",
    "TextStyle",
    "Transform",
    "PatchOp",
    "PatchOperation",
    "apply_patches",
    "ExecutionMode",
    "StageReport",
    "StageRequest",
    "StageResponse",
    "StageStatus",
    "StageRuntimeContext",
    "CredentialResolutionError",
    "CredentialResolver",
    "DefaultCredentialResolver",
    "ProcessStage",
    "ModelRegistry",
    "ModelSelection",
    "ModelSelectionError",
    "PipelineOrchestrator",
    "PipelineRunResult",
    "ServiceBackedPipelineRunner",
    "CurrentUserPayload",
    "ServiceEngineAuthError",
    "ServiceEngineClient",
    "ServiceEngineConflictError",
    "ServiceEngineCreditError",
    "ServiceEngineError",
    "ServiceEngineNotFoundError",
    "ServiceEngineTransportError",
    "UsageJobCreatePayload",
    "UsageJobPayload",
    "AdapterBackedStage",
    "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest",
    "build_manga_ocr_adapter",
    "build_manga_ocr_manifest",
    "build_nanobanana_inpaint_adapter",
    "build_nanobanana_inpaint_manifest",
    "craft_text_detection_handler",
    "manga_ocr_handler",
    "nanobanana_inpaint_handler",
    "register_craft_text_detection_model",
    "register_manga_ocr_model",
    "register_nanobanana_inpaint_model",
    "run_mask_or_erase_planning",
    "Stage",
    "StaticStage",
    "load_custom_models_into_registry",
    "ocr_text_blocks_payload_from_mapping",
]
