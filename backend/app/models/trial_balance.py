"""Trial balance model.

A trial balance is the raw input an accountant exports from the ledger: one
row per account with its debit or credit balance. Each row is mapped to a
category, and the statement figures held on a financial record are calculated
from those rows. The rows are stored against the record revision they
produced, so every figure can be traced back to the accounts that make it up.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.financial_record import Money


class TrialBalanceLine(Base):
    """One account balance from a trial balance."""

    __tablename__ = "trial_balance_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    financial_record_id: Mapped[int] = mapped_column(
        ForeignKey("financial_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Position in the submitted trial balance, so the rows read back in order.
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_code: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    debit: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    credit: Mapped[float] = mapped_column(Money, nullable=False, default=0)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    # The group or account type given in the source export (for example
    # Tally's "Sundry Debtors"), kept as evidence for the category.
    account_group: Mapped[str] = mapped_column(
        String(120), nullable=False, default="", server_default=""
    )
    # Where the row came from: file, sheet and row number.
    source_ref: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )

    financial_record: Mapped["FinancialRecord"] = relationship(  # noqa: F821
        back_populates="trial_balance_lines"
    )
