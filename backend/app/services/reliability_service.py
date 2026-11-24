"""How far an assessment can be relied on.

Financial health (Sound, Vulnerable, Distressed) says what the figures show.
Assessment reliability says whether the figures themselves can be trusted.
They are separate: a company can be Sound on figures that do not add up, or
Distressed on figures that are perfectly consistent.

Reliability statuses:

* ``validated``          every implemented check passes and no material data
                         problem is open. Shown as **"Checks passed"**: it
                         means the figures are internally consistent and
                         complete as far as these checks can tell, not that
                         they have been audited or are correct. A balanced,
                         reconciling set of figures can still omit an
                         account. ``checks`` lists exactly what was checked.
* ``provisional``        a score can be calculated, but a material problem is
                         unresolved (for example net profit does not reconcile
                         to its components). The score is indicative only.
* ``insufficient_data``  essential figures are missing, so financial health
                         cannot be assessed. No score is shown.

The status is worked out from the record as it is now, every time it is
shown (dashboard, overview, trend), never from a stored flag alone and never
just from whether a score happens to exist.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.models.enums import AssessmentStatus
from app.models.financial_record import FinancialRecord
from app.schemas.financial_inputs import FinancialInputs
from app.services.scoring_service import HealthAssessment
from app.services.trial_balance_service import Derivation, Line, derive
from app.services.validation_service import (
    CENT,
    INFO,
    MATERIAL,
    PRESENTATION_UNIT_LABELS,
    IncomeStatementReconciliation,
    Issue,
    rounding_tolerance,
    validate_financial_inputs,
)

_INVENTORY_CODES = {"missing_closing_stock", "inventory_may_be_opening_stock",
                    "closing_stock_mismatch", "stock_not_confirmed", "mixed_cost_of_sales"}


@dataclass(frozen=True)
class Check:
    """One check that was run. passed is None when it did not apply."""

    name: str
    passed: bool | None
    detail: str


@dataclass(frozen=True)
class AssessmentReliability:
    status: AssessmentStatus
    issues: list[Issue] = field(default_factory=list)
    reconciliation: IncomeStatementReconciliation | None = None
    checks: list[Check] = field(default_factory=list)

    @property
    def is_provisional(self) -> bool:
        return self.status is AssessmentStatus.PROVISIONAL

    @property
    def material_issues(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == MATERIAL]


def _derivation(record: FinancialRecord) -> Derivation | None:
    if record.source != "trial_balance" or not record.trial_balance_lines:
        return None
    return derive([
        Line(row.line_number, row.account_code, row.account_name, float(row.debit),
             float(row.credit), row.category, row.account_group, row.source_ref)
        for row in record.trial_balance_lines
    ])


def _trial_balance_issues(derivation: Derivation | None) -> list[Issue]:
    """Findings from the trial balance a record was calculated from."""
    if derivation is None:
        return []
    issues = [Issue("material", "trial_balance_error", f"Trial balance: {message}")
              for message in derivation.errors]
    issues += [Issue(severity, code, f"Trial balance: {message}")
               for severity, code, message in derivation.findings]
    return issues


def evaluate_reliability(
    record: FinancialRecord,
    inputs: FinancialInputs,
    health: HealthAssessment,
    data_quality_notes: list[str] | None = None,
) -> AssessmentReliability:
    """Decide whether an assessment is validated, provisional or impossible."""
    unit = Decimal(str(getattr(record, "presentation_unit", None) or "0.01")).quantize(CENT)
    validation = validate_financial_inputs(inputs, unit)
    derivation = _derivation(record)
    issues: list[Issue] = []

    # A blocking finding cannot be in a stored record created under the
    # current rules, but older records predate them. They stay readable and
    # are flagged, never silently treated as valid.
    for issue in validation.issues:
        severity = MATERIAL if issue.severity == "blocking" else issue.severity
        issues.append(Issue(severity, issue.code, issue.message))
    if not record.accounting_identity_ok and not any(
        issue.code == "balance_sheet_identity" for issue in issues
    ):
        issues.append(Issue(MATERIAL, "balance_sheet_identity",
                            "This record was stored as failing the accounting identity."))
    issues += _trial_balance_issues(derivation)
    if unit != CENT:
        issues.append(Issue(
            INFO, "rounded_source",
            f"The figures were entered from a statement with "
            f"{PRESENTATION_UNIT_LABELS[unit]}, so rounding differences of up to "
            f"{rounding_tolerance(unit, 3):,.2f} on the balance sheet and "
            f"{validation.reconciliation.tolerance:,.2f} on net profit are accepted."))
    issues += [Issue(INFO, "data_quality_note", note) for note in (data_quality_notes or [])]

    essential_missing = []
    if Decimal(str(inputs.total_assets)) <= 0:
        essential_missing.append("total assets")
    if health.overall_score is None or essential_missing:
        reason = (
            "Essential financial information is unavailable"
            + (f" ({', '.join(essential_missing)})" if essential_missing else "")
            + ": no financial indicator could be calculated meaningfully."
        )
        issues.insert(0, Issue(MATERIAL, "insufficient_data", reason))
        status = AssessmentStatus.INSUFFICIENT_DATA
    elif any(issue.severity == MATERIAL for issue in issues):
        status = AssessmentStatus.PROVISIONAL
    else:
        status = AssessmentStatus.VALIDATED

    # Keep each message once, in order.
    unique: dict[tuple[str, str], Issue] = {}
    for issue in issues:
        unique.setdefault((issue.code, issue.message), issue)
    checks = _checks(validation, derivation, unit, status)
    return AssessmentReliability(
        status, list(unique.values()), validation.reconciliation, checks
    )


def _checks(validation, derivation, unit, status) -> list[Check]:
    """What was actually verified, in plain words."""
    rec = validation.reconciliation
    precision = PRESENTATION_UNIT_LABELS[unit]
    checks = [
        Check(
            "Balance sheet balances (assets = liabilities + equity)",
            validation.accounting_identity_ok,
            f"Exact decimal check; tolerance {rounding_tolerance(unit, 3):,.2f} for {precision}.",
        ),
        Check(
            "Net profit reconciles with the income statement lines",
            rec.reconciled,
            f"Difference {abs(rec.difference):,.2f}; tolerance {rec.tolerance:,.2f} "
            f"for {precision}.",
        ),
    ]
    if derivation is None:
        checks.append(Check(
            "Trial balance checks", None,
            "Not applicable: the figures were entered as statement totals, so account-level "
            "completeness could not be checked."))
    else:
        material = {code for severity, code, _ in derivation.findings if severity == MATERIAL}
        checks.append(Check(
            "Trial balance balances and every account is categorised",
            derivation.is_valid,
            f"Debits {derivation.total_debit:,.2f}, credits {derivation.total_credit:,.2f}.",
        ))
        inventory = derivation.inventory
        checks.append(Check(
            "Period-end stock is accounted for",
            not (material & _INVENTORY_CODES),
            inventory.label + ". " + inventory.explanation if inventory else "",
        ))
        checks.append(Check(
            "No duplicated, reversed or post-closing balances",
            not (material - _INVENTORY_CODES),
            "Repeated account codes, accounts on the wrong side of their category, and a "
            "trial balance taken after closing entries.",
        ))
    checks.append(Check(
        "Enough figures to assess financial health",
        status is not AssessmentStatus.INSUFFICIENT_DATA,
        "At least one category of indicators can be scored and total assets are recorded.",
    ))
    return checks
