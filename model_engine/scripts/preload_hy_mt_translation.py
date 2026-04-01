from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_engine.custom_models.hy_mt_translation import (
    HY_MT_TRANSLATION_DEFAULT_MODEL,
    preload_hy_mt_model,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preload Tencent HY-MT translation model into the shared cache."
    )
    parser.add_argument(
        "--model-name",
        default=HY_MT_TRANSLATION_DEFAULT_MODEL,
        help="Model id or local path passed to transformers.from_pretrained().",
    )
    parser.add_argument(
        "--cache-dir",
        default="/cache/models",
        help="Root cache directory used by the runtime image.",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HOME", str(cache_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))
    os.environ.setdefault(
        "TRANSFORMERS_CACHE",
        str(cache_dir / "huggingface" / "transformers"),
    )
    preload_hy_mt_model(model_name_or_path=args.model_name)
    print(f"Preloaded HY-MT model into cache: {args.model_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
