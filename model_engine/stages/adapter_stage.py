from __future__ import annotations

from typing import Optional

from ..contracts.models import StageKind
from ..contracts.stages import StageRequest, StageResponse
from ..models.registry import ModelRegistry
from .base import Stage


class AdapterBackedStage(Stage):
    """A stage that selects and runs a compatible model adapter from the registry."""

    def __init__(
        self,
        stage_name: str,
        *,
        stage_kind: StageKind,
        registry: ModelRegistry,
        preferred_model_id: Optional[str] = None,
        config: Optional[dict[str, object]] = None,
    ) -> None:
        self._stage_name = stage_name
        self._stage_kind = stage_kind
        self._registry = registry
        self._preferred_model_id = preferred_model_id
        self._config = config or {}

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        config = dict(self._config)
        if self._preferred_model_id:
            config["preferred_model_id"] = self._preferred_model_id
        return config

    def run(self, request: StageRequest) -> StageResponse:
        preferred_model_id = request.stage_config.get("preferred_model_id")
        if not isinstance(preferred_model_id, str):
            preferred_model_id = self._preferred_model_id

        selection = self._registry.select_for_request(
            stage_kind=self._stage_kind,
            request=request,
            preferred_model_id=preferred_model_id,
        )
        response = selection.adapter.run(request)
        response.stage_report.metrics.setdefault("model_id", selection.manifest.model_id)
        response.stage_report.metrics.setdefault("adapter_id", selection.manifest.adapter_id)
        response.stage_report.metrics.setdefault("selection_reason", selection.reason)
        return response
