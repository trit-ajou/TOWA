from collections.abc import Iterable
from enum import Enum as PyEnum
from typing import Any, TypeVar

from sqlalchemy import JSON, Enum
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.type_api import TypeEngine

_EnumT = TypeVar("_EnumT", bound=PyEnum)


def json_type() -> TypeEngine[Any]:
    return postgresql.JSONB().with_variant(JSON(), "sqlite")


def enum_type(enum_cls: type[_EnumT], *, name: str) -> TypeEngine[Any]:
    return Enum(
        enum_cls,
        name=name,
        values_callable=_enum_values,
        validate_strings=True,
        native_enum=False,
    )


def _enum_values(enum_cls: type[_EnumT]) -> list[str]:
    values: Iterable[str] = (item.value for item in enum_cls)
    return list(values)
