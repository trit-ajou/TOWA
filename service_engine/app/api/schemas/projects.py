from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import PageStatus, ProjectStatus


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    thumbnail_url: str | None = None
    source_lang: str
    target_lang: str
    status: ProjectStatus
    folder: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class ProjectPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    thumbnail_url: str | None = None
    source_lang: str | None = None
    target_lang: str | None = None
    status: ProjectStatus | None = None
    folder: str | None = None
    config: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    thumbnail_url: str | None = None
    source_lang: str
    target_lang: str
    page_count: int
    status: ProjectStatus
    folder: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ProjectResponse]


class ProjectDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deleted: bool
    project_id: str


class PageSnapshotPageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    index: int
    status: PageStatus
    text_blocks: list[dict[str, Any]] = Field(default_factory=list)


class PageSnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: PageSnapshotPageMetadata


class PageSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    index: int
    status: PageStatus
    thumbnail_url: str
    updated_at: datetime


class PageSummaryEnvelope(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page: PageSummaryResponse


class PageListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[PageSummaryResponse]


class PageDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deleted: bool
    page_id: str
