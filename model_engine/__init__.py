"""Core contracts and orchestration primitives for the model engine."""

from .adapters import CallableModelAdapter, HttpApiModelAdapter, ModelAdapter
from .builtin_models import (
    CRAFT_TEXT_DETECTION_MODEL_ID,
    NANOBANANA_DEFAULT_PROMPT,
    NANOBANANA_IMAGE_MODEL,
    NANOBANANA_INPAINT_MODEL_ID,
    build_craft_text_detection_adapter,
    build_craft_text_detection_manifest,
    build_nanobanana_inpaint_adapter,
    build_nanobanana_inpaint_manifest,
    craft_text_detection_handler,
    nanobanana_inpaint_handler,
    register_craft_text_detection_model,
    register_nanobanana_inpaint_model,
)
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
from .contracts.text_regions import TextRegion, TextRegionsPayload
from .credentials import CredentialResolutionError, CredentialResolver, DefaultCredentialResolver
from .custom_models import CustomModelLoader, load_custom_models_into_registry
from .ipc.process_stage import ProcessStage
from .models.registry import ModelRegistry, ModelSelection, ModelSelectionError
from .orchestrator import PipelineOrchestrator, PipelineRunResult
from .stages.adapter_stage import AdapterBackedStage
from .stages.base import Stage, StaticStage
from .stages.mask_or_erase_planning import run_mask_or_erase_planning

__all__ = [
    "CallableModelAdapter",
    "CRAFT_TEXT_DETECTION_MODEL_ID",
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
    "AdapterBackedStage",
    "build_craft_text_detection_adapter",
    "build_craft_text_detection_manifest",
    "build_nanobanana_inpaint_adapter",
    "build_nanobanana_inpaint_manifest",
    "craft_text_detection_handler",
    "nanobanana_inpaint_handler",
    "register_craft_text_detection_model",
    "register_nanobanana_inpaint_model",
    "run_mask_or_erase_planning",
    "Stage",
    "StaticStage",
    "load_custom_models_into_registry",
]
