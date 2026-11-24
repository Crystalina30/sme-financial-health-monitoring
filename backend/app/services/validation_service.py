"""Validation of submitted financial data.

Validation that can be expressed as a field rule lives in the Pydantic
schemas. This module holds the checks that span several fields — the
balance-sheet identity and the income-statement reconciliation above all —
and returns findings rather than raising, so that a record can be stored *and
flagged* instead of being silently accepted or silently discarded.

Every finding has a severity:

* ``blocking``  structurally invalid data or an accounting failure. The record
  is not stored. (The balance-sheet identity, to RM0.01.)
* ``material``  the figures can be stored for correction, but any assessment
  made from them is **provisional** until the record is corrected. (An
  income statement that does not reconcile.)
* ``info``      an explanation that does not affect reliability. (A negative
  gross profit: a loss is not an error.)
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.financial_inputs import FinancialInputs

#: Amounts are recorded to two decimal places (sen/cents).
CENT = Decimal("0.01")

# ---------------------------------------------------------------------------
# Rounding policy for the accounting identity
# ---------------------------------------------------------------------------
#: Every check is made on exact decimal amounts. The tolerance depends only on
#: the *presentation unit* the source figures were rounded to, which must be
#: stated with the record; it never depends on the size of the company.
#:
#: * **Exact figures (to the sen)**, the default and every figure calculated
#:   from a trial balance: the tolerance is RM0.01. Any larger difference is a
#:   genuine discrepancy.
#: * **A published statement rounded to RM1, RM'000 or RM million** (as listed
#:   companies present their accounts): each published figure carries up to
#:   half a unit of rounding, and an equation that combines n such figures can
#:   be out by up to n × ½ unit with nothing wrong. The tolerance is therefore
#:   ½ unit × the number of non-zero figures in the equation (3 for
#:   assets = liabilities + equity; the reported net profit plus each non-zero
#:   line for the income statement). Anything larger cannot be rounding.
#:   Figures are still entered as full amounts (RM'000 figures multiplied by
#:   1,000), so ratios and amounts stay in ringgit.
#:
#: Figures are never adjusted to make them balance: the submitted values are
#: stored as entered.
DEFAULT_PRESENTATION_UNIT = CENT
ALLOWED_PRESENTATION_UNITS = (CENT, Decimal("1"), Decimal("1000"), Decimal("1000000"))


def to_money(value: float | int | Decimal) -> Decimal:
    """An amount as an exact decimal rounded to the cent.

    Floats are converted through their shortest decimal representation, so
    109999.99 becomes exactly Decimal("109999.99") rather than the binary
    approximation 109999.98999999...
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError("Amounts must be finite numbers.")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


BLOCKING = "blocking"
MATERIAL = "material"
INFO = "info"


@dataclass(frozen=True)
class Issue:
    """One validation finding."""

    severity: str  # BLOCKING, MATERIAL or INFO
    code: str
    message: str


@dataclass(frozen=True)
class IncomeStatementReconciliation:
    """The income statement rebuilt from its lines, against the reported net
    profit. All amounts are exact decimals to the cent.

        gross profit       = revenue − cost of goods sold
        operating profit   = gross profit + other operating income
                             − operating expenses
        profit before tax  = operating profit + other (non-operating) income
                             − other (non-operating) expenses − interest
        calculated net     = profit before tax − tax expense
        difference         = reported net profit − calculated net profit
    """

    revenue: Decimal
    cost_of_goods_sold: Decimal
    gross_profit: Decimal
    other_operating_income: Decimal
    operating_expenses: Decimal
    operating_profit: Decimal
    other_income: Decimal
    other_expenses: Decimal
    interest_expense: Decimal
    profit_before_tax: Decimal
    tax_expense: Decimal
    calculated_net_profit: Decimal
    reported_net_profit: Decimal
    difference: Decimal
    tolerance: Decimal

    @property
    def reconciled(self) -> bool:
        return abs(self.difference) <= self.tolerance


@dataclass
class ValidationResult:
    """Outcome of cross-field validation."""

    accounting_identity_ok: bool = True
    issues: list[Issue] = field(default_factory=list)
    reconciliation: IncomeStatementReconciliation | None = None

    def add(self, severity: str, code: str, message: str) -> None:
        self.issues.append(Issue(severity, code, message))

    @property
    def errors(self) -> list[str]:
        """Blocking findings: the record must not be stored."""
        return [issue.message for issue in self.issues if issue.severity == BLOCKING]

    @property
    def warnings(self) -> list[str]:
        """Material findings: stored, but the assessment is provisional."""
        return [issue.message for issue in self.issues if issue.severity == MATERIAL]

    @property
    def info(self) -> list[str]:
        return [issue.message for issue in self.issues if issue.severity == INFO]

    @property
    def is_valid(self) -> bool:
        """True when nothing blocks the record from being stored."""
        return not self.errors

    @property
    def notes(self) -> str | None:
        """Blocking and material findings as one string, stored with the record."""
        combined = self.errors + self.warnings
        return "; ".join(combined) if combined else None


PRESENTATION_UNIT_LABELS = {
    CENT: "exact figures (to the sen)",
    Decimal("1"): "figures rounded to RM1",
    Decimal("1000"): "figures rounded to RM'000",
    Decimal("1000000"): "figures rounded to RM million",
}


def _presentation_unit(unit: Decimal) -> Decimal:
    unit = Decimal(str(unit)).normalize() if not isinstance(unit, Decimal) else unit
    for allowed in ALLOWED_PRESENTATION_UNITS:
        if unit == allowed:
            return allowed
    raise ValueError(
        f"Unsupported presentation unit {unit}; use one of "
        + ", ".join(str(u) for u in ALLOWED_PRESENTATION_UNITS)
    )


def rounding_tolerance(presentation_unit: Decimal, rounded_figures: int) -> Decimal:
    """The largest difference rounding alone can explain (see the policy above)."""
    unit = _presentation_unit(presentation_unit)
    if unit == CENT:
        return CENT
    return unit / 2 * max(rounded_figures, 1)


def check_accounting_identity(
    data: FinancialInputs, presentation_unit: Decimal = DEFAULT_PRESENTATION_UNIT
) -> tuple[bool, float]:
    """Check that total assets equal total liabilities plus total equity.

    Works on exact decimal amounts. The identity holds when the difference is
    at most one presentation unit (RM0.01 by default; see the rounding policy
    above). Negative equity is allowed: only the equation is checked.

    Returns whether the identity holds and the signed difference
    (assets − liabilities − equity), to the cent.
    """
    tolerance = rounding_tolerance(presentation_unit, 3)
    difference = to_money(data.total_assets) - (
        to_money(data.total_liabilities) + to_money(data.total_equity)
    )
    return abs(difference) <= tolerance, float(difference)


def reconcile_income_statement(
    data: FinancialInputs, presentation_unit: Decimal = DEFAULT_PRESENTATION_UNIT
) -> IncomeStatementReconciliation:
    """Rebuild net profit from the statement's lines and compare it with the
    reported figure, exactly.

    **Materiality policy.** Net profit is the last line of the same statement
    as its components, so in a correctly prepared statement it equals them
    exactly. Any difference larger than one presentation unit (RM0.01 by
    default, the same rule as the balance sheet) is therefore treated as a
    material, unresolved discrepancy, whatever its size: either a line is
    missing from the entry or a figure is wrong, and the system cannot tell
    which. The earlier rule (a warning only beyond 5% of revenue) was
    rejected: it let RM60,000 go unexplained on RM1.2 million of revenue,
    and it shrank to almost nothing exactly when revenue itself was the
    mistyped figure.
    """
    revenue = to_money(data.revenue)
    cogs = to_money(data.cost_of_goods_sold)
    other_operating_income = to_money(data.other_operating_income)
    opex = to_money(data.operating_expenses)
    other_income = to_money(data.other_income)
    other_expenses = to_money(data.other_expenses)
    interest = to_money(data.interest_expense)
    tax = to_money(data.tax_expense)

    gross = revenue - cogs
    operating = gross + other_operating_income - opex
    before_tax = operating + other_income - other_expenses - interest
    calculated = before_tax - tax
    reported = to_money(data.net_profit)
    lines = (revenue, cogs, other_operating_income, opex, other_income, other_expenses,
             interest, tax)
    tolerance = rounding_tolerance(presentation_unit, 1 + sum(1 for v in lines if v != 0))
    return IncomeStatementReconciliation(
        revenue=revenue,
        cost_of_goods_sold=cogs,
        gross_profit=gross,
        other_operating_income=other_operating_income,
        operating_expenses=opex,
        operating_profit=operating,
        other_income=other_income,
        other_expenses=other_expenses,
        interest_expense=interest,
        profit_before_tax=before_tax,
        tax_expense=tax,
        calculated_net_profit=calculated,
        reported_net_profit=reported,
        difference=reported - calculated,
        tolerance=tolerance,
    )


def validate_financial_inputs(
    data: FinancialInputs, presentation_unit: Decimal = DEFAULT_PRESENTATION_UNIT
) -> ValidationResult:
    """Run every cross-field check over one set of financial inputs.

    Nothing here changes the figures; it only reports what is wrong with them.
    """
    result = ValidationResult()

    identity_ok, difference = check_accounting_identity(data, presentation_unit)
    result.accounting_identity_ok = identity_ok
    if not identity_ok:
        assets = to_money(data.total_assets)
        liabilities_and_equity = to_money(data.total_liabilities) + to_money(data.total_equity)
        result.add(
            BLOCKING,
            "balance_sheet_identity",
            "Accounting identity does not hold: total assets "
            f"{assets:,.2f} do not equal total liabilities plus equity "
            f"{liabilities_and_equity:,.2f} (difference {abs(Decimal(str(difference))):,.2f}; "
            f"they must agree to within "
            f"{rounding_tolerance(presentation_unit, 3):,.2f} for "
            f"{PRESENTATION_UNIT_LABELS[_presentation_unit(presentation_unit)]})."
        )

    if data.current_assets > data.total_assets:
        result.add(BLOCKING, "current_assets_exceed_total",
                   "Current assets exceed total assets.")

    if data.current_liabilities > data.total_liabilities:
        result.add(BLOCKING, "current_liabilities_exceed_total",
                   "Current liabilities exceed total liabilities.")

    if data.inventory is not None and data.inventory > data.current_assets:
        result.add(BLOCKING, "inventory_exceeds_current_assets",
                   "Inventory exceeds current assets.")

    if data.accounts_receivable > data.current_assets:
        result.add(BLOCKING, "receivables_exceed_current_assets",
                   "Accounts receivable exceed current assets.")

    # The parts of current assets cannot add up to more than the whole. Each
    # part is non-negative (receivables are net of the allowance), so their
    # sum is a lower bound on current assets; only rounding is allowed.
    parts = (to_money(data.cash_and_equivalents) + to_money(data.accounts_receivable)
             + to_money(data.inventory or 0))
    rounded_parts = 1 + sum(1 for v in (data.cash_and_equivalents, data.accounts_receivable,
                                        data.inventory) if v)
    if parts - to_money(data.current_assets) > rounding_tolerance(presentation_unit,
                                                                  rounded_parts):
        result.add(
            BLOCKING, "current_asset_components_exceed_total",
            f"Cash, receivables and inventory together ({parts:,.2f}) exceed current "
            f"assets ({to_money(data.current_assets):,.2f}) by "
            f"{parts - to_money(data.current_assets):,.2f}. Current assets must include them.",
        )

    reconciliation = reconcile_income_statement(data, presentation_unit)
    result.reconciliation = reconciliation
    if not reconciliation.reconciled:
        result.add(
            MATERIAL,
            "net_profit_unreconciled",
            f"Reported net profit ({reconciliation.reported_net_profit:,.2f}) differs from "
            f"the calculated net profit ({reconciliation.calculated_net_profit:,.2f}) by "
            f"{abs(reconciliation.difference):,.2f} (allowed: {reconciliation.tolerance:,.2f} "
            f"for {PRESENTATION_UNIT_LABELS[_presentation_unit(presentation_unit)]}). "
            "Net profit is calculated as revenue − "
            "cost of goods sold + other operating income − operating expenses + other "
            "income − other expenses − interest − tax. Correct the figures, or enter the "
            "missing income or expense lines.",
        )

    # A loss is a financial result, not a data error.
    if reconciliation.gross_profit < 0:
        result.add(
            INFO,
            "negative_gross_profit",
            f"Gross profit is negative ({reconciliation.gross_profit:,.2f}): cost of goods "
            "sold exceeds revenue. This is not treated as an error, but check the figures "
            "if it is unexpected.",
        )

    return result
