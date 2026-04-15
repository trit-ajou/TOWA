"""initial service engine

Revision ID: 20260325_000001
Revises:
Create Date: 2026-03-25 00:00:01
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260325_000001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_status = sa.Enum("active", "disabled", name="user_status", native_enum=False)
    usage_operation_kind = sa.Enum(
        "mask",
        "translate",
        "inpaint",
        name="usage_operation_kind",
        native_enum=False,
    )
    usage_job_status = sa.Enum(
        "authorized",
        "succeeded",
        "failed",
        name="usage_job_status",
        native_enum=False,
    )
    credit_hold_status = sa.Enum(
        "held",
        "captured",
        "released",
        name="credit_hold_status",
        native_enum=False,
    )
    credit_ledger_entry_type = sa.Enum(
        "usage",
        "adjustment",
        name="credit_ledger_entry_type",
        native_enum=False,
    )
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
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=False),
        sa.Column("status", user_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_auth_sessions_session_token_hash")),
    )
    op.create_index(
        "ix_auth_sessions_user_id_revoked_at_expires_at",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
        unique=False,
    )

    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("balance_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("balance_units >= 0", name="ck_credit_accounts_balance_non_negative"),
        sa.CheckConstraint("reserved_units >= 0", name="ck_credit_accounts_reserved_non_negative"),
        sa.CheckConstraint("version >= 1", name="ck_credit_accounts_version_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_credit_accounts_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_accounts")),
        sa.UniqueConstraint("user_id", name=op.f("uq_credit_accounts_user_id")),
    )

    op.create_table(
        "usage_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation_kind", usage_operation_kind, nullable=False),
        sa.Column("status", usage_job_status, nullable=False, server_default="authorized"),
        sa.Column("estimated_units", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_ref", sa.String(length=255), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("estimated_units > 0", name="ck_usage_jobs_estimated_units_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_usage_jobs_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_jobs")),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_usage_jobs_user_id_idempotency_key"),
    )

    op.create_table(
        "credit_holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("usage_job_id", sa.Uuid(), nullable=False),
        sa.Column("estimated_units", sa.BigInteger(), nullable=False),
        sa.Column("status", credit_hold_status, nullable=False, server_default="held"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("estimated_units > 0", name="ck_credit_holds_estimated_units_positive"),
        sa.ForeignKeyConstraint(["usage_job_id"], ["usage_jobs.id"], name=op.f("fk_credit_holds_usage_job_id_usage_jobs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_credit_holds_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_holds")),
        sa.UniqueConstraint("usage_job_id", name=op.f("uq_credit_holds_usage_job_id")),
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", credit_ledger_entry_type, nullable=False),
        sa.Column("delta_units", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("usage_job_id", sa.Uuid(), nullable=True),
        sa.Column("credit_hold_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("delta_units <> 0", name="ck_credit_ledger_delta_units_non_zero"),
        sa.ForeignKeyConstraint(["credit_hold_id"], ["credit_holds.id"], name=op.f("fk_credit_ledger_credit_hold_id_credit_holds"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usage_job_id"], ["usage_jobs.id"], name=op.f("fk_credit_ledger_usage_job_id_usage_jobs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_credit_ledger_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ledger")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_credit_ledger_idempotency_key")),
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
    op.drop_table("credit_ledger")
    op.drop_table("credit_holds")
    op.drop_table("usage_jobs")
    op.drop_table("credit_accounts")
    op.drop_index("ix_auth_sessions_user_id_revoked_at_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
