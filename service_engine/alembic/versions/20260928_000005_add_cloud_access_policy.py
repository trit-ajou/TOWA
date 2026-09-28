"""add cloud access policy

Revision ID: 20260928_000005
Revises: 20260924_000004
Create Date: 2026-09-28 00:00:05
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260928_000005"
down_revision: str | None = "20260924_000004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cloud_access_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cloud_access_policy")),
    )
    # Nullable: no unlock recorded. With no policy password set, cloud stays open to all.
    op.add_column("users", sa.Column("cloud_access_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "cloud_access_version")
    op.drop_table("cloud_access_policy")
