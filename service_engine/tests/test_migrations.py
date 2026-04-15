from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.settings import get_settings

INITIAL_REVISION = "20260325_000001"
BASE_TABLES = {
    "users",
    "auth_sessions",
    "credit_accounts",
    "usage_jobs",
    "credit_holds",
    "credit_ledger",
}
STORAGE_TABLES = {
    "projects",
    "pages",
    "page_snapshots",
}


@pytest.mark.postgres
def test_alembic_upgrade_head_creates_expected_schema(
    postgres_test_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not postgres_test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests.")

    monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    get_settings.cache_clear()

    reset_engine = create_engine(postgres_test_url)
    try:
        with reset_engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        reset_engine.dispose()

    service_engine_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(service_engine_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(service_engine_dir / "alembic"))
    command.upgrade(alembic_config, INITIAL_REVISION)

    engine = create_engine(postgres_test_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert BASE_TABLES.issubset(table_names)
        assert STORAGE_TABLES.isdisjoint(table_names)

        command.upgrade(alembic_config, "head")

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert BASE_TABLES.union(STORAGE_TABLES).issubset(table_names)

        usage_columns = {column["name"] for column in inspector.get_columns("usage_jobs")}
        assert {"operation_kind", "request_ref", "estimated_units"}.issubset(usage_columns)

        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        assert {"thumbnail_url", "source_lang", "target_lang", "config"}.issubset(project_columns)

        page_columns = {column["name"] for column in inspector.get_columns("pages")}
        assert {"project_id", "index", "status"}.issubset(page_columns)

        snapshot_columns = {column["name"] for column in inspector.get_columns("page_snapshots")}
        assert {"metadata_json", "original_image_bytes", "layer_blob_bytes", "thumbnail_bytes"}.issubset(snapshot_columns)

        user_id = str(uuid4())
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, nickname, status)
                    VALUES (:id, :email, :nickname, 'active')
                    """,
                ),
                {
                    "id": user_id,
                    "email": f"{user_id}@example.com",
                    "nickname": "tester",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO credit_accounts (
                        id, user_id, balance_units, reserved_units, version
                    ) VALUES (
                        :id, :user_id, 1000, 0, 1
                    )
                    """,
                ),
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                },
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO credit_accounts (
                            id, user_id, balance_units, reserved_units, version
                        ) VALUES (
                            :id, :user_id, 1000, 0, 1
                        )
                        """,
                    ),
                    {
                        "id": str(uuid4()),
                        "user_id": user_id,
                    },
                )
    finally:
        engine.dispose()
