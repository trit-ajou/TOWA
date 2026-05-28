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
    "folders",
    "projects",
    "pages",
    "page_snapshots",
}


def _service_engine_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    service_engine_dir = _service_engine_dir()
    alembic_config = Config(str(service_engine_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(service_engine_dir / "alembic"))
    return alembic_config


def _reset_public_schema(database_url: str) -> None:
    reset_engine = create_engine(database_url)
    try:
        with reset_engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        reset_engine.dispose()


@pytest.mark.postgres
def test_alembic_upgrade_head_creates_expected_schema(
    postgres_test_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not postgres_test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests.")

    monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    get_settings.cache_clear()

    _reset_public_schema(postgres_test_url)

    alembic_config = _alembic_config()
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
        assert {"thumbnail_url", "source_lang", "target_lang", "config", "folder_id", "deleted_at"}.issubset(project_columns)
        assert "folder" not in project_columns

        folder_columns = {column["name"] for column in inspector.get_columns("folders")}
        assert {"id", "user_id", "name", "parent_id", "deleted_at"}.issubset(folder_columns)

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


@pytest.mark.postgres
def test_folder_migration_converts_legacy_project_paths(
    postgres_test_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not postgres_test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests.")

    monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    get_settings.cache_clear()
    _reset_public_schema(postgres_test_url)

    alembic_config = _alembic_config()
    command.upgrade(alembic_config, "20260415_000002")
    engine = create_engine(postgres_test_url)
    try:
        user_id = str(uuid4())
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, nickname, status)
                    VALUES (:id, :email, 'tester', 'active')
                    """,
                ),
                {"id": user_id, "email": f"{user_id}@example.com"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO projects (
                        id, user_id, name, source_lang, target_lang, status, folder, config
                    ) VALUES
                        ('01ARZ3NDEKTSV4RRFFQ69G5FA1', :user_id, 'a', 'ja', 'ko', 'todo', '주간연재/점프', '{}'),
                        ('01ARZ3NDEKTSV4RRFFQ69G5FA2', :user_id, 'b', 'ja', 'ko', 'todo', '주간연재/점프', '{}'),
                        ('01ARZ3NDEKTSV4RRFFQ69G5FA3', :user_id, 'c', 'ja', 'ko', 'todo', '', '{}')
                    """,
                ),
                {"user_id": user_id},
            )

        command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            folders = connection.execute(
                text("SELECT id, name, parent_id FROM folders ORDER BY parent_id NULLS FIRST, name"),
            ).mappings().all()
            assert [folder["name"] for folder in folders] == ["주간연재", "점프"]
            jump_id = next(folder["id"] for folder in folders if folder["name"] == "점프")
            project_rows = connection.execute(
                text("SELECT id, folder_id FROM projects ORDER BY id"),
            ).mappings().all()
            assert project_rows[0]["folder_id"] == jump_id
            assert project_rows[1]["folder_id"] == jump_id
            assert project_rows[2]["folder_id"] is None
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_folder_migration_rejects_invalid_legacy_paths(
    postgres_test_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not postgres_test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration tests.")

    monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    get_settings.cache_clear()
    _reset_public_schema(postgres_test_url)

    alembic_config = _alembic_config()
    command.upgrade(alembic_config, "20260415_000002")
    engine = create_engine(postgres_test_url)
    try:
        user_id = str(uuid4())
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, nickname, status)
                    VALUES (:id, :email, 'tester', 'active')
                    """,
                ),
                {"id": user_id, "email": f"{user_id}@example.com"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO projects (
                        id, user_id, name, source_lang, target_lang, status, folder, config
                    ) VALUES (
                        '01ARZ3NDEKTSV4RRFFQ69G5FA4', :user_id, 'bad', 'ja', 'ko', 'todo', 'bad//path', '{}'
                    )
                    """,
                ),
                {"user_id": user_id},
            )

        with pytest.raises(ValueError, match="empty folder path segment"):
            command.upgrade(alembic_config, "head")
    finally:
        engine.dispose()
