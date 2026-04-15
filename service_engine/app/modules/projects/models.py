from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, LargeBinary, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import PageStatus, ProjectStatus
from app.db.mixins import TimestampMixin
from app.db.types import enum_type, json_type

if TYPE_CHECKING:
    from app.modules.auth.models import User


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_lang: Mapped[str] = mapped_column(String(32), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        enum_type(ProjectStatus, name="project_status"),
        nullable=False,
    )
    folder: Mapped[str] = mapped_column(String(512), nullable=False, default="", server_default="")
    config: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="projects")
    pages: Mapped[list["Page"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Page.index",
    )


class Page(TimestampMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (
        CheckConstraint('"index" > 0', name="pages_index_positive"),
        UniqueConstraint("project_id", "index", name="uq_pages_project_id_index"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PageStatus] = mapped_column(
        enum_type(PageStatus, name="page_status"),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="pages")
    snapshot: Mapped["PageSnapshot | None"] = relationship(
        back_populates="page",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PageSnapshot(TimestampMixin, Base):
    __tablename__ = "page_snapshots"
    __table_args__ = (
        CheckConstraint("original_image_byte_size > 0", name="page_snapshots_original_image_positive"),
        CheckConstraint("layer_blob_byte_size > 0", name="page_snapshots_layer_blob_positive"),
        CheckConstraint("thumbnail_byte_size > 0", name="page_snapshots_thumbnail_positive"),
    )

    page_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("pages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    original_image_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    original_image_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_image_byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_blob_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    layer_blob_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    layer_blob_byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    thumbnail_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    thumbnail_byte_size: Mapped[int] = mapped_column(Integer, nullable=False)

    page: Mapped["Page"] = relationship(back_populates="snapshot")
