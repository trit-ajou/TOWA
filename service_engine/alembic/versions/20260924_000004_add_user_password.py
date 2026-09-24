"""add user password hash

Revision ID: 20260924_000004
Revises: 20260526_000003
Create Date: 2026-09-24 00:00:04
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_000004"
down_revision: str | None = "20260526_000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: pre-existing users have no password and can only sign in after signup/reset.
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
