from __future__ import annotations

import time
import unittest

from fastapi.testclient import TestClient

from model_engine.api.app import create_app
from model_engine.api.jobs import (
    JobExecutionRequest,
    JobExecutionResult,
    JobExecutor,
    ModelJobManager,
    ModelJobStatus,
    PlaceholderJobExecutor,
)
from model_engine.api.service_bridge import ServiceEngineHTTPError


class ModelJobAPITests(unittest.TestCase):
    def test_local_job_lifecycle_returns_placeholder_stage_reports(self) -> None:
        app = create_app(
            job_manager=ModelJobManager(
                executor=PlaceholderJobExecutor(sleep_seconds=0.0),
            )
        )
        client = TestClient(app)

        response = client.post("/v1/jobs", json=_job_payload(operation_kind="detect", mode="local"))

        self.assertEqual(202, response.status_code)
        body = response.json()
        self.assertEqual("queued", body["status"])

        detail = _wait_for_terminal_job(client, body["job_id"])

        self.assertEqual("succeeded", detail["status"])
        self.assertEqual(["text_detection"], [report["stage_name"] for report in detail["stage_reports"]])
        self.assertEqual(
            "placeholder",
            detail["document"]["stage_meta"]["text_detection"]["executor"],
        )

    def test_saas_job_create_and_capture_are_forwarded_to_service_engine(self) -> None:
        fake_service = _FakeServiceClient()
        app = create_app(
            job_manager=ModelJobManager(
                executor=PlaceholderJobExecutor(sleep_seconds=0.0),
                service_client_factory=lambda: fake_service,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/v1/jobs",
            json=_job_payload(operation_kind="translate", mode="saas"),
            headers={"Authorization": "Bearer demo-session"},
        )

        self.assertEqual(202, response.status_code)
        detail = _wait_for_terminal_job(client, response.json()["job_id"])

        self.assertEqual("succeeded", detail["status"])
        self.assertEqual(
            ["/usage/jobs", "/usage/jobs/svc_job_1/capture"],
            [call["path"] for call in fake_service.calls],
        )
        self.assertEqual("Bearer demo-session", fake_service.calls[0]["authorization"])
        self.assertEqual("translate", fake_service.calls[0]["body"]["operation_kind"])
        self.assertEqual(20, fake_service.calls[0]["body"]["estimated_units"])

    def test_detect_jobs_are_mapped_to_mask_usage_for_service_engine(self) -> None:
        fake_service = _FakeServiceClient()
        app = create_app(
            job_manager=ModelJobManager(
                executor=PlaceholderJobExecutor(sleep_seconds=0.0),
                service_client_factory=lambda: fake_service,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/v1/jobs",
            json=_job_payload(operation_kind="detect", mode="saas"),
            headers={"Authorization": "Bearer demo-session"},
        )

        self.assertEqual(202, response.status_code)
        _wait_for_terminal_job(client, response.json()["job_id"])
        self.assertEqual("mask", fake_service.calls[0]["body"]["operation_kind"])
        self.assertEqual(5, fake_service.calls[0]["body"]["estimated_units"])

    def test_saas_failure_releases_usage_hold(self) -> None:
        fake_service = _FakeServiceClient()
        app = create_app(
            job_manager=ModelJobManager(
                executor=_FailingExecutor(),
                service_client_factory=lambda: fake_service,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/v1/jobs",
            json=_job_payload(operation_kind="inpaint", mode="saas"),
            headers={"Authorization": "Bearer demo-session"},
        )

        self.assertEqual(202, response.status_code)
        detail = _wait_for_terminal_job(client, response.json()["job_id"])

        self.assertEqual("failed", detail["status"])
        self.assertEqual(
            ["/usage/jobs", "/usage/jobs/svc_job_1/release"],
            [call["path"] for call in fake_service.calls],
        )
        self.assertEqual("model_stage_failed", fake_service.calls[1]["body"]["error_code"])
        self.assertEqual("placeholder executor failed", detail["error"]["message"])

    def test_service_usage_error_is_passed_through_on_create(self) -> None:
        payload = {
            "error": {
                "code": "insufficient_credits",
                "message": "not enough balance",
                "retryable": False,
                "details": None,
            }
        }
        fake_service = _FakeServiceClient(create_error=ServiceEngineHTTPError(409, payload))
        app = create_app(
            job_manager=ModelJobManager(
                executor=PlaceholderJobExecutor(sleep_seconds=0.0),
                service_client_factory=lambda: fake_service,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/v1/jobs",
            json=_job_payload(operation_kind="detect", mode="saas"),
            headers={"Authorization": "Bearer demo-session"},
        )

        self.assertEqual(409, response.status_code)
        self.assertEqual(payload, response.json())

    def test_jobs_endpoint_supports_cors_preflight(self) -> None:
        app = create_app(
            job_manager=ModelJobManager(
                executor=PlaceholderJobExecutor(sleep_seconds=0.0),
            )
        )
        client = TestClient(app)

        response = client.options(
            "/v1/jobs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("http://localhost:5173", response.headers["access-control-allow-origin"])


class _FailingExecutor(JobExecutor):
    def execute(self, request: JobExecutionRequest) -> JobExecutionResult:
        _ = request
        raise RuntimeError("placeholder executor failed")


class _FakeServiceClient:
    def __init__(self, *, create_error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._create_error = create_error

    def post(
        self,
        path: str,
        *,
        body: dict[str, object] | None = None,
        authorization: str | None = None,
    ) -> dict[str, object]:
        payload = dict(body or {})
        self.calls.append(
            {
                "path": path,
                "body": payload,
                "authorization": authorization,
            }
        )
        if path == "/usage/jobs":
            if self._create_error is not None:
                raise self._create_error
            return {
                "job_id": "svc_job_1",
                "status": "authorized",
                "reserved_units": payload.get("estimated_units", 0),
                "hold_expires_at": "2026-03-25T01:00:00Z",
            }
        return {"status": "ok"}


def _wait_for_terminal_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.time() + 2.0
    while time.time() < deadline:
        response = client.get(f"/v1/jobs/{job_id}")
        if response.status_code != 200:
            raise AssertionError(f"Unexpected status while polling job {job_id}: {response.status_code}")
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "partial"}:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for job {job_id} to finish")


def _job_payload(*, operation_kind: str, mode: str) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "idempotency_key": f"project:proj-1:page:001:op:{operation_kind}:v:1",
        "operation_kind": operation_kind,
        "request_ref": "project/proj-1/page/001",
        "document": {
            "id": "doc_page_001",
            "name": "page-001",
            "width": 800,
            "height": 1200,
            "layers": [
                {
                    "id": "layer_original",
                    "name": "Original",
                    "type": "graphic",
                    "left": 0,
                    "top": 0,
                    "width": 800,
                    "height": 1200,
                    "source_ref": "artifact://page-original",
                }
            ],
            "text_blocks": [],
            "stage_meta": {},
        },
        "artifacts": {
            "artifact://page-original": {
                "artifact_ref": "artifact://page-original",
                "kind": "bitmap",
                "media_type": "image/png",
                "uri": "https://storage.example.test/page-001.png",
            }
        },
        "runtime_context": {
            "mode": mode,
            "workspace_uri": "workspace://project/proj-1/page/001",
            "requested_by": "user@example.com",
            "target_regions": [],
            "selected_layer_ids": [],
        },
    }


if __name__ == "__main__":
    unittest.main()
