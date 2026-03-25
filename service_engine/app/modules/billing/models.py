from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import CreditHoldStatus, CreditLedgerEntryType, UsageJobStatus, UsageOperationKind
from app.db.mixins import CreatedAtMixin, TimestampMixin
from app.db.types import enum_type, json_type

if TYPE_CHECKING:
    from app.modules.auth.models import User


class CreditAccount(TimestampMixin, Base):
    __tablename__ = "credit_accounts"
    __table_args__ = (
        CheckConstraint("balance_units >= 0", name="ck_credit_accounts_balance_non_negative"),
        CheckConstraint("reserved_units >= 0", name="ck_credit_accounts_reserved_non_negative"),
        CheckConstraint("version >= 1", name="ck_credit_accounts_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    balance_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    reserved_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda current_version: 1 if current_version is None else current_version + 1,
    }

    user: Mapped["User"] = relationship(back_populates="credit_account")


class UsageJob(TimestampMixin, Base):
    __tablename__ = "usage_jobs"
    __table_args__ = (
        CheckConstraint("estimated_units > 0", name="ck_usage_jobs_estimated_units_positive"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_usage_jobs_user_id_idempotency_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_kind: Mapped[UsageOperationKind] = mapped_column(
        enum_type(UsageOperationKind, name="usage_operation_kind"),
        nullable=False,
    )
    status: Mapped[UsageJobStatus] = mapped_column(
        enum_type(UsageJobStatus, name="usage_job_status"),
        nullable=False,
        default=UsageJobStatus.AUTHORIZED,
        server_default=UsageJobStatus.AUTHORIZED.value,
    )
    estimated_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="usage_jobs")
    credit_hold: Mapped["CreditHold | None"] = relationship(
        back_populates="usage_job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    credit_entries: Mapped[list["CreditLedger"]] = relationship(back_populates="usage_job")


class CreditHold(TimestampMixin, Base):
    __tablename__ = "credit_holds"
    __table_args__ = (
        CheckConstraint("estimated_units > 0", name="ck_credit_holds_estimated_units_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("usage_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    estimated_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[CreditHoldStatus] = mapped_column(
        enum_type(CreditHoldStatus, name="credit_hold_status"),
        nullable=False,
        default=CreditHoldStatus.HELD,
        server_default=CreditHoldStatus.HELD.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    usage_job: Mapped["UsageJob"] = relationship(back_populates="credit_hold")
    credit_entries: Mapped[list["CreditLedger"]] = relationship(back_populates="credit_hold")


class CreditLedger(CreatedAtMixin, Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        CheckConstraint("delta_units <> 0", name="ck_credit_ledger_delta_units_non_zero"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_type: Mapped[CreditLedgerEntryType] = mapped_column(
        enum_type(CreditLedgerEntryType, name="credit_ledger_entry_type"),
        nullable=False,
    )
    delta_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    usage_job_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usage_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    credit_hold_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("credit_holds.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        json_type(),
        nullable=False,
        default=dict,
    )

    user: Mapped["User"] = relationship(back_populates="credit_entries")
    usage_job: Mapped["UsageJob | None"] = relationship(back_populates="credit_entries")
    credit_hold: Mapped["CreditHold | None"] = relationship(back_populates="credit_entries")

