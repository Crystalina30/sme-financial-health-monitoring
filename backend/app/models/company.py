"""Company (SME) and reporting period models."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    """An SME belonging to exactly one user."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(120))
    currency_code: Mapped[str] = mapped_column(String(3), default="MYR", nullable=False)
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
