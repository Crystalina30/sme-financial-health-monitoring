"""Financial indicator calculation engine.

This module is the sole numerical source of truth for indicator values. It
contains no database access, no HTTP concerns and no presentation logic: each
function takes validated financial inputs and returns a number or ``None``.

``None`` means the indicator is *not applicable* for the given inputs — most
often because a denominator is zero or a required value was not reported. It
never means zero. The distinction matters because a category score is the
average of its applicable indicators only, and treating a missing indicator as
zero would understate the company's health.

One case is different: debt-to-equity has no meaningful value when equity is
zero or negative, but that is the *worst* solvency position, not a gap in the
data. Dropping it would let the remaining solvency indicators average upwards,
so it is marked ``worst_case`` and the scorer gives it the lowest score.
"""

from dataclasses import dataclass

from app.models.enums import (
    INDICATOR_CATEGORIES,
    INDICATOR_DISPLAY_NAMES,
    INDICATOR_UNITS,
    IndicatorCategory,
    IndicatorCode,
)
from app.schemas.financial_inputs import DAYS_IN_YEAR, FinancialInputs

# Denominators whose absolute value is below this are treated as zero, which
# avoids both division-by-zero errors and meaningless very large ratios.
ZERO_TOLERANCE = 1e-9


def _safe_divide(numerator: float, denominator: float) -> float | None:
    """Divide, returning None when the denominator is effectively zero."""
    if abs(denominator) < ZERO_TOLERANCE:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------


def calculate_current_ratio(data: FinancialInputs) -> float | None:
    """Current assets divided by current liabilities.

    Measures whether short-term assets cover short-term obligations. Not
    applicable when the company reports no current liabilities.
    """
    return _safe_divide(data.current_assets, data.current_liabilities)


def calculate_quick_ratio(data: FinancialInputs) -> float | None:
    """Current assets excluding inventory, divided by current liabilities.

    A stricter liquidity test than the current ratio, since inventory is the
    current asset least readily converted to cash. Not applicable when
    inventory was not reported, because excluding an unknown amount would
    silently equal the current ratio and overstate liquidity.
    """
    if data.inventory is None:
        return None
    return _safe_divide(data.current_assets - data.inventory, data.current_liabilities)


# ---------------------------------------------------------------------------
# Profitability
# ---------------------------------------------------------------------------


def calculate_gross_profit_margin(data: FinancialInputs) -> float | None:
    """Gross profit as a percentage of revenue."""
    ratio = _safe_divide(data.gross_profit, data.revenue)
    return None if ratio is None else ratio * 100


def calculate_net_profit_margin(data: FinancialInputs) -> float | None:
    """Net profit as a percentage of revenue."""
    ratio = _safe_divide(data.net_profit, data.revenue)
    return None if ratio is None else ratio * 100


def calculate_return_on_assets(data: FinancialInputs) -> float | None:
    """Net profit as a percentage of total assets.

    Measures how efficiently the asset base generates profit.
    """
    ratio = _safe_divide(data.net_profit, data.total_assets)
    return None if ratio is None else ratio * 100


# ---------------------------------------------------------------------------
# Solvency
# ---------------------------------------------------------------------------


def calculate_debt_to_equity(data: FinancialInputs) -> float | None:
    """Total liabilities divided by total equity.

    Not applicable when equity is zero or negative: the ratio is undefined at
    zero, and at negative equity it becomes negative, which would be read as
    an improvement when the position has in fact deteriorated badly.
    """
    if data.total_equity <= ZERO_TOLERANCE:
        return None
    return _safe_divide(data.total_liabilities, data.total_equity)


def calculate_debt_ratio(data: FinancialInputs) -> float | None:
    """Total liabilities divided by total assets."""
    return _safe_divide(data.total_liabilities, data.total_assets)


def calculate_interest_coverage(data: FinancialInputs) -> float | None:
    """Operating profit divided by interest expense.

    Measures how many times over operating profit covers interest. Not
    applicable when there is no interest expense, since a company with no
    interest-bearing debt has nothing to cover.
    """
    return _safe_divide(data.operating_profit, data.interest_expense)


# ---------------------------------------------------------------------------
# Efficiency
# ---------------------------------------------------------------------------


def calculate_asset_turnover(data: FinancialInputs) -> float | None:
    """Annualised revenue divided by total assets.

    Revenue covers the reporting period while total assets is a closing
    balance, so revenue is scaled to a year: ``revenue * 365 / D``, where D is
    the period length in days. For a full-year period this is plain revenue
    divided by total assets. Closing rather than average assets are used
    because opening balances are not recorded.
    """
    annual_revenue = data.revenue * DAYS_IN_YEAR / data.effective_period_days
    return _safe_divide(annual_revenue, data.total_assets)


def calculate_days_sales_outstanding(data: FinancialInputs) -> float | None:
    """Average number of days taken to collect receivables.

    Closing accounts receivable divided by the period's revenue, times the
    period length in days: receivables expressed as days of sales. Using the
    period's own length means a quarterly or monthly period is not scaled as
    though its revenue were a year's.
    """
    ratio = _safe_divide(data.accounts_receivable, data.revenue)
    return None if ratio is None else ratio * data.effective_period_days


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

#: Maps each indicator to the function that calculates it.
INDICATOR_FUNCTIONS = {
    IndicatorCode.CURRENT_RATIO: calculate_current_ratio,
    IndicatorCode.QUICK_RATIO: calculate_quick_ratio,
    IndicatorCode.GROSS_PROFIT_MARGIN: calculate_gross_profit_margin,
    IndicatorCode.NET_PROFIT_MARGIN: calculate_net_profit_margin,
    IndicatorCode.RETURN_ON_ASSETS: calculate_return_on_assets,
    IndicatorCode.DEBT_TO_EQUITY: calculate_debt_to_equity,
    IndicatorCode.DEBT_RATIO: calculate_debt_ratio,
    IndicatorCode.INTEREST_COVERAGE: calculate_interest_coverage,
    IndicatorCode.ASSET_TURNOVER: calculate_asset_turnover,
    IndicatorCode.DAYS_SALES_OUTSTANDING: calculate_days_sales_outstanding,
}

#: Why an indicator may be not applicable, shown to the user alongside N/A.
NOT_APPLICABLE_NOTES = {
    IndicatorCode.CURRENT_RATIO: "No current liabilities reported.",
    IndicatorCode.QUICK_RATIO: "Inventory not reported.",
    IndicatorCode.GROSS_PROFIT_MARGIN: "No revenue reported.",
    IndicatorCode.NET_PROFIT_MARGIN: "No revenue reported.",
    IndicatorCode.RETURN_ON_ASSETS: "No total assets reported.",
    IndicatorCode.DEBT_TO_EQUITY: "Neither equity nor liabilities are reported.",
    IndicatorCode.DEBT_RATIO: "No total assets reported.",
    IndicatorCode.INTEREST_COVERAGE: "No interest expense reported.",
    IndicatorCode.ASSET_TURNOVER: "No total assets reported.",
    IndicatorCode.DAYS_SALES_OUTSTANDING: "No revenue reported.",
}


@dataclass(frozen=True)
class CalculatedIndicator:
    """One indicator value together with the metadata the frontend needs."""

    code: IndicatorCode
    display_name: str
    category: IndicatorCategory
    unit: str
    value: float | None
    is_applicable: bool
    note: str | None = None
    # Set when the value is undefined because the position is as bad as it
    # can be (equity at or below zero), rather than because data is missing.
    worst_case: bool = False


#: Shown when debt-to-equity is scored as the worst case.
NEGATIVE_EQUITY_NOTE = (
    "Equity is zero or negative, so liabilities exceed assets. The ratio is "
    "undefined and is scored as the worst solvency position."
)


def _is_negative_equity_worst_case(code: IndicatorCode, data: FinancialInputs) -> bool:
    """True when debt-to-equity is undefined because the company is insolvent.

    Equity at or below zero with liabilities outstanding means liabilities are
    at least equal to assets. With no liabilities either, there is simply
    nothing to measure, and the indicator stays not applicable.
    """
    return (
        code is IndicatorCode.DEBT_TO_EQUITY
        and data.total_equity <= ZERO_TOLERANCE
        and data.total_liabilities > ZERO_TOLERANCE
    )


def calculate_indicators(data: FinancialInputs) -> list[CalculatedIndicator]:
    """Calculate all ten indicators from the given financial inputs.

    Always returns ten results in a fixed order. An indicator that cannot be
    calculated is returned with ``value=None`` and ``is_applicable=False``
    rather than being omitted, so that the dashboard can show it as N/A and
    the reason why.
    """
    results: list[CalculatedIndicator] = []
    for code, function in INDICATOR_FUNCTIONS.items():
        value = function(data)
        worst_case = value is None and _is_negative_equity_worst_case(code, data)
        if worst_case:
            note = NEGATIVE_EQUITY_NOTE
        else:
            note = None if value is not None else NOT_APPLICABLE_NOTES[code]
        results.append(
            CalculatedIndicator(
                code=code,
                display_name=INDICATOR_DISPLAY_NAMES[code],
                category=INDICATOR_CATEGORIES[code],
                unit=INDICATOR_UNITS[code],
                value=value,
                is_applicable=value is not None or worst_case,
                note=note,
                worst_case=worst_case,
            )
        )
    return results
