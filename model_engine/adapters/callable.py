from __future__ import annotations

from importlib import import_module
from typing import Callable

from ..contracts.models import StageManifest
from ..contracts.stages import StageRequest, StageResponse
from .base import ModelAdapter


StageCallable = Callable[[StageRequest], StageResponse]


class CallableModelAdapter(ModelAdapter):
    """Wrap a Python callable so it can participate in capability-based selection."""

    def __init__(
        self,
        manifest: StageManifest,
        *,
        entrypoint: StageCallable,
    ) -> None:
        self._manifest = manifest
        self._entrypoint = entrypoint

    @property
    def manifest(self) -> StageManifest:
        return self._manifest

    def run(self, request: StageRequest) -> StageResponse:
        return self._entrypoint(request)

    @classmethod
    def from_import_path(
        cls,
        manifest: StageManifest,
        *,
        import_path: str,
    ) -> "CallableModelAdapter":
        return cls(manifest, entrypoint=load_stage_callable(import_path))


def load_stage_callable(import_path: str) -> StageCallable:
    module_name, sep, symbol_name = import_path.partition(":")
    if not sep:
        raise ValueError(
            "import_path must use 'module.submodule:symbol' format"
        )

    module = import_module(module_name)
    try:
        target = getattr(module, symbol_name)
    except AttributeError as exc:
        raise ValueError(f"Callable not found: {import_path}") from exc

    if not callable(target):
        raise ValueError(f"Imported symbol is not callable: {import_path}")
    return target
