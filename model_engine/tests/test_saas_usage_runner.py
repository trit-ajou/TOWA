from __future__ import annotations

import unittest

from model_engine.contracts.document_ir import DocumentIR
from model_engine.contracts.stages import ExecutionMode, StageRuntimeContext, StageStatus
from model_engine.credentials import DefaultCredentialResolver
from model_engine.orchestrator import PipelineOrchestrator, ServiceBackedPipelineRunner
from model_engine.service_engine.models import UsageJobCreatePayload, UsageJobPayload
from model_engine.stages.base import StaticStage


class ServiceBackedPipelineRunnerTests(unittest.TestCase):
    def test_successful_saas_run_authorizes_and_captures_usage(self) -> None:
        service_client = _FakeServiceEngineClient()
        runner = ServiceBackedPipelineRunner(
            service_client_factory=lambda _base_url: service_client,
        )

        result = runner.run(
            document=DocumentIR(id="page-1", name="page-1", width=100, height=100),
            stages=[StaticStage("text_detection")],
            runtime_context=_saas_runtime_context(),
        )

        self.assertEqual(StageStatus.SUCCEEDED, result.status)
        self.assertEqual(
            [
                ("create", "mask", "page-1"),
                ("capture", "svc_job_1", None),
            ],
            service_client.calls,
        )
        self.assertEqual("svc_job_1", result.service_job_id)
        self.assertEqual("succeeded", result.service_status)
        self.assertEqual("captured", result.service_hold_status)

    def test_failed_saas_run_releases_usage_with_stage_reason(self) -> None:
        service_client = _FakeServiceEngineClient()
        runner = ServiceBackedPipelineRunner(
            orchestrator=PipelineOrchestrator(
                credential_resolver=DefaultCredentialResolver(
                    environ={"TOWA_PLATFORM_PROVIDER_NANOBANANA_API_KEY": "platform-secret"},
                )
            ),
            service_client_factory=lambda _base_url: service_client,
        )

        result = runner.run(
            document=DocumentIR(id="page-2", name="page-2", width=100, height=100),
            stages=[
                StaticStage("text_detection"),
                StaticStage(
                    "inpaint",
                    status=StageStatus.FAILED,
                    error_code="provider_timeout",
                    error_message="nanobanana timeout",
                ),
            ],
            runtime_context=_saas_runtime_context(request_ref="page-2"),
        )

        self.assertEqual(StageStatus.FAILED, result.status)
        self.assertEqual(
            [
                ("create", "inpaint", "page-2"),
                ("release", "svc_job_1", "provider_timeout"),
            ],
            service_client.calls,
        )
        self.assertEqual("failed", result.service_status)
        self.assertEqual("released", result.service_hold_status)

    def test_local_mode_bypasses_service_engine(self) -> None:
        service_client = _FakeServiceEngineClient()
        runner = ServiceBackedPipelineRunner(
            service_client_factory=lambda _base_url: service_client,
        )

        result = runner.run(
            document=DocumentIR(id="page-3", name="page-3", width=100, height=100),
            stages=[StaticStage("text_detection")],
            runtime_context=StageRuntimeContext(
                mode=ExecutionMode.LOCAL,
                workspace_uri="file:///tmp/towa/local-run",
            ),
        )

        self.assertEqual(StageStatus.SUCCEEDED, result.status)
        self.assertEqual([], service_client.calls)
        self.assertIsNone(result.service_job_id)


def _saas_runtime_context(*, request_ref: str = "page-1") -> StageRuntimeContext:
    return StageRuntimeContext(
        mode=ExecutionMode.SAAS,
        workspace_uri="file:///tmp/towa/saas-run",
        service_session_key="demo-session",
        service_base_url="http://service-engine:8000",
        service_request_ref=request_ref,
    )


class _FakeServiceEngineClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def create_usage_job(
        self,
        session_key: str,
        *,
        idempotency_key: str,
        operation_kind: str,
        request_ref: str,
        estimated_units: int,
    ) -> UsageJobCreatePayload:
        self.calls.append(("create", operation_kind, request_ref))
        self._last_idempotency_key = idempotency_key
        self._last_estimated_units = estimated_units
        return UsageJobCreatePayload(
            job_id="svc_job_1",
            status="authorized",
            reserved_units=estimated_units,
            hold_expires_at=_dt("2026-04-01T00:10:00Z"),
        )

    def capture_usage_job(self, session_key: str, *, job_id: str) -> UsageJobPayload:
        self.calls.append(("capture", job_id, None))
        return UsageJobPayload(
            id=job_id,
            operation_kind="mask",
            request_ref="page-1",
            estimated_units=5,
            status="succeeded",
            reserved_units=5,
            hold_status="captured",
            hold_expires_at=_dt("2026-04-01T00:10:00Z"),
            requested_at=_dt("2026-04-01T00:00:00Z"),
            finished_at=_dt("2026-04-01T00:00:02Z"),
        )

    def release_usage_job(
        self,
        session_key: str,
        *,
        job_id: str,
        error_code: str | None = None,
        reason: str | None = None,
    ) -> UsageJobPayload:
        self.calls.append(("release", job_id, error_code))
        return UsageJobPayload(
            id=job_id,
            operation_kind="inpaint",
            request_ref="page-2",
            estimated_units=20,
            status="failed",
            reserved_units=20,
            hold_status="released",
            hold_expires_at=_dt("2026-04-01T00:10:00Z"),
            error_code=error_code,
            error_detail=reason,
            requested_at=_dt("2026-04-01T00:00:00Z"),
            finished_at=_dt("2026-04-01T00:00:03Z"),
        )


def _dt(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    unittest.main()
