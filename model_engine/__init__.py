"""Core contracts and orchestration primitives for the model engine."""

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
from .credentials import CredentialResolutionError, CredentialResolver, DefaultCredentialResolver
from .custom_models import CustomModelLoader, load_custom_models_into_registry
from .ipc.process_stage import ProcessStage
from .models.registry import ModelRegistry, ModelSelection, ModelSelectionError
from .orchestrator import PipelineOrchestrator, PipelineRunResult
from .stages.adapter_stage import AdapterBackedStage
from .stages.base import Stage, StaticStage

__all__ = [
    "CallableModelAdapter",
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
    "LayerIR",
    "StageKind",
    "StageManifest",
    "TextBlock",
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
    "Stage",
    "StaticStage",
    "load_custom_models_into_registry",
]
