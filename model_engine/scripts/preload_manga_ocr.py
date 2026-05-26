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
        description="Preload manga-ocr model weights into the shared cache directory."
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("TOWA_MODEL_CACHE_DIR", "/cache/models"),
        help="Cache directory mounted from the host.",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    torch_home = cache_dir / "torch"
    hf_home = cache_dir / "huggingface"
    transformers_cache = hf_home / "transformers"

    os.environ["TOWA_MODEL_CACHE_DIR"] = str(cache_dir)
    os.environ["HOME"] = str(cache_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)
    os.environ["TORCH_HOME"] = str(torch_home)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["TRANSFORMERS_CACHE"] = str(transformers_cache)

    torch_home.mkdir(parents=True, exist_ok=True)
    hf_home.mkdir(parents=True, exist_ok=True)
    transformers_cache.mkdir(parents=True, exist_ok=True)

    try:
        from manga_ocr import MangaOcr
    except ImportError as exc:
        raise RuntimeError(
            "Failed to import manga_ocr while preloading weights. "
            f"Original import error: {exc!r}"
        ) from exc

    recognizer = MangaOcr()
    summary = {
        "status": "ready",
        "cache_dir": str(cache_dir),
        "torch_home": os.environ["TORCH_HOME"],
        "hf_home": os.environ["HF_HOME"],
        "transformers_cache": os.environ["TRANSFORMERS_CACHE"],
        "model_name": getattr(recognizer, "pretrained_model_name_or_path", "kha-white/manga-ocr-base"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
