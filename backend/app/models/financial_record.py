"""Financial record model.

One record holds the standardised financial statement values required by the
ten indicators, for one reporting period. Records are versioned: a correction
creates a new revision rather than overwriting history.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
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
        # At most one current revision per period, enforced by the database
        # so two simultaneous corrections cannot both become current.
        Index(
            "uq_record_one_current_per_period",
            "reporting_period_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # How the figures were obtained: "statement" when the totals were typed in
    # from finished statements, "trial_balance" when they were calculated from
    # the account balances stored in trial_balance_lines.
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="statement", server_default="statement"
    )

    # ---- Income statement ------------------------------------------------
    revenue: Mapped[float] = mapped_column(Money, nullable=False)
    cost_of_goods_sold: Mapped[float] = mapped_column(Money, nullable=False)
    operating_expenses: Mapped[float] = mapped_column(Money, nullable=False)
    interest_expense: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    tax_expense: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    net_profit: Mapped[float] = mapped_column(Money, nullable=False)
    # The precision the source figures were rounded to: 0.01 (exact, the
    # default), 1, 1000 (RM'000) or 1000000 (RM million). It sets the
    # tolerance of the reconciliation checks; see validation_service.
    presentation_unit: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.01, server_default="0.01"
    )
    # Lines between operating profit and net profit (see FinancialInputs).
    other_operating_income: Mapped[float] = mapped_column(
        Money, nullable=False, default=0, server_default="0"
    )
    other_income: Mapped[float] = mapped_column(
        Money, nullable=False, default=0, server_default="0"
    )
    other_expenses: Mapped[float] = mapped_column(
        Money, nullable=False, default=0, server_default="0"
    )

    # ---- Balance sheet ---------------------------------------------------
    cash_and_equivalents: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    accounts_receivable: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    inventory: Mapped[float | None] = mapped_column(Money)
    current_assets: Mapped[float] = mapped_column(Money, nullable=False)
    total_assets: Mapped[float] = mapped_column(Money, nullable=False)
    current_liabilities: Mapped[float] = mapped_column(Money, nullable=False)
    total_liabilities: Mapped[float] = mapped_column(Money, nullable=False)
    total_equity: Mapped[float] = mapped_column(Money, nullable=False)
    # Used only by the Altman Z'' benchmark. Null means not reported; it is
    # never treated as zero.
    retained_earnings: Mapped[float | None] = mapped_column(Money)

    # ---- Validation outcome ---------------------------------------------
    # Set when the accounting identity does not hold within tolerance. The
    # record is stored and flagged rather than silently accepted.
    accounting_identity_ok: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    validation_notes: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # The signed-in user who entered this revision (empty for records made
    # before this was recorded).
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by: Mapped["User | None"] = relationship()  # noqa: F821

    @property
    def created_by_email(self) -> str | None:
        return self.created_by.email if self.created_by else None

    reporting_period: Mapped["ReportingPeriod"] = relationship(  # noqa: F821
        back_populates="financial_records"
    )
    trial_balance_lines: Mapped[list["TrialBalanceLine"]] = relationship(  # noqa: F821
        back_populates="financial_record",
        cascade="all, delete-orphan",
        order_by="TrialBalanceLine.line_number",
    )
