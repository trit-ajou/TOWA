from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

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

