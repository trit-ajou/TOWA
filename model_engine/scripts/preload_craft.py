from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preload CRAFT model weights into the shared cache directory."
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("TOWA_MODEL_CACHE_DIR", "/cache/models"),
        help="Cache directory mounted from the host.",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["TOWA_MODEL_CACHE_DIR"] = str(cache_dir)
    os.environ["HOME"] = str(cache_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)
    os.environ["TORCH_HOME"] = str(cache_dir / "torch")
    (cache_dir / "torch").mkdir(parents=True, exist_ok=True)

    try:
        from craft_text_detector import Craft
    except ImportError as exc:
        raise RuntimeError(
            "Failed to import craft_text_detector while preloading weights. "
            f"Original import error: {exc!r}"
        ) from exc

    detector = Craft(output_dir=None, crop_type="poly", cuda=False)
    try:
        summary = {
            "status": "ready",
            "cache_dir": str(cache_dir),
            "torch_home": os.environ["TORCH_HOME"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        unload_all = getattr(detector, "unload_all_models", None)
        if callable(unload_all):
            unload_all()
        else:
            unload_craftnet = getattr(detector, "unload_craftnet_model", None)
            unload_refinenet = getattr(detector, "unload_refinenet_model", None)
            if callable(unload_craftnet):
                unload_craftnet()
            if callable(unload_refinenet):
                unload_refinenet()


if __name__ == "__main__":
    raise SystemExit(main())
