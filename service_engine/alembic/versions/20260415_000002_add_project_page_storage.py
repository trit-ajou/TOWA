"""add project and page storage

Revision ID: 20260415_000002
Revises: 20260325_000001
Create Date: 2026-04-15 00:00:02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_000002"
down_revision: str | None = "20260325_000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    project_status = sa.Enum(
        "todo",
        "in-progress",
        "done",
        name="project_status",
        native_enum=False,
    )
    page_status = sa.Enum(
        "waiting",
        "ai-processing",
        "in-progress",
        "done",
        name="page_status",
        native_enum=False,
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("source_lang", sa.String(length=32), nullable=False),
        sa.Column("target_lang", sa.String(length=32), nullable=False),
        sa.Column("status", project_status, nullable=False),
        sa.Column("folder", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_projects_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    op.create_table(
        "pages",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_id", sa.String(length=26), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("status", page_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint('"index" > 0', name="ck_pages_pages_index_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_pages_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
        sa.UniqueConstraint("project_id", "index", name="uq_pages_project_id_index"),
    )
    op.create_index(op.f("ix_pages_project_id"), "pages", ["project_id"], unique=False)

    op.create_table(
        "page_snapshots",
        sa.Column("page_id", sa.String(length=26), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("original_image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("original_image_media_type", sa.String(length=100), nullable=False),
        sa.Column("original_image_byte_size", sa.Integer(), nullable=False),
        sa.Column("layer_blob_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("layer_blob_media_type", sa.String(length=100), nullable=False),
        sa.Column("layer_blob_byte_size", sa.Integer(), nullable=False),
        sa.Column("thumbnail_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_media_type", sa.String(length=100), nullable=False),
        sa.Column("thumbnail_byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("original_image_byte_size > 0", name="ck_page_snapshots_page_snapshots_original_image_positive"),
        sa.CheckConstraint("layer_blob_byte_size > 0", name="ck_page_snapshots_page_snapshots_layer_blob_positive"),
        sa.CheckConstraint("thumbnail_byte_size > 0", name="ck_page_snapshots_page_snapshots_thumbnail_positive"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_page_snapshots_page_id_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("page_id", name=op.f("pk_page_snapshots")),
    )


def downgrade() -> None:
    op.drop_table("page_snapshots")
    op.drop_index(op.f("ix_pages_project_id"), table_name="pages")
    op.drop_table("pages")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
