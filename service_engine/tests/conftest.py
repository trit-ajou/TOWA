from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.modules  # noqa: F401
from app.core.settings import get_settings
from app.db.base import Base
from app.db.session import make_engine, make_session_factory


@pytest.fixture(autouse=True)
def clear_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sqlite_session_factory(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    try:
        yield session_factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def postgres_test_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL")


@pytest.fixture
def postgres_session_factory(
    postgres_test_url: str | None,
    monkeypatch: pytest.MonkeyPatch,
):
    if not postgres_test_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL tests.")

    monkeypatch.setenv("DATABASE_URL", postgres_test_url)
    get_settings.cache_clear()

    engine = make_engine(postgres_test_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        Base.metadata.create_all(engine)
        session_factory = make_session_factory(engine)
        yield session_factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
