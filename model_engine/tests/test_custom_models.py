from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
from model_engine.custom_models import CustomModelLoader
from model_engine.ipc.serde import stage_request_from_data
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage


class CustomModelLoaderTests(unittest.TestCase):
    def test_python_callable_manifest_loads_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "detector.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v1",
                        "adapter_type": "python_callable",
                        "model_id": "custom.demo.detector",
                        "adapter_id": "adapter.custom.demo.detector",
                        "stage_kind": "text_detection",
                        "required_artifact_kinds": ["bitmap"],
                        "produced_artifact_kinds": ["text_regions"],
                        "supported_modes": ["local", "saas"],
                        "allowed_credential_sources": ["none"],
                        "billing_modes": ["none"],
                        "custom_model": True,
                        "priority": 100,
                        "adapter_config": {
                            "import_path": "model_engine.custom_models.demo:demo_text_detection"
                        },
                    }
                )
            )

            registry = ModelRegistry()
            loaded = registry.load_custom_model_directory(tmpdir)
            stage = AdapterBackedStage(
                "text_detection",
                stage_kind=StageKind.TEXT_DETECTION,
                registry=registry,
            )

            response = stage.run(_stage_request("text_detection"))

            self.assertEqual(["custom.demo.detector"], loaded)
            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("custom.demo.detector", response.stage_report.metrics["model_id"])
            self.assertEqual(
                "python_callable",
                response.stage_report.metrics["transport"],
            )

    def test_http_api_manifest_loads_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            endpoint_url = "https://custom.example.test/run"
            manifest_path = Path(tmpdir) / "remote_inpaint.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v1",
                        "adapter_type": "http_api",
                        "model_id": "custom.remote.inpaint",
                        "adapter_id": "adapter.custom.remote.inpaint",
                        "stage_kind": "inpaint",
                        "required_artifact_kinds": ["bitmap"],
                        "produced_artifact_kinds": ["bitmap"],
                        "supported_modes": ["local"],
                        "allowed_credential_sources": ["user_personal_persisted"],
                        "billing_modes": ["user_direct"],
                        "custom_model": True,
                        "priority": 60,
                        "adapter_config": {
                            "endpoint_url": endpoint_url,
                            "timeout_seconds": 5,
                            "auth_header_name": "Authorization",
                            "auth_header_prefix": "Bearer",
                            "credential_alias": "primary_provider",
                            "headers": {"X-Towa-Model": "demo-remote"},
                        },
                    }
                )
            )

            registry = ModelRegistry()
            loader = CustomModelLoader()
            loader.load_into_registry(registry, tmpdir)
            stage = AdapterBackedStage(
                "inpaint",
                stage_kind=StageKind.INPAINT,
                registry=registry,
            )

            with patch(
                "model_engine.adapters.http_api.request.urlopen",
                side_effect=_fake_urlopen,
            ):
                response = stage.run(_stage_request("inpaint", with_credential=True))

            self.assertEqual(StageStatus.SUCCEEDED, response.status)
            self.assertEqual("custom.remote.inpaint", response.stage_report.metrics["model_id"])
            self.assertEqual("http_api", response.stage_report.metrics["transport"])
            self.assertEqual("yes", response.stage_report.metrics["auth_header_seen"])
            self.assertEqual("demo-remote", response.stage_report.metrics["header_model"])


def _stage_request(stage_name: str, *, with_credential: bool = False) -> StageRequest:
    runtime_context = StageRuntimeContext(
        mode=ExecutionMode.LOCAL,
        workspace_uri="file:///tmp/towa/custom-models",
    )
    credential_bindings = {}
    resolved_credentials = {}
    if with_credential:
        credential_bindings["primary_provider"] = CredentialBinding(
            provider="custom_provider",
            credential_source=CredentialSource.USER_PERSONAL_PERSISTED,
            credential_id="local/custom_provider/default",
            credential_version="2026-03-27",
            billing_mode=BillingMode.USER_DIRECT,
        )
        resolved_credentials["primary_provider"] = ResolvedCredential(
            binding=credential_bindings["primary_provider"],
            secrets={"api_key": "custom-secret"},
        )

    return StageRequest(
        schema_version="v1",
        pipeline_id="pipe_custom_models",
        job_id="job_custom_models",
        stage_name=stage_name,
        stage_run_id=f"{stage_name}:run:1",
        document=DocumentIR(id="doc_custom_models", name="custom-models", width=100, height=100),
        artifacts={
            "artifact://page": ArtifactDescriptor(
                artifact_ref="artifact://page",
                kind="bitmap",
                media_type="image/png",
                uri="file:///tmp/towa/page.png",
            )
        },
        credential_bindings=credential_bindings,
        resolved_credentials=resolved_credentials,
        runtime_context=runtime_context,
    )


def _fake_urlopen(http_request: object, timeout: float = 0.0) -> "_FakeHttpResponse":
    payload = json.loads(http_request.data.decode("utf-8"))
    stage_request = stage_request_from_data(payload)
    auth_header = http_request.headers.get("Authorization")
    custom_header = http_request.headers.get("X-towa-model")
    response = {
        "schema_version": stage_request.schema_version,
        "stage_name": stage_request.stage_name,
        "stage_run_id": stage_request.stage_run_id,
        "status": "succeeded",
        "patches": [
            {
                "op": "set_stage_meta",
                "target": {},
                "payload": {
                    "key": "custom_model_demo",
                    "value": "http_api",
                },
            }
        ],
        "artifacts": {},
        "stage_report": {
            "stage_name": stage_request.stage_name,
            "stage_run_id": stage_request.stage_run_id,
            "status": "succeeded",
            "input_refs": sorted(stage_request.artifacts.keys()),
            "output_refs": [],
            "warnings": [],
            "metrics": {
                "transport": "http_api",
                "auth_header_seen": "yes" if auth_header == "Bearer custom-secret" else "no",
                "header_model": custom_header or "",
            },
            "provider": {
                "provider": "custom_provider",
                "credential_source": "user_personal_persisted",
                "credential_id": "local/custom_provider/default",
                "credential_version": "2026-03-27",
                "billing_mode": "user_direct",
            },
            "error_code": None,
            "error_message": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    return _FakeHttpResponse(json.dumps(response).encode("utf-8"))


class _FakeHttpResponse:
    def __init__(self, body: bytes) -> None:
        self._stream = io.BytesIO(body)

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


if __name__ == "__main__":
    unittest.main()
