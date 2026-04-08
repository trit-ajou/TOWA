from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping, Optional


DEFAULT_RUNTIME_CONFIG_NAME = "runtime_config.json"
RUNTIME_CONFIG_ENV = "TOWA_RUNTIME_CONFIG_FILE"


def load_runtime_config(
    *,
    environ: Optional[Mapping[str, str]] = None,
    config_path: Optional[str] = None,
) -> dict[str, object]:
    env = environ if environ is not None else os.environ
    configured_path = config_path or env.get(RUNTIME_CONFIG_ENV)
    candidate = _first_existing_config_path(configured_path)
    if candidate is None:
        return {}
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Runtime config must be a JSON object: {candidate}")
    return payload


def runtime_config_value(
    config: Mapping[str, object],
    env_key: str,
    *,
    default: str = "",
    aliases: tuple[str, ...] = (),
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    env = environ if environ is not None else os.environ
    env_value = env.get(env_key)
    if env_value not in {None, ""}:
        return str(env_value)

    for key in (env_key, *aliases):
        value = _nested_config_value(config, key)
        if value not in {None, ""}:
            return str(value)
    return default


def _first_existing_config_path(configured_path: Optional[str]) -> Optional[Path]:
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Runtime config file not found: {path}")

    package_root = Path(__file__).resolve().parents[1]
    candidates = [
        Path.cwd() / ".runtime" / DEFAULT_RUNTIME_CONFIG_NAME,
        Path.cwd() / "model_engine" / ".runtime" / DEFAULT_RUNTIME_CONFIG_NAME,
        package_root / ".runtime" / DEFAULT_RUNTIME_CONFIG_NAME,
        Path("/workspace_out") / DEFAULT_RUNTIME_CONFIG_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _nested_config_value(config: Mapping[str, object], key: str) -> object:
    if key in config:
        return config[key]

    current: object = config
    for part in key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current
