from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Union

from ..contracts.artifacts import ArtifactDescriptor
from ..contracts.patches import PatchOperation
from ..contracts.stages import StageReport, StageRequest, StageResponse, StageStatus


class Stage(ABC):
    @property
    @abstractmethod
    def stage_name(self) -> str:
        raise NotImplementedError

    def stage_config(self) -> dict[str, object]:
        return {}

    @abstractmethod
    def run(self, request: StageRequest) -> StageResponse:
        raise NotImplementedError


class StaticStage(Stage):
    """A deterministic stage used to validate the orchestration contract."""

    def __init__(
        self,
        stage_name: str,
        *,
        status: StageStatus = StageStatus.SUCCEEDED,
        patches: Optional[list[PatchOperation]] = None,
        artifacts: Optional[dict[str, ArtifactDescriptor]] = None,
        warnings: Optional[list[str]] = None,
        metrics: Optional[dict[str, Union[float, int, str]]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        config: Optional[dict[str, object]] = None,
    ) -> None:
        self._stage_name = stage_name
        self._status = status
        self._patches = patches or []
        self._artifacts = artifacts or {}
        self._warnings = warnings or []
        self._metrics = metrics or {}
        self._error_code = error_code
        self._error_message = error_message
        self._config = config or {}

    @property
    def stage_name(self) -> str:
        return self._stage_name

    def stage_config(self) -> dict[str, object]:
        return dict(self._config)

    def run(self, request: StageRequest) -> StageResponse:
        started_at = datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)
        input_refs = sorted(request.artifacts.keys())
        output_refs = sorted(self._artifacts.keys())
        report = StageReport(
            stage_name=self.stage_name,
            stage_run_id=request.stage_run_id,
            status=self._status,
            input_refs=input_refs,
            output_refs=output_refs,
            warnings=list(self._warnings),
            metrics=dict(self._metrics),
            provider=request.credential_bindings.get("primary_provider"),
            error_code=self._error_code,
            error_message=self._error_message,
            started_at=started_at,
            finished_at=finished_at,
        )
        return StageResponse(
            schema_version=request.schema_version,
            stage_name=self.stage_name,
            stage_run_id=request.stage_run_id,
            status=self._status,
            patches=list(self._patches),
            artifacts=dict(self._artifacts),
            stage_report=report,
        )
