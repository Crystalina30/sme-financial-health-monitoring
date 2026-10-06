"""Financial record model.

One record holds the standardised financial statement values required by the
ten indicators, for one reporting period. Records are versioned: a correction
creates a new revision rather than overwriting history.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Monetary values: 18 digits with 2 decimal places.
Money = Numeric(18, 2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FinancialRecord(Base):
    """Standardised financial statement values for one reporting period."""

    __tablename__ = "financial_records"
    __table_args__ = (
        UniqueConstraint(
            "reporting_period_id", "revision", name="uq_record_period_revision"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- Income statement ------------------------------------------------
    revenue: Mapped[float] = mapped_column(Money, nullable=False)
    cost_of_goods_sold: Mapped[float] = mapped_column(Money, nullable=False)
    operating_expenses: Mapped[float] = mapped_column(Money, nullable=False)
    interest_expense: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    tax_expense: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    net_profit: Mapped[float] = mapped_column(Money, nullable=False)

    # ---- Balance sheet ---------------------------------------------------
    cash_and_equivalents: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    accounts_receivable: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    inventory: Mapped[float | None] = mapped_column(Money)
    current_assets: Mapped[float] = mapped_column(Money, nullable=False)
    total_assets: Mapped[float] = mapped_column(Money, nullable=False)
    current_liabilities: Mapped[float] = mapped_column(Money, nullable=False)
    total_liabilities: Mapped[float] = mapped_column(Money, nullable=False)
    total_equity: Mapped[float] = mapped_column(Money, nullable=False)

    # ---- Validation outcome ---------------------------------------------
    # Set when the accounting identity does not hold within tolerance. The
    # record is stored and flagged rather than silently accepted.
    accounting_identity_ok: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    validation_notes: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    reporting_period: Mapped["ReportingPeriod"] = relationship(  # noqa: F821
        back_populates="financial_records"
    )
