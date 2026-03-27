"""Stage abstractions for the model engine."""

from .adapter_stage import AdapterBackedStage
from .base import Stage, StaticStage

__all__ = ["AdapterBackedStage", "Stage", "StaticStage"]
