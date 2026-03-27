from __future__ import annotations

from datetime import datetime, timezone
import unittest
from typing import Optional

from model_engine.adapters.base import ModelAdapter
from model_engine.contracts.artifacts import ArtifactDescriptor
from model_engine.contracts.credentials import BillingMode, CredentialSource
from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.models import ResourceProfile, StageKind, StageManifest
from model_engine.contracts.patches import PatchOperation
from model_engine.contracts.stages import (
    ExecutionMode,
    StageReport,
    StageRequest,
    StageResponse,
    StageRuntimeContext,
    StageStatus,
)
from model_engine.models.registry import ModelRegistry
from model_engine.stages.adapter_stage import AdapterBackedStage


class FakeAdapter(ModelAdapter):
    def __init__(self, manifest: StageManifest, *, marker: str) -> None:
        self._manifest = manifest
        self._marker = marker

    @property
    def manifest(self) -> StageManifest:
        return self._manifest

    def run(self, request: StageRequest) -> StageResponse:
        started_at = datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)
        report = StageReport(
            stage_name=request.stage_name,
            stage_run_id=request.stage_run_id,
            status=StageStatus.SUCCEEDED,
            input_refs=sorted(request.artifacts.keys()),
            output_refs=[],
            warnings=[],
            metrics={"marker": self._marker},
            provider=request.credential_bindings.get("primary_provider"),
            started_at=started_at,
            finished_at=finished_at,
        )
        return StageResponse(
            schema_version=request.schema_version,
            stage_name=request.stage_name,
            stage_run_id=request.stage_run_id,
            status=StageStatus.SUCCEEDED,
            patches=[PatchOperation(op="set_stage_meta", payload={"key": "selected_model", "value": self._manifest.model_id})],
            artifacts={},
            stage_report=report,
        )


class ModelMergeTests(unittest.TestCase):
    def test_registry_selects_highest_priority_compatible_adapter(self) -> None:
        registry = ModelRegistry()
        registry.register(_text_detection_adapter("craft_builtin", priority=10))
        registry.register(_text_detection_adapter("custom_detector", priority=20, custom_model=True))

        stage = AdapterBackedStage(
            "text_detection",
            stage_kind=StageKind.TEXT_DETECTION,
            registry=registry,
        )
        request = _stage_request("text_detection", credential_source=None)

        response = stage.run(request)

        self.assertEqual("custom_detector", response.stage_report.metrics["model_id"])
        self.assertEqual("highest_priority_compatible_manifest", response.stage_report.metrics["selection_reason"])

    def test_stage_honors_preferred_model_id_override(self) -> None:
        registry = ModelRegistry()
        registry.register(_text_detection_adapter("craft_builtin", priority=10))
        registry.register(_text_detection_adapter("custom_detector", priority=20, custom_model=True))

        stage = AdapterBackedStage(
            "text_detection",
            stage_kind=StageKind.TEXT_DETECTION,
            registry=registry,
            preferred_model_id="craft_builtin",
        )
        request = _stage_request("text_detection", credential_source=None)

        response = stage.run(request)

        self.assertEqual("craft_builtin", response.stage_report.metrics["model_id"])

    def test_inpaint_registry_requires_compatible_credential_source(self) -> None:
        registry = ModelRegistry()
        registry.register(
            FakeAdapter(
                StageManifest(
                    model_id="nanobanana_platform",
                    adapter_id="adapter.nanobanana.platform",
                    stage_kind=StageKind.INPAINT,
                    required_artifact_kinds=["bitmap"],
                    produced_artifact_kinds=["bitmap"],
                    supported_modes=[ExecutionMode.SAAS],
                    allowed_credential_sources=[CredentialSource.PLATFORM_MANAGED],
                    billing_modes=[BillingMode.PLATFORM_CREDIT],
                    resource_profile=ResourceProfile(latency_tier="network"),
                    priority=10,
                ),
                marker="platform",
            )
        )
        registry.register(
            FakeAdapter(
                StageManifest(
                    model_id="custom_local_inpaint",
                    adapter_id="adapter.custom.local",
                    stage_kind=StageKind.INPAINT,
                    required_artifact_kinds=["bitmap"],
                    produced_artifact_kinds=["bitmap"],
                    supported_modes=[ExecutionMode.LOCAL],
                    allowed_credential_sources=[CredentialSource.USER_PERSONAL_PERSISTED],
                    billing_modes=[BillingMode.USER_DIRECT],
                    resource_profile=ResourceProfile(gpu_required=True),
                    custom_model=True,
                    priority=50,
                ),
                marker="local",
            )
        )

        stage = AdapterBackedStage(
            "inpaint",
            stage_kind=StageKind.INPAINT,
            registry=registry,
        )
        request = _stage_request("inpaint", credential_source=CredentialSource.USER_PERSONAL_PERSISTED)

        response = stage.run(request)

        self.assertEqual("custom_local_inpaint", response.stage_report.metrics["model_id"])
        self.assertEqual("local", response.stage_report.metrics["marker"])


def _text_detection_adapter(model_id: str, *, priority: int, custom_model: bool = False) -> FakeAdapter:
    return FakeAdapter(
        StageManifest(
            model_id=model_id,
            adapter_id=f"adapter.{model_id}",
            stage_kind=StageKind.TEXT_DETECTION,
            required_artifact_kinds=["bitmap"],
            produced_artifact_kinds=["text_regions"],
            supported_modes=[ExecutionMode.LOCAL, ExecutionMode.SAAS],
            allowed_credential_sources=[CredentialSource.NONE],
            billing_modes=[BillingMode.NONE],
            custom_model=custom_model,
            priority=priority,
        ),
        marker=model_id,
    )


def _stage_request(stage_name: str, *, credential_source: Optional[CredentialSource]) -> StageRequest:
    runtime_context = StageRuntimeContext(
        mode=ExecutionMode.LOCAL if credential_source != CredentialSource.PLATFORM_MANAGED else ExecutionMode.SAAS,
        workspace_uri="file:///tmp/towa/model-merge",
    )
    credential_bindings = {}
    if credential_source is not None:
        from model_engine.contracts.credentials import CredentialBinding

        billing_mode = BillingMode.USER_DIRECT
        if credential_source is CredentialSource.PLATFORM_MANAGED:
            billing_mode = BillingMode.PLATFORM_CREDIT
        credential_bindings["primary_provider"] = CredentialBinding(
            provider="nanobanana",
            credential_source=credential_source,
            credential_id="test/provider/default",
            credential_version="2026-03-27",
            billing_mode=billing_mode,
        )

    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_model_merge",
        job_id="job_model_merge",
        stage_name=stage_name,
        stage_run_id=f"{stage_name}:run:1",
        document=DocumentIR(id="doc_model_merge", name="merge", width=100, height=100),
        artifacts={
            "artifact://page": ArtifactDescriptor(
                artifact_ref="artifact://page",
                kind="bitmap",
                media_type="image/png",
                uri="file:///tmp/towa/page.png",
            )
        },
        credential_bindings=credential_bindings,
        runtime_context=runtime_context,
    )


if __name__ == "__main__":
    unittest.main()
