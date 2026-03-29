from __future__ import annotations

from abc import ABC, abstractmethod

from ..contracts.models import StageManifest
from ..contracts.stages import StageRequest, StageResponse


class ModelAdapter(ABC):
    """Adapter layer between a stage capability and a concrete model/provider."""

    @property
    @abstractmethod
    def manifest(self) -> StageManifest:
        raise NotImplementedError

    def adapter_id(self) -> str:
        return self.manifest.adapter_id

    @abstractmethod
    def run(self, request: StageRequest) -> StageResponse:
        raise NotImplementedError
