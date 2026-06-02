from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
from unittest.mock import patch

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from fastapi.testclient import TestClient
except ImportError as exc:  # pragma: no cover - local environment helper
    raise SystemExit(
        "fastapi is required for this REST verification script. "
        "Run it in the API image, for example:\n"
        "docker compose run --no-deps --rm model-engine "
        "python3 model_engine/scripts/verify_translate_existing_blocks.py"
    ) from exc

from model_engine.api.app import create_app
from model_engine.api.jobs import ModelJobManager, OrchestratedJobExecutor
from model_engine.contracts.document_ir import TextBlock


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that a UI-style translate request with existing text_blocks runs "
            "translation only, without re-running text detection or OCR."
        )
    )
    parser.add_argument(
        "--transport",
        choices=("json", "multipart"),
        default="json",
        help="HTTP request shape used against the in-process FastAPI app.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=3.0,
        help="Maximum time to wait for the background model job.",
    )
    args = parser.parse_args()

    payload = _ui_translate_payload()
    job_manager = ModelJobManager(executor=OrchestratedJobExecutor())
    app = create_app(job_manager=job_manager)
    client = TestClient(app)

    with patch(
        "model_engine.builtin_models.craft_text_detection._detect_with_craft",
        side_effect=AssertionError("translate unexpectedly ran text detection"),
    ), patch(
        "model_engine.builtin_models.manga_ocr._recognize_with_manga_ocr",
        side_effect=AssertionError("translate unexpectedly ran OCR"),
    ), patch(
        "model_engine.builtin_models.openai_compatible_translation._translate_blocks_with_openai_compatible",
        side_effect=_fake_translate_blocks,
    ):
        if args.transport == "multipart":
            response = client.post(
                "/v1/jobs",
                files={"metadata": (None, json.dumps(payload), "application/json")},
            )
        else:
            response = client.post("/v1/jobs", json=payload)

        _assert_response(response.status_code == 202, f"expected 202, got {response.status_code}")
        detail = _wait_for_terminal_job(
            client,
            str(response.json()["job_id"]),
            timeout_seconds=args.timeout_seconds,
        )

    _assert_response(detail["status"] == "succeeded", f"job failed: {detail.get('error')}")
    stage_names = [report["stage_name"] for report in detail["stage_reports"]]
    _assert_response(stage_names == ["translation"], f"unexpected stages: {stage_names}")

    stage_meta = detail["document"].get("stage_meta", {})
    _assert_response("text_detection" not in stage_meta, "text_detection stage_meta was added")
    _assert_response("ocr" not in stage_meta, "ocr stage_meta was added")
    _assert_response("translation" in stage_meta, "translation stage_meta is missing")

    translated_blocks = detail["document"]["text_blocks"]
    expected_blocks = payload["document"]["text_blocks"]
    _assert_response(len(translated_blocks) == len(expected_blocks), "text block count changed")
    for actual, expected in zip(translated_blocks, expected_blocks):
        _assert_response(actual["block_id"] == expected["block_id"], "block_id changed")
        _assert_response(
            actual["source_lang_text"] == expected["source_lang_text"],
            "source_lang_text changed",
        )
        _assert_response(actual["bbox"] == expected["bbox"], "bbox changed")
        _assert_response(actual["polygon"] == expected["polygon"], "polygon changed")
        _assert_response(actual["translated_text"], "translated_text is empty")

    summary = {
        "ok": True,
        "transport": args.transport,
        "job_id": detail["job_id"],
        "status": detail["status"],
        "stage_names": stage_names,
        "source_texts": [block["source_lang_text"] for block in translated_blocks],
        "translated_texts": [block["translated_text"] for block in translated_blocks],
        "geometry_preserved": True,
        "reran_text_detection": False,
        "reran_ocr": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _wait_for_terminal_job(
    client: TestClient,
    job_id: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/v1/jobs/{job_id}")
        _assert_response(
            response.status_code == 200,
            f"unexpected poll status {response.status_code}: {response.text}",
        )
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "partial"}:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for job {job_id}")


def _fake_translate_blocks(
    blocks: list[TextBlock],
    config: dict[str, object],
    api_key: str | None,
) -> list[dict[str, str]]:
    _ = config
    _ = api_key
    translations = {
        "block_0001": "안녕하세요",
        "block_0002": "세로쓰기 텍스트",
    }
    return [
        {
            "block_id": block.block_id,
            "translated_text": translations.get(block.block_id, f"번역:{block.source_lang_text}"),
        }
        for block in blocks
    ]


def _ui_translate_payload() -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "idempotency_key": "verify:translate-existing-blocks:v1",
        "operation_kind": "translate",
        "request_ref": "project/proj-verify/page/001",
        "document": {
            "id": "doc_verify_page_001",
            "name": "verify-page-001",
            "width": 800,
            "height": 1200,
            "layers": [],
            "text_blocks": [
                {
                    "block_id": "block_0001",
                    "source_lang_text": "こんにちは",
                    "translated_text": "",
                    "polygon": [],
                    "bbox": {"x": 120, "y": 80, "width": 160, "height": 70},
                    "reading_order": 1,
                    "writing_mode": "vertical",
                    "source_region_ref": "region_0001",
                },
                {
                    "block_id": "block_0002",
                    "source_lang_text": "縦書きテキスト",
                    "translated_text": "",
                    "polygon": [
                        {"x": 410, "y": 220},
                        {"x": 470, "y": 220},
                        {"x": 470, "y": 390},
                        {"x": 410, "y": 390},
                    ],
                    "bbox": {"x": 410, "y": 220, "width": 60, "height": 170},
                    "reading_order": 2,
                    "writing_mode": "vertical",
                    "source_region_ref": "region_0002",
                },
            ],
            "stage_meta": {},
        },
        "artifacts": {},
        "runtime_context": {
            "mode": "local",
            "workspace_uri": "workspace://verify/translate-existing-blocks",
            "requested_by": "verify-script",
            "target_regions": [],
            "selected_layer_ids": [],
            "metadata": {
                "translation_backend": "openai_compatible",
                "openai_compatible_base_url": "http://127.0.0.1:1234/v1",
                "translation_model_name": "verify-fake-translator",
            },
        },
    }


def _assert_response(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
