"""Stage abstractions for the model engine."""

from importlib import import_module

from .adapter_stage import AdapterBackedStage
from .base import Stage, StaticStage


def __getattr__(name: str):
    if name != "run_mask_or_erase_planning":
        raise AttributeError(f"module 'model_engine.stages' has no attribute {name!r}")

    module = import_module("model_engine.stages.mask_or_erase_planning")
    value = getattr(module, name)
    globals()[name] = value
    return value

__all__ = ["AdapterBackedStage", "Stage", "StaticStage", "run_mask_or_erase_planning"]
