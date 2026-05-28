from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.modules.auth import service as auth_service
from app.modules.projects.models import Folder, Page, Project

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class FolderStorageError(RuntimeError):
    pass


class FolderNotFoundError(FolderStorageError):
    pass


class FolderConflictError(FolderStorageError):
    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class ProjectBadRequestError(FolderStorageError):
    pass


def normalize_uuid(value: str | UUID, *, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a canonical UUID.") from exc


def normalize_optional_uuid(value: str | UUID | None, *, field_name: str) -> UUID | None:
    if value is None:
        return None
    return normalize_uuid(value, field_name=field_name)


def normalize_folder_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("folder name must not be blank.")
    if len(normalized) > 100:
        raise ValueError("folder name must be at most 100 characters.")
    if "/" in normalized or "\\" in normalized or _CONTROL_RE.search(normalized):
        raise ValueError("folder name contains a forbidden character.")
    return normalized


def folder_path(folder: Folder | None) -> str | None:
    if folder is None:
        return None
    names: list[str] = []
    seen: set[UUID] = set()
    current: Folder | None = folder
    while current is not None:
        if current.id in seen:
            raise ProjectBadRequestError("Folder cycle detected while building a path.")
        seen.add(current.id)
        names.append(current.name)
        current = current.parent
    return "/".join(reversed(names))


def present_folder(folder: Folder) -> dict[str, Any]:
    return {
        "id": str(folder.id),
        "name": folder.name,
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "path": folder_path(folder),
        "created_at": folder.created_at,
        "updated_at": folder.updated_at,
        "deleted_at": folder.deleted_at,
    }


def present_project(project: Project, *, page_count: int) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "thumbnail_url": project.thumbnail_url,
        "source_lang": project.source_lang,
        "target_lang": project.target_lang,
        "page_count": page_count,
        "status": project.status,
        "folder_id": str(project.folder_id) if project.folder_id else None,
        "folder_path": folder_path(project.folder),
        "config": copy.deepcopy(project.config),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "deleted_at": project.deleted_at,
    }


def _folder_query_for_user(user_id: UUID, *, include_deleted: bool = False) -> Select[tuple[Folder]]:
    statement = select(Folder).where(Folder.user_id == user_id)
    if not include_deleted:
        statement = statement.where(Folder.deleted_at.is_(None))
    return statement


def load_folder(
    session: Session,
    *,
    user_id: UUID,
    folder_id: str | UUID,
    include_deleted: bool = False,
    for_update: bool = False,
) -> Folder:
    normalized_folder_id = normalize_uuid(folder_id, field_name="folder_id")
    statement = _folder_query_for_user(user_id, include_deleted=include_deleted).where(Folder.id == normalized_folder_id)
    if for_update:
        statement = statement.with_for_update()
    folder = session.scalar(statement)
    if folder is None:
        raise FolderNotFoundError(f"Folder {normalized_folder_id} was not found.")
    return folder


def load_optional_parent(session: Session, *, user_id: UUID, parent_id: str | UUID | None) -> Folder | None:
    normalized_parent_id = normalize_optional_uuid(parent_id, field_name="parent_id")
    if normalized_parent_id is None:
        return None
    return load_folder(session, user_id=user_id, folder_id=normalized_parent_id)


def _live_sibling_conflict_exists(
    session: Session,
    *,
    user_id: UUID,
    parent_id: UUID | None,
    name: str,
    exclude_ids: set[UUID] | None = None,
) -> bool:
    statement = select(Folder.id).where(
        Folder.user_id == user_id,
        Folder.name == name,
        Folder.deleted_at.is_(None),
    )
    if parent_id is None:
        statement = statement.where(Folder.parent_id.is_(None))
    else:
        statement = statement.where(Folder.parent_id == parent_id)
    if exclude_ids:
        statement = statement.where(Folder.id.not_in(exclude_ids))
    return session.scalar(statement.limit(1)) is not None


def _assert_unique_live_sibling(
    session: Session,
    *,
    user_id: UUID,
    parent_id: UUID | None,
    name: str,
    exclude_ids: set[UUID] | None = None,
) -> None:
    if _live_sibling_conflict_exists(
        session,
        user_id=user_id,
        parent_id=parent_id,
        name=name,
        exclude_ids=exclude_ids,
    ):
        raise FolderConflictError(
            f"Folder name {name!r} already exists under the same parent.",
            reason="duplicate_folder_name",
        )


def _assert_not_descendant(folder: Folder, parent: Folder | None) -> None:
    current = parent
    while current is not None:
        if current.id == folder.id:
            raise ProjectBadRequestError("folder cannot be moved under itself or its descendant.")
        current = current.parent


def _live_child_folders(session: Session, *, user_id: UUID, folder_id: UUID) -> list[Folder]:
    return list(
        session.scalars(
            select(Folder).where(
                Folder.user_id == user_id,
                Folder.parent_id == folder_id,
                Folder.deleted_at.is_(None),
            ),
        ).all(),
    )


def _live_projects_in_folder(session: Session, *, user_id: UUID, folder_id: UUID) -> list[Project]:
    return list(
        session.scalars(
            select(Project).where(
                Project.user_id == user_id,
                Project.folder_id == folder_id,
                Project.deleted_at.is_(None),
            ),
        ).all(),
    )


def _folder_subtree(session: Session, *, user_id: UUID, root_id: UUID, include_deleted: bool) -> list[Folder]:
    folders = list(session.scalars(_folder_query_for_user(user_id, include_deleted=include_deleted)).all())
    by_parent: dict[UUID | None, list[Folder]] = {}
    by_id = {folder.id: folder for folder in folders}
    for folder in folders:
        by_parent.setdefault(folder.parent_id, []).append(folder)

    root = by_id.get(root_id)
    if root is None:
        return []

    ordered: list[Folder] = []

    def visit(folder: Folder) -> None:
        ordered.append(folder)
        for child in by_parent.get(folder.id, []):
            visit(child)

    visit(root)
    return ordered


def _projects_in_folder_ids(
    session: Session,
    *,
    user_id: UUID,
    folder_ids: set[UUID],
    include_deleted: bool,
) -> list[Project]:
    if not folder_ids:
        return []
    statement = select(Project).where(
        Project.user_id == user_id,
        Project.folder_id.in_(folder_ids),
    )
    if not include_deleted:
        statement = statement.where(Project.deleted_at.is_(None))
    return list(session.scalars(statement).all())


def _page_count_map(session: Session, *, project_ids: list[str]) -> dict[str, int]:
    if not project_ids:
        return {}
    rows = session.execute(
        select(Page.project_id, func.count(Page.id))
        .where(Page.project_id.in_(project_ids))
        .group_by(Page.project_id),
    ).all()
    return {project_id: page_count for project_id, page_count in rows}


def create_folder(
    session: Session,
    *,
    session_token: str,
    name: str,
    parent_id: str | None,
) -> dict[str, Any]:
    normalized_name = normalize_folder_name(name)
    normalized_parent_id = normalize_optional_uuid(parent_id, field_name="parent_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        parent = load_optional_parent(session, user_id=context.user.id, parent_id=normalized_parent_id)
        _assert_unique_live_sibling(
            session,
            user_id=context.user.id,
            parent_id=parent.id if parent else None,
            name=normalized_name,
        )
        folder = Folder(user_id=context.user.id, name=normalized_name, parent_id=parent.id if parent else None)
        session.add(folder)
        session.flush()
        return present_folder(folder)


def list_folders(session: Session, *, session_token: str, search: str | None = None) -> list[dict[str, Any]]:
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    statement = _folder_query_for_user(context.user.id)
    normalized_search = search.strip() if search else ""
    if normalized_search:
        statement = statement.where(Folder.name.ilike(f"%{normalized_search}%"))
    folders = session.scalars(statement.order_by(Folder.name.asc(), Folder.created_at.asc())).all()
    return [present_folder(folder) for folder in folders]


def update_folder(
    session: Session,
    *,
    session_token: str,
    folder_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    normalized_folder_id = normalize_uuid(folder_id, field_name="folder_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        folder = load_folder(session, user_id=context.user.id, folder_id=normalized_folder_id, for_update=True)

        next_name = folder.name
        if "name" in updates:
            next_name = normalize_folder_name(updates["name"])

        next_parent_id = folder.parent_id
        if "parent_id" in updates:
            parent = load_optional_parent(session, user_id=context.user.id, parent_id=updates["parent_id"])
            _assert_not_descendant(folder, parent)
            next_parent_id = parent.id if parent else None

        _assert_unique_live_sibling(
            session,
            user_id=context.user.id,
            parent_id=next_parent_id,
            name=next_name,
            exclude_ids={folder.id},
        )

        folder.name = next_name
        folder.parent_id = next_parent_id
        session.flush()
        return present_folder(folder)


def _assert_single_delete_mode(*, cascade: str | None, reparent: bool, permanent: bool) -> None:
    mode_count = sum([cascade is not None, reparent, permanent])
    if mode_count > 1:
        raise ProjectBadRequestError("cascade, reparent, and permanent delete modes are mutually exclusive.")
    if cascade is not None and cascade != "trash":
        raise ProjectBadRequestError("cascade must be 'trash' when provided.")


def delete_folder(
    session: Session,
    *,
    session_token: str,
    folder_id: str,
    cascade: str | None = None,
    reparent: bool = False,
    permanent: bool = False,
) -> dict[str, Any] | str:
    _assert_single_delete_mode(cascade=cascade, reparent=reparent, permanent=permanent)
    normalized_folder_id = normalize_uuid(folder_id, field_name="folder_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        if permanent:
            folder = load_folder(
                session,
                user_id=context.user.id,
                folder_id=normalized_folder_id,
                include_deleted=True,
                for_update=True,
            )
            if folder.deleted_at is None:
                raise ProjectBadRequestError("Only trashed folders can be permanently deleted.")
            subtree = _folder_subtree(session, user_id=context.user.id, root_id=folder.id, include_deleted=True)
            folder_ids = {item.id for item in subtree}
            for project in _projects_in_folder_ids(
                session,
                user_id=context.user.id,
                folder_ids=folder_ids,
                include_deleted=True,
            ):
                session.delete(project)
            for item in reversed(subtree):
                session.delete(item)
            return str(normalized_folder_id)

        folder = load_folder(session, user_id=context.user.id, folder_id=normalized_folder_id, for_update=True)
        now = utcnow()
        if cascade == "trash":
            subtree = _folder_subtree(session, user_id=context.user.id, root_id=folder.id, include_deleted=False)
            folder_ids = {item.id for item in subtree}
            for item in subtree:
                item.deleted_at = now
            for project in _projects_in_folder_ids(
                session,
                user_id=context.user.id,
                folder_ids=folder_ids,
                include_deleted=False,
            ):
                project.deleted_at = now
            session.flush()
            return present_folder(folder)

        child_folders = _live_child_folders(session, user_id=context.user.id, folder_id=folder.id)
        projects = _live_projects_in_folder(session, user_id=context.user.id, folder_id=folder.id)
        if reparent:
            target_parent_id = folder.parent_id
            for child in child_folders:
                _assert_unique_live_sibling(
                    session,
                    user_id=context.user.id,
                    parent_id=target_parent_id,
                    name=child.name,
                    exclude_ids={child.id, folder.id},
                )
            for child in child_folders:
                child.parent_id = target_parent_id
            for project in projects:
                project.folder_id = target_parent_id
            folder.deleted_at = now
            session.flush()
            return present_folder(folder)

        if child_folders or projects:
            raise FolderConflictError(
                f"Folder {normalized_folder_id} is not empty.",
                reason="folder_not_empty",
            )
        folder.deleted_at = now
        session.flush()
        return present_folder(folder)


def restore_folder(session: Session, *, session_token: str, folder_id: str) -> dict[str, Any]:
    normalized_folder_id = normalize_uuid(folder_id, field_name="folder_id")
    with session.begin():
        context = auth_service.authenticate_session_token(session, session_token=session_token)
        folder = load_folder(
            session,
            user_id=context.user.id,
            folder_id=normalized_folder_id,
            include_deleted=True,
            for_update=True,
        )
        if folder.deleted_at is None:
            raise ProjectBadRequestError("Only trashed folders can be restored.")

        subtree = _folder_subtree(session, user_id=context.user.id, root_id=folder.id, include_deleted=True)
        subtree_ids = {item.id for item in subtree}
        deleted_folder_ids = {item.id for item in subtree if item.deleted_at is not None}

        if folder.parent_id is not None:
            parent = session.get(Folder, folder.parent_id)
            if parent is None or parent.user_id != context.user.id or parent.deleted_at is not None:
                folder.parent_id = None

        for item in subtree:
            if item.id not in deleted_folder_ids:
                continue
            _assert_unique_live_sibling(
                session,
                user_id=context.user.id,
                parent_id=item.parent_id,
                name=item.name,
                exclude_ids=subtree_ids,
            )

        folder_ids = {item.id for item in subtree}
        for item in subtree:
            item.deleted_at = None
        for project in _projects_in_folder_ids(
            session,
            user_id=context.user.id,
            folder_ids=folder_ids,
            include_deleted=True,
        ):
            if project.deleted_at is not None:
                project.deleted_at = None
        session.flush()
        return present_folder(folder)


def list_trash(session: Session, *, session_token: str) -> list[dict[str, Any]]:
    context = auth_service.authenticate_session_token(session, session_token=session_token)
    folders = session.scalars(
        select(Folder)
        .where(Folder.user_id == context.user.id, Folder.deleted_at.is_not(None))
        .order_by(Folder.deleted_at.desc(), Folder.name.asc()),
    ).all()
    projects = session.scalars(
        select(Project)
        .where(Project.user_id == context.user.id, Project.deleted_at.is_not(None))
        .order_by(Project.deleted_at.desc(), Project.name.asc()),
    ).all()
    counts = _page_count_map(session, project_ids=[project.id for project in projects])
    items: list[dict[str, Any]] = [
        {"type": "folder", "item": present_folder(folder)}
        for folder in folders
    ]
    items.extend(
        {"type": "project", "item": present_project(project, page_count=counts.get(project.id, 0))}
        for project in projects
    )

    def deleted_at(item: dict[str, Any]) -> datetime:
        return item["item"]["deleted_at"] or datetime.min.replace(tzinfo=UTC)

    return sorted(items, key=deleted_at, reverse=True)
