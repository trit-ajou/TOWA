from __future__ import annotations

import unittest

from model_engine.service_engine import (
    ServiceEngineAuthError,
    ServiceEngineClient,
    ServiceEngineCreditError,
)
from model_engine.api.service_bridge import ServiceEngineHTTPError, ServiceEngineUnavailableError


class ServiceEngineClientTests(unittest.TestCase):
    def test_create_usage_job_forwards_bearer_session_key_and_payload(self) -> None:
        bridge = _FakeBridgeClient(
            post_payload={
                "job_id": "svc_job_1",
                "status": "authorized",
                "reserved_units": 20,
                "hold_expires_at": "2026-04-01T00:10:00Z",
            }
        )
        client = ServiceEngineClient(base_url="http://service-engine:8000", bridge_client=bridge)

        response = client.create_usage_job(
            "demo-session",
            idempotency_key="translate:page-1:fingerprint",
            operation_kind="translate",
            request_ref="page-1",
            estimated_units=20,
        )

        self.assertEqual("svc_job_1", response.job_id)
        self.assertEqual("/usage/jobs", bridge.last_post["path"])
        self.assertEqual("Bearer demo-session", bridge.last_post["authorization"])
        self.assertEqual("translate", bridge.last_post["body"]["operation_kind"])

    def test_auth_errors_are_mapped_to_specific_exception(self) -> None:
        bridge = _FakeBridgeClient(
            get_error=ServiceEngineHTTPError(
                401,
                {
                    "error": {
                        "code": "session_expired",
                        "message": "session expired",
                        "retryable": False,
                        "details": None,
                    }
                },
            )
        )
        client = ServiceEngineClient(base_url="http://service-engine:8000", bridge_client=bridge)

        with self.assertRaises(ServiceEngineAuthError) as exc_info:
            client.get_auth_me("expired-session")

        self.assertEqual("session_expired", exc_info.exception.code)

    def test_credit_errors_are_mapped_from_error_envelope(self) -> None:
        bridge = _FakeBridgeClient(
            post_error=ServiceEngineHTTPError(
                409,
                {
                    "error": {
                        "code": "insufficient_credits",
                        "message": "not enough balance",
                        "retryable": False,
                        "details": None,
                    }
                },
            )
        )
        client = ServiceEngineClient(base_url="http://service-engine:8000", bridge_client=bridge)

        with self.assertRaises(ServiceEngineCreditError) as exc_info:
            client.create_usage_job(
                "demo-session",
                idempotency_key="mask:page-1:fingerprint",
                operation_kind="mask",
                request_ref="page-1",
                estimated_units=5,
            )

        self.assertEqual(409, exc_info.exception.status_code)

    def test_transport_failures_are_wrapped(self) -> None:
        bridge = _FakeBridgeClient(get_error=ServiceEngineUnavailableError("connection refused"))
        client = ServiceEngineClient(base_url="http://service-engine:8000", bridge_client=bridge)

        with self.assertRaisesRegex(Exception, "connection refused"):
            client.get_auth_me("demo-session")


class _FakeBridgeClient:
    def __init__(
        self,
        *,
        get_payload: dict[str, object] | None = None,
        post_payload: dict[str, object] | None = None,
        get_error: Exception | None = None,
        post_error: Exception | None = None,
    ) -> None:
        self._get_payload = get_payload or {
            "user": {
                "id": "user_1",
                "email": "user@example.com",
                "nickname": "tester",
                "status": "active",
                "created_at": "2026-04-01T00:00:00Z",
            },
            "credit_balance": 1000,
            "reserved_units": 0,
        }
        self._post_payload = post_payload or {}
        self._get_error = get_error
        self._post_error = post_error
        self.last_get: dict[str, object] | None = None
        self.last_post: dict[str, object] | None = None

    def get(self, path: str, *, authorization: str | None = None) -> dict[str, object]:
        self.last_get = {
            "path": path,
            "authorization": authorization,
        }
        if self._get_error is not None:
            raise self._get_error
        return dict(self._get_payload)

    def post(
        self,
        path: str,
        *,
        body: dict[str, object] | None = None,
        authorization: str | None = None,
    ) -> dict[str, object]:
        self.last_post = {
            "path": path,
            "body": dict(body or {}),
            "authorization": authorization,
        }
        if self._post_error is not None:
            raise self._post_error
        return dict(self._post_payload)


if __name__ == "__main__":
    unittest.main()
