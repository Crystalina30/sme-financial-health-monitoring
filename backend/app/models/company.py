"""Company (SME) and reporting period models."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    """An SME: the organisation an account belongs to.

    Each account has one organisation. ``is_primary`` marks it, and a partial
    unique index allows at most one primary company per owner, so the rule is
    enforced by the database and not only by the API. Companies that are not
    primary are kept (never deleted) but cannot be opened through the API;
    they exist only for accounts that held several companies before the
    single-organisation change, until the owner chooses one.
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "uq_companies_one_organisation_per_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(120))
    currency_code: Mapped[str] = mapped_column(String(3), default="MYR", nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped["User"] = relationship(back_populates="companies")  # noqa: F821
    reporting_periods: Mapped[list["ReportingPeriod"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="ReportingPeriod.period_end",
    )


class ReportingPeriod(Base):
    """A financial reporting period for one company.

    A company may not have two periods with the same label, which is how
    duplicate reporting periods are prevented at the database level.
    """

    __tablename__ = "reporting_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "label", name="uq_period_company_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    company: Mapped["Company"] = relationship(back_populates="reporting_periods")
    financial_records: Mapped[list["FinancialRecord"]] = relationship(  # noqa: F821
        back_populates="reporting_period", cascade="all, delete-orphan"
    )
