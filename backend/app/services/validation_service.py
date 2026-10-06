"""Validation of submitted financial data.

Validation that can be expressed as a field rule lives in the Pydantic
schemas. This module holds the checks that span several fields — above all the
accounting identity — and returns findings rather than raising, so that a
record can be stored *and flagged* instead of being silently accepted or
silently discarded.
"""

from dataclasses import dataclass, field

from app.schemas.financial_inputs import FinancialInputs

#: The accounting identity is checked with a relative tolerance, since
#: statements are rounded to the nearest currency unit.
IDENTITY_RELATIVE_TOLERANCE = 0.01
IDENTITY_ABSOLUTE_TOLERANCE = 1.00


@dataclass
class ValidationResult:
    """Outcome of cross-field validation."""

    accounting_identity_ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when nothing blocks the record from being stored."""
        return not self.errors

    @property
    def notes(self) -> str | None:
        """Findings as a single string for storage against the record."""
        combined = self.errors + self.warnings
        return "; ".join(combined) if combined else None


def check_accounting_identity(data: FinancialInputs) -> tuple[bool, float]:
    """Check that total assets equal total liabilities plus equity.

    Returns whether the identity holds within tolerance, and the difference.
    """
    expected = data.total_liabilities + data.total_equity
    difference = data.total_assets - expected
    tolerance = max(
        IDENTITY_ABSOLUTE_TOLERANCE, abs(data.total_assets) * IDENTITY_RELATIVE_TOLERANCE
    )
    return abs(difference) <= tolerance, difference


def validate_financial_inputs(data: FinancialInputs) -> ValidationResult:
    """Run every cross-field check over one set of financial inputs."""
    result = ValidationResult()

    identity_ok, difference = check_accounting_identity(data)
    result.accounting_identity_ok = identity_ok
    if not identity_ok:
        result.errors.append(
            "Accounting identity does not hold: total assets differ from "
            f"liabilities plus equity by {difference:,.2f}."
        )

    if data.current_assets > data.total_assets:
        result.errors.append("Current assets exceed total assets.")

    if data.current_liabilities > data.total_liabilities:
        result.errors.append("Current liabilities exceed total liabilities.")

    if data.inventory is not None and data.inventory > data.current_assets:
        result.errors.append("Inventory exceeds current assets.")

    if data.cost_of_goods_sold > data.revenue:
        result.warnings.append(
            "Cost of goods sold exceeds revenue, giving a negative gross profit."
        )

    if data.accounts_receivable > data.current_assets:
        result.errors.append("Accounts receivable exceed current assets.")

    # A reported net profit far from the figure implied by the other income
    # statement lines usually means a data entry error, but it can also be a
    # legitimate consequence of items the simplified model does not carry, so
    # it is a warning rather than an error.
    implied_net = (
        data.operating_profit - data.interest_expense - data.tax_expense
    )
    if abs(data.net_profit - implied_net) > max(1.0, abs(data.revenue) * 0.05):
        result.warnings.append(
            "Reported net profit differs from the figure implied by revenue, "
            "costs, interest and tax."
        )

    return result
