from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from typing import Callable

from ..contracts.stages import StageRequest, StageResponse
from .serde import stage_request_from_data, stage_response_to_data


def _load_handler(import_path: str) -> Callable[[StageRequest], StageResponse]:
    module_name, attr_name = import_path.split(":", 1)
    module = importlib.import_module(module_name)
    handler = getattr(module, attr_name)
    return handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handler", required=True)
    args = parser.parse_args()

    try:
        raw_payload = sys.stdin.read()
        request_payload = json.loads(raw_payload)
        request = stage_request_from_data(request_payload)
        handler = _load_handler(args.handler)
        response = handler(request)
        json.dump(stage_response_to_data(response), sys.stdout)
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
