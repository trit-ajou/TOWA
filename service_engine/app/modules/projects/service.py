from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session, contains_eager, joinedload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.clock import utcnow
from app.db.enums import PageStatus, ProjectStatus
from app.modules.auth import service as auth_service
from app.modules.projects.models import Page, PageSnapshot, Project

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


class ProjectStorageError(RuntimeError):
    pass


class ProjectNotFoundError(ProjectStorageError):
    pass


class PageNotFoundError(ProjectStorageError):
    pass


class ProjectConflictError(ProjectStorageError):
    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class PageConflictError(ProjectStorageError):
    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class SnapshotValidationError(ProjectStorageError):
    pass


@dataclass(frozen=True)
class BinaryPayload:
    content: bytes
    media_type: str

    @property
    def byte_size(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class PageSnapshotWrite:
    page_id: str
    project_id: str
    index: int
    status: PageStatus
    metadata: dict[str, Any]
    original_image: BinaryPayload
    layer_blob: BinaryPayload
    thumbnail: BinaryPayload


@dataclass(frozen=True)
class StoredPageSnapshot:
    metadata: dict[str, Any]
    original_image: BinaryPayload
    layer_blob: BinaryPayload
    thumbnail: BinaryPayload


def _normalize_ulid(value: str, *, field_name: str) -> str:
    normalized = value.strip().upper()
    if not ULID_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a canonical ULID.")
    return normalized


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank when provided.")
    return normalized


def _normalize_folder(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _project_query_for_user(user_id) -> Select[tuple[Project]]:
    return select(Project).where(Project.user_id == user_id)


def _load_project(session: Session, *, user_id, project_id: str, for_update: bool = False) -> Project:
    statement = _project_query_for_user(user_id).where(Project.id == project_id)
    if for_update:
        statement = statement.with_for_update()
    project = session.scalar(statement)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} was not found.")
    return project


def _load_page(
    session: Session,
    *,
    user_id,
    page_id: str,
    for_update: bool = False,
    include_snapshot: bool = False,
) -> Page:
    statement = (
        select(Page)
        .join(Page.project)
        .where(
            Page.id == page_id,
            Project.user_id == user_id,
        )
        .options(contains_eager(Page.project))
    )
    if include_snapshot and not for_update:
        statement = statement.options(joinedload(Page.snapshot))
    if for_update:
        statement = statement.with_for_update()
    page = session.scalar(statement)
    if page is None:
        raise PageNotFoundError(f"Page {page_id} was not found.")
    if include_snapshot and for_update:
        snapshot = session.scalar(
            select(PageSnapshot)
            .where(PageSnapshot.page_id == page.id)
            .with_for_update(),
        )
        set_committed_value(page, "snapshot", snapshot)
    return page


def _page_count_map(session: Session, *, project_ids: list[str]) -> dict[str, int]:
    if not project_ids:
        return {}
    rows = session.execute(
        select(Page.project_id, func.count(Page.id))
        .where(Page.project_id.in_(project_ids))
        .group_by(Page.project_id),
    ).all()
    return {project_id: page_count for project_id, page_count in rows}


def _present_project(project: Project, *, page_count: int) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "thumbnail_url": project.thumbnail_url,
        "source_lang": project.source_lang,
        "target_lang": project.target_lang,
        "page_count": page_count,
        "status": project.status,
        "folder": project.folder,
        "config": copy.deepcopy(project.config),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _canonical_metadata(write: PageSnapshotWrite) -> dict[str, Any]:
    metadata = copy.deepcopy(write.metadata)
    page = metadata.setdefault("page", {})
    page["id"] = write.page_id
    page["project_id"] = write.project_id
    page["index"] = write.index
    page["status"] = write.status.value
    return metadata


def _snapshot_from_model(snapshot: PageSnapshot) -> StoredPageSnapshot:
    return StoredPageSnapshot(
        metadata=copy.deepcopy(snapshot.metadata_json),
        original_image=BinaryPayload(
            content=snapshot.original_image_bytes,
            media_type=snapshot.original_image_media_type,
        ),
        layer_blob=BinaryPayload(
            content=snapshot.layer_blob_bytes,
            media_type=snapshot.layer_blob_media_type,
        ),
        thumbnail=BinaryPayload(
            content=snapshot.thumbnail_bytes,
            media_type=snapshot.thumbnail_media_type,
        ),
    )


def create_project(
    session: Session,
    *,
    session_token: str,
    project_id: str,
    name: str,
    thumbnail_url: str | None,
    source_lang: str,
    target_lang: str,
    status: ProjectStatus,
    folder: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized_project_id = _normalize_ulid(project_id, field_name="id")
    normalized_name = _normalize_required_text(name, field_name="name")
    normalized_thumbnail_url = _normalize_optional_text(thumbnail_url, field_name="thumbnail_url")
    normalized_source_lang = _normalize_required_text(source_lang, field_name="source_lang")
    normalized_target_lang = _normalize_required_text(target_lang, field_name="target_lang")
    normalized_folder = _normalize_folder(folder)

    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        if session.get(Project, normalized_project_id) is not None:
            raise ProjectConflictError(
                f"Project {normalized_project_id} already exists.",
                reason="duplicate_project_id",
            )

        project = Project(
            id=normalized_project_id,
            user_id=context.user.id,
            name=normalized_name,
            thumbnail_url=normalized_thumbnail_url,
            source_lang=normalized_source_lang,
            target_lang=normalized_target_lang,
            status=status,
            folder=normalized_folder,
            config=copy.deepcopy(config),
        )
        session.add(project)
        session.flush()
        return _present_project(project, page_count=0)


def list_projects(session: Session, *, session_token: str) -> list[dict[str, Any]]:
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    projects = session.scalars(
        _project_query_for_user(context.user.id).order_by(Project.updated_at.desc(), Project.created_at.desc()),
    ).all()
    counts = _page_count_map(session, project_ids=[project.id for project in projects])
    return [_present_project(project, page_count=counts.get(project.id, 0)) for project in projects]


def get_project(session: Session, *, session_token: str, project_id: str) -> dict[str, Any]:
    normalized_project_id = _normalize_ulid(project_id, field_name="project_id")
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    project = _load_project(session, user_id=context.user.id, project_id=normalized_project_id)
    counts = _page_count_map(session, project_ids=[project.id])
    return _present_project(project, page_count=counts.get(project.id, 0))


def update_project(
    session: Session,
    *,
    session_token: str,
    project_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    normalized_project_id = _normalize_ulid(project_id, field_name="project_id")

    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        project = _load_project(session, user_id=context.user.id, project_id=normalized_project_id, for_update=True)

        for field_name, value in updates.items():
            if field_name == "name":
                project.name = _normalize_required_text(value, field_name="name")
            elif field_name == "thumbnail_url":
                project.thumbnail_url = _normalize_optional_text(value, field_name="thumbnail_url")
            elif field_name == "source_lang":
                project.source_lang = _normalize_required_text(value, field_name="source_lang")
            elif field_name == "target_lang":
                project.target_lang = _normalize_required_text(value, field_name="target_lang")
            elif field_name == "status":
                if value is None:
                    raise ValueError("status must not be null.")
                project.status = value
            elif field_name == "folder":
                if value is None:
                    raise ValueError("folder must not be null.")
                project.folder = _normalize_folder(value)
            elif field_name == "config":
                if value is None:
                    raise ValueError("config must not be null.")
                project.config = copy.deepcopy(value)

        session.flush()
        counts = _page_count_map(session, project_ids=[project.id])
        return _present_project(project, page_count=counts.get(project.id, 0))


def delete_project(session: Session, *, session_token: str, project_id: str) -> str:
    normalized_project_id = _normalize_ulid(project_id, field_name="project_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        project = _load_project(session, user_id=context.user.id, project_id=normalized_project_id, for_update=True)
        session.delete(project)
    return normalized_project_id


def list_pages(session: Session, *, session_token: str, project_id: str) -> list[Page]:
    normalized_project_id = _normalize_ulid(project_id, field_name="project_id")
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    _load_project(session, user_id=context.user.id, project_id=normalized_project_id)
    return session.scalars(
        select(Page)
        .where(Page.project_id == normalized_project_id)
        .order_by(Page.index.asc()),
    ).all()


def create_page_snapshot(
    session: Session,
    *,
    session_token: str,
    write: PageSnapshotWrite,
) -> Page:
    normalized_page_id = _normalize_ulid(write.page_id, field_name="page.id")
    normalized_project_id = _normalize_ulid(write.project_id, field_name="page.project_id")

    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        project = _load_project(
            session,
            user_id=context.user.id,
            project_id=normalized_project_id,
            for_update=True,
        )
        if session.get(Page, normalized_page_id) is not None:
            raise PageConflictError(
                f"Page {normalized_page_id} already exists.",
                reason="duplicate_page_id",
            )
        next_index = (
            session.scalar(
                select(func.coalesce(func.max(Page.index), 0) + 1).where(Page.project_id == project.id),
            )
            or 1
        )
        if write.index != next_index:
            raise PageConflictError(
                f"Page index {write.index} must be the next append-only index {next_index}.",
                reason="append_only_index_mismatch",
            )

        now = utcnow()
        project.updated_at = now
        page = Page(
            id=normalized_page_id,
            project_id=project.id,
            index=write.index,
            status=write.status,
        )
        snapshot = PageSnapshot(
            page=page,
            metadata_json=_canonical_metadata(
                PageSnapshotWrite(
                    page_id=normalized_page_id,
                    project_id=project.id,
                    index=write.index,
                    status=write.status,
                    metadata=write.metadata,
                    original_image=write.original_image,
                    layer_blob=write.layer_blob,
                    thumbnail=write.thumbnail,
                ),
            ),
            original_image_bytes=write.original_image.content,
            original_image_media_type=write.original_image.media_type,
            original_image_byte_size=write.original_image.byte_size,
            layer_blob_bytes=write.layer_blob.content,
            layer_blob_media_type=write.layer_blob.media_type,
            layer_blob_byte_size=write.layer_blob.byte_size,
            thumbnail_bytes=write.thumbnail.content,
            thumbnail_media_type=write.thumbnail.media_type,
            thumbnail_byte_size=write.thumbnail.byte_size,
        )
        session.add_all([page, snapshot])
        session.flush()
        return page


def get_page_snapshot(session: Session, *, session_token: str, page_id: str) -> StoredPageSnapshot:
    normalized_page_id = _normalize_ulid(page_id, field_name="page_id")
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    page = _load_page(
        session,
        user_id=context.user.id,
        page_id=normalized_page_id,
        include_snapshot=True,
    )
    snapshot = page.snapshot
    if snapshot is None:
        raise PageConflictError(
            f"Page {normalized_page_id} is missing its snapshot.",
            reason="snapshot_missing",
        )
    return _snapshot_from_model(snapshot)


def update_page_snapshot(
    session: Session,
    *,
    session_token: str,
    page_id: str,
    write: PageSnapshotWrite,
) -> Page:
    normalized_page_id = _normalize_ulid(page_id, field_name="page_id")

    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        page = _load_page(
            session,
            user_id=context.user.id,
            page_id=normalized_page_id,
            for_update=True,
            include_snapshot=True,
        )
        if write.page_id.strip().upper() != page.id:
            raise PageConflictError(
                f"Page snapshot metadata id {write.page_id} does not match page {page.id}.",
                reason="page_identity_mismatch",
            )
        if write.project_id.strip().upper() != page.project_id:
            raise PageConflictError(
                f"Page snapshot metadata project_id {write.project_id} does not match project {page.project_id}.",
                reason="project_identity_mismatch",
            )
        if write.index != page.index:
            raise PageConflictError(
                f"Page snapshot metadata index {write.index} does not match page index {page.index}.",
                reason="page_index_mismatch",
            )
        snapshot = page.snapshot
        if snapshot is None:
            raise PageConflictError(
                f"Page {page.id} is missing its snapshot.",
                reason="snapshot_missing",
            )

        now = utcnow()
        page.status = write.status
        page.updated_at = now
        page.project.updated_at = now

        canonical_write = PageSnapshotWrite(
            page_id=page.id,
            project_id=page.project_id,
            index=page.index,
            status=write.status,
            metadata=write.metadata,
            original_image=write.original_image,
            layer_blob=write.layer_blob,
            thumbnail=write.thumbnail,
        )
        snapshot.metadata_json = _canonical_metadata(canonical_write)
        snapshot.original_image_bytes = write.original_image.content
        snapshot.original_image_media_type = write.original_image.media_type
        snapshot.original_image_byte_size = write.original_image.byte_size
        snapshot.layer_blob_bytes = write.layer_blob.content
        snapshot.layer_blob_media_type = write.layer_blob.media_type
        snapshot.layer_blob_byte_size = write.layer_blob.byte_size
        snapshot.thumbnail_bytes = write.thumbnail.content
        snapshot.thumbnail_media_type = write.thumbnail.media_type
        snapshot.thumbnail_byte_size = write.thumbnail.byte_size
        session.flush()
        return page


def delete_page(session: Session, *, session_token: str, page_id: str) -> str:
    normalized_page_id = _normalize_ulid(page_id, field_name="page_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        page = _load_page(
            session,
            user_id=context.user.id,
            page_id=normalized_page_id,
            for_update=True,
            include_snapshot=True,
        )
        deleted_index = page.index
        project = page.project
        project.updated_at = utcnow()
        session.delete(page)
        session.flush()
        session.execute(
            update(Page)
            .where(
                Page.project_id == project.id,
                Page.index > deleted_index,
            )
            .values(index=Page.index - 1),
        )
    return normalized_page_id


def get_page_thumbnail(session: Session, *, session_token: str, page_id: str) -> BinaryPayload:
    normalized_page_id = _normalize_ulid(page_id, field_name="page_id")
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    page = _load_page(
        session,
        user_id=context.user.id,
        page_id=normalized_page_id,
        include_snapshot=True,
    )
    snapshot = page.snapshot
    if snapshot is None:
        raise PageConflictError(
            f"Page {normalized_page_id} is missing its snapshot.",
            reason="snapshot_missing",
        )
    return BinaryPayload(
        content=snapshot.thumbnail_bytes,
        media_type=snapshot.thumbnail_media_type,
    )
