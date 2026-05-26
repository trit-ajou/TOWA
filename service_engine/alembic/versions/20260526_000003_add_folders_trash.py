"""add folders and trash state

Revision ID: 20260526_000003
Revises: 20260415_000002
Create Date: 2026-05-26 00:00:03
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import re
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_000003"
down_revision: str | None = "20260415_000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _legacy_folder_segments(project_id: str, value: str | None) -> list[str]:
    if value is None or value == "":
        return []
    if value != value.strip():
        raise ValueError(f"Project {project_id} has a folder path with leading or trailing whitespace.")
    segments = value.split("/")
    for segment in segments:
        if not segment:
            raise ValueError(f"Project {project_id} has an empty folder path segment.")
        if segment != segment.strip():
            raise ValueError(f"Project {project_id} has a folder segment with leading or trailing whitespace.")
        if len(segment) > 100:
            raise ValueError(f"Project {project_id} has a folder segment longer than 100 characters.")
        if "\\" in segment or _CONTROL_RE.search(segment):
            raise ValueError(f"Project {project_id} has a folder segment containing a forbidden character.")
    return segments


def _migrate_legacy_project_folders() -> None:
    connection = op.get_bind()
    folder_cache: dict[tuple[str, str | None, str], str] = {}
    now = datetime.now(UTC)

    rows = connection.execute(
        sa.text("SELECT id, user_id, folder FROM projects ORDER BY user_id, folder, id"),
    ).mappings()
    for row in rows:
        project_id = row["id"]
        user_id = row["user_id"]
        parent_id: str | None = None
        for segment in _legacy_folder_segments(project_id, row["folder"]):
            cache_key = (str(user_id), parent_id, segment)
            folder_id = folder_cache.get(cache_key)
            if folder_id is None:
                folder_id = str(uuid4())
                folder_cache[cache_key] = folder_id
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO folders (
                            id, user_id, name, parent_id, created_at, updated_at, deleted_at
                        ) VALUES (
                            :id, :user_id, :name, :parent_id, :created_at, :updated_at, NULL
                        )
                        """,
                    ),
                    {
                        "id": folder_id,
                        "user_id": user_id,
                        "name": segment,
                        "parent_id": parent_id,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            parent_id = folder_id
        if parent_id is not None:
            connection.execute(
                sa.text("UPDATE projects SET folder_id = :folder_id WHERE id = :project_id"),
                {"folder_id": parent_id, "project_id": project_id},
            )


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["parent_id"], ["folders.id"], name=op.f("fk_folders_parent_id_folders"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_folders_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_folders")),
    )
    op.create_index(op.f("ix_folders_deleted_at"), "folders", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_folders_parent_id"), "folders", ["parent_id"], unique=False)
    op.create_index(op.f("ix_folders_user_id"), "folders", ["user_id"], unique=False)
    op.create_index(
        "uq_folders_user_id_root_name_live",
        "folders",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND deleted_at IS NULL"),
        sqlite_where=sa.text("parent_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_folders_user_id_parent_id_name_live",
        "folders",
        ["user_id", "parent_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL AND deleted_at IS NULL"),
        sqlite_where=sa.text("parent_id IS NOT NULL AND deleted_at IS NULL"),
    )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("folder_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(op.f("ix_projects_deleted_at"), ["deleted_at"], unique=False)
        batch_op.create_index(op.f("ix_projects_folder_id"), ["folder_id"], unique=False)
        batch_op.create_foreign_key(
            op.f("fk_projects_folder_id_folders"),
            "folders",
            ["folder_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _migrate_legacy_project_folders()
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("folder")


def _folder_paths() -> dict[str, str]:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, parent_id, name FROM folders")).mappings().all()
    by_id = {str(row["id"]): row for row in rows}
    path_cache: dict[str, str] = {}

    def build_path(folder_id: str) -> str:
        cached = path_cache.get(folder_id)
        if cached is not None:
            return cached
        row = by_id[folder_id]
        parent_id = row["parent_id"]
        if parent_id is None:
            path = row["name"]
        else:
            path = f"{build_path(str(parent_id))}/{row['name']}"
        path_cache[folder_id] = path
        return path

    return {folder_id: build_path(folder_id) for folder_id in by_id}


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("folder", sa.String(length=512), nullable=False, server_default=""))

    connection = op.get_bind()
    folder_paths = _folder_paths()
    rows = connection.execute(sa.text("SELECT id, folder_id FROM projects WHERE folder_id IS NOT NULL")).mappings()
    for row in rows:
        connection.execute(
            sa.text("UPDATE projects SET folder = :folder WHERE id = :project_id"),
            {
                "folder": folder_paths[str(row["folder_id"])],
                "project_id": row["id"],
            },
        )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint(op.f("fk_projects_folder_id_folders"), type_="foreignkey")
        batch_op.drop_index(op.f("ix_projects_folder_id"))
        batch_op.drop_index(op.f("ix_projects_deleted_at"))
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("folder_id")

    op.drop_index("uq_folders_user_id_parent_id_name_live", table_name="folders")
    op.drop_index("uq_folders_user_id_root_name_live", table_name="folders")
    op.drop_index(op.f("ix_folders_user_id"), table_name="folders")
    op.drop_index(op.f("ix_folders_parent_id"), table_name="folders")
    op.drop_index(op.f("ix_folders_deleted_at"), table_name="folders")
    op.drop_table("folders")
