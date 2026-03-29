from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings


def _engine_kwargs(database_url: str, echo: bool) -> dict[str, Any]:
    if database_url.startswith("sqlite"):
        return {
            "echo": echo,
            "connect_args": {"check_same_thread": False},
        }

    return {
        "echo": echo,
        "pool_pre_ping": True,
    }


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(database_url, **_engine_kwargs(database_url, echo))


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


settings = get_settings()
engine = make_engine(settings.database_url, echo=settings.database_echo)
SessionLocal = make_session_factory(engine)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

