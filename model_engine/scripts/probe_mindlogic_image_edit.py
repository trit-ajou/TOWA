from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://factchat-cloud.mindlogic.ai/v1/gateway"
DEFAULT_MODEL = "gemini-2.5-flash-image"
DEFAULT_PROMPT = (
    "Use the provided manga page as the source image. Remove all visible text and sound effects. "
    "Reconstruct the original manga background, lineart, screentones, and speech balloon interiors naturally. "
    "Do not add any new text. Preserve the page composition and character art."
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Mindlogic Gateway image-edit style requests with a real input image."
    )
    parser.add_argument(
        "--image",
        default="model_engine/samples/dlsite/sample.jpg",
        help="Input image path to send to the gateway.",
    )
    parser.add_argument(
        "--output-dir",
        default="model_engine/.runtime/mindlogic_probe",
        help="Directory for raw response and generated images.",
    )
    parser.add_argument(
        "--api-key-env",
        default="TEST_KEY",
        help="Environment variable containing the Mindlogic API key.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Mindlogic Gateway base URL.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Image model name.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Edit prompt.",
    )
    parser.add_argument(
        "--image-field",
        choices=["image", "images", "input_image", "reference_images"],
        default="image",
        help="Payload field used for the input image. Change this if the gateway schema differs.",
    )
    parser.add_argument(
        "--image-value",
        choices=["data_url", "base64"],
        default="data_url",
        help="How to encode the image value.",
    )
    parser.add_argument(
        "--extra-json",
        default=None,
        help='Extra JSON object merged into the request payload, e.g. \'{"quality":"high"}\'.',
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout seconds.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Polling interval for async image generation responses.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=180.0,
        help="Total polling timeout seconds for async responses.",
    )
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key. Set {args.api_key_env}=... before running.")

    image_path = Path(args.image).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(
        image_path=image_path,
        model=args.model,
        prompt=args.prompt,
        image_field=args.image_field,
        image_value=args.image_value,
        extra_json=args.extra_json,
    )
    endpoint = args.base_url.rstrip("/") + "/images/generate/"
    print(f"POST {endpoint}")
    print(f"model={args.model} image_field={args.image_field} image={image_path}")

    response_payload = _post_json(
        endpoint,
        payload=payload,
        api_key=api_key,
        timeout=args.timeout,
    )
    response_payload = _poll_if_needed(
        response_payload,
        base_url=args.base_url,
        model=args.model,
        api_key=api_key,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        poll_timeout=args.poll_timeout,
    )

    raw_response_path = output_dir / "mindlogic_response.json"
    raw_response_path.write_text(
        json.dumps(response_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    saved_images = _save_images(response_payload, output_dir)

    print(f"raw_response={raw_response_path}")
    if saved_images:
        for path in saved_images:
            print(f"saved_image={path}")
        return 0

    print("No image was found in the response. Inspect raw_response for the actual schema.")
    return 2


def _build_payload(
    *,
    image_path: Path,
    model: str,
    prompt: str,
    image_field: str,
    image_value: str,
    extra_json: str | None,
) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    value = f"data:{mime_type};base64,{encoded}" if image_value == "data_url" else encoded

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "number_of_images": 1,
    }
    if image_field == "images":
        payload["images"] = [value]
    elif image_field == "reference_images":
        payload["reference_images"] = [{"url": value}]
    else:
        payload[image_field] = value

    if extra_json:
        extra = json.loads(extra_json)
        if not isinstance(extra, dict):
            raise ValueError("--extra-json must decode to a JSON object")
        payload.update(extra)
    return payload


def _post_json(
    url: str,
    *,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return _read_json_response(resp.read())
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Mindlogic API failed: HTTP {exc.code}: {raw}") from exc


def _poll_if_needed(
    payload: dict[str, Any],
    *,
    base_url: str,
    model: str,
    api_key: str,
    timeout: float,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, Any]:
    operation_id = payload.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id:
        return payload

    deadline = time.monotonic() + poll_timeout
    poll_url = base_url.rstrip("/") + f"/images/generate/{parse.quote(operation_id)}/"
    while time.monotonic() < deadline:
        status = _get_json(
            poll_url,
            params={"model": model},
            api_key=api_key,
            timeout=timeout,
        )
        print(f"poll status={status.get('status')}")
        if status.get("status") in {"completed", "succeeded", "failed", "error"}:
            return status
        time.sleep(poll_interval)
    raise TimeoutError(f"Timed out polling operation_id={operation_id}")


def _get_json(
    url: str,
    *,
    params: dict[str, str],
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    query = parse.urlencode(params)
    req = request.Request(f"{url}?{query}", method="GET")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return _read_json_response(resp.read())
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Mindlogic poll failed: HTTP {exc.code}: {raw}") from exc


def _read_json_response(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Expected JSON object response")
    return payload


def _save_images(payload: dict[str, Any], output_dir: Path) -> list[Path]:
    saved: list[Path] = []
    for index, item in enumerate(_iter_image_items(payload), start=1):
        image_bytes = _image_bytes_from_item(item)
        if image_bytes is None:
            continue
        path = output_dir / f"mindlogic_output_{index}.png"
        path.write_bytes(image_bytes)
        saved.append(path)
    return saved


def _iter_image_items(payload: dict[str, Any]) -> list[Any]:
    data = payload.get("data")
    if isinstance(data, list):
        return data
    images = payload.get("images")
    if isinstance(images, list):
        return images
    output = payload.get("output")
    if isinstance(output, list):
        return output
    return []


def _image_bytes_from_item(item: Any) -> bytes | None:
    if isinstance(item, str):
        return _decode_image_value(item)
    if not isinstance(item, dict):
        return None
    for key in ("url", "b64_json", "base64", "image", "image_url"):
        value = item.get(key)
        if isinstance(value, str):
            image_bytes = _decode_image_value(value)
            if image_bytes is not None:
                return image_bytes
    return None


def _decode_image_value(value: str) -> bytes | None:
    if value.startswith("data:image/"):
        _, b64 = value.split(",", 1)
        return base64.b64decode(b64)
    if value.startswith("http://") or value.startswith("https://"):
        with request.urlopen(value, timeout=120.0) as resp:
            return resp.read()
    try:
        return base64.b64decode(value, validate=True)
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
