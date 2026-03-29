from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib import error

from model_engine.api.service_bridge import (
    ServiceEngineBridgeClient,
    ServiceEngineHTTPError,
    ServiceEngineUnavailableError,
)


class ServiceEngineBridgeClientTests(unittest.TestCase):
    def test_post_forwards_authorization_and_json_body(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(http_request: object, timeout: float = 0.0) -> "_FakeHttpResponse":
            captured["url"] = http_request.full_url
            captured["headers"] = dict(http_request.header_items())
            captured["body"] = json.loads(http_request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeHttpResponse({"status": "ok"})

        client = ServiceEngineBridgeClient(
            base_url="http://service-engine:8000",
            timeout_seconds=7.5,
        )

        with patch("model_engine.api.service_bridge.request.urlopen", side_effect=fake_urlopen):
            response = client.post(
                "/usage/jobs",
                body={
                    "idempotency_key": "page-1-translate",
                    "operation_kind": "translate",
                    "request_ref": "page-1",
                    "estimated_units": 20,
                },
                authorization="Bearer demo-token",
            )

        self.assertEqual({"status": "ok"}, response)
        self.assertEqual("http://service-engine:8000/usage/jobs", captured["url"])
        self.assertEqual("Bearer demo-token", captured["headers"]["Authorization"])
        self.assertEqual("application/json", captured["headers"]["Content-type"])
        self.assertEqual(7.5, captured["timeout"])
        self.assertEqual("translate", captured["body"]["operation_kind"])

    def test_http_error_payload_is_preserved(self) -> None:
        client = ServiceEngineBridgeClient(base_url="http://service-engine:8000")
        payload = {
            "error": {
                "code": "insufficient_credits",
                "message": "not enough balance",
                "retryable": False,
                "details": None,
            }
        }

        http_error = error.HTTPError(
            url="http://service-engine:8000/usage/jobs",
            code=409,
            msg="Conflict",
            hdrs=None,
            fp=io.BytesIO(json.dumps(payload).encode("utf-8")),
        )

        with patch("model_engine.api.service_bridge.request.urlopen", side_effect=http_error):
            with self.assertRaises(ServiceEngineHTTPError) as exc_info:
                client.post("/usage/jobs", body={"estimated_units": 1})

        self.assertEqual(409, exc_info.exception.status_code)
        self.assertEqual(payload, exc_info.exception.payload)

    def test_unreachable_service_raises_specific_error(self) -> None:
        client = ServiceEngineBridgeClient(base_url="http://service-engine:8000")

        with patch(
            "model_engine.api.service_bridge.request.urlopen",
            side_effect=error.URLError("connection refused"),
        ):
            with self.assertRaises(ServiceEngineUnavailableError):
                client.get("/healthz")


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


if __name__ == "__main__":
    unittest.main()
