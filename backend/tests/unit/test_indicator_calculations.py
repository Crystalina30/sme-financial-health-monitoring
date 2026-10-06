"""Tests for the ten indicator calculations.

Expected values are computed by hand in the fixture module, so these tests
check the implementation against an independent calculation rather than
against the implementation's own output.
"""

import pytest

from app.schemas.financial_inputs import FinancialInputs
from app.services.financial_calculation_service import (
    calculate_asset_turnover,
    calculate_current_ratio,
    calculate_days_sales_outstanding,
    calculate_debt_ratio,
    calculate_debt_to_equity,
    calculate_gross_profit_margin,
    calculate_indicators,
    calculate_interest_coverage,
    calculate_net_profit_margin,
    calculate_quick_ratio,
    calculate_return_on_assets,
)
from tests.fixtures.financial_data import (
    SERVICE_COMPANY_NO_INVENTORY,
    SOUND_COMPANY,
)


def test_current_ratio():
    assert calculate_current_ratio(SOUND_COMPANY) == pytest.approx(2.5)


def test_quick_ratio_excludes_inventory():
    assert calculate_quick_ratio(SOUND_COMPANY) == pytest.approx(220_000 / 120_000)


def test_gross_profit_margin():
    assert calculate_gross_profit_margin(SOUND_COMPANY) == pytest.approx(40.0)


def test_net_profit_margin():
    assert calculate_net_profit_margin(SOUND_COMPANY) == pytest.approx(12.0)


def test_return_on_assets():
    assert calculate_return_on_assets(SOUND_COMPANY) == pytest.approx(15.0)


def test_debt_to_equity():
    assert calculate_debt_to_equity(SOUND_COMPANY) == pytest.approx(0.6)


def test_debt_ratio():
    assert calculate_debt_ratio(SOUND_COMPANY) == pytest.approx(0.375)


def test_interest_coverage_uses_operating_profit():
    # Operating profit = 1,000,000 - 600,000 - 220,000 = 180,000
    assert calculate_interest_coverage(SOUND_COMPANY) == pytest.approx(9.0)


def test_asset_turnover():
    assert calculate_asset_turnover(SOUND_COMPANY) == pytest.approx(1.25)


def test_days_sales_outstanding():
    assert calculate_days_sales_outstanding(SOUND_COMPANY) == pytest.approx(
        90_000 / 1_000_000 * 365
    )


def test_calculate_indicators_always_returns_ten():
    assert len(calculate_indicators(SOUND_COMPANY)) == 10


def test_all_ten_applicable_for_complete_data():
    results = calculate_indicators(SOUND_COMPANY)
    assert all(item.is_applicable for item in results)


# ---------------------------------------------------------------------------
# Division by zero and missing data
# ---------------------------------------------------------------------------

ZERO_DENOMINATORS = FinancialInputs(
    revenue=0,
    cost_of_goods_sold=0,
    operating_expenses=0,
    interest_expense=0,
    tax_expense=0,
    net_profit=0,
    cash_and_equivalents=0,
    accounts_receivable=0,
    inventory=0,
    current_assets=0,
    total_assets=0,
    current_liabilities=0,
    total_liabilities=0,
    total_equity=0,
)


def test_zero_denominators_give_not_applicable_not_an_error():
    results = calculate_indicators(ZERO_DENOMINATORS)
    assert len(results) == 10
    assert all(not item.is_applicable for item in results)
    assert all(item.value is None for item in results)


def test_missing_inventory_makes_quick_ratio_not_applicable():
    assert calculate_quick_ratio(SERVICE_COMPANY_NO_INVENTORY) is None


def test_no_interest_expense_makes_coverage_not_applicable():
    assert calculate_interest_coverage(SERVICE_COMPANY_NO_INVENTORY) is None


def test_not_applicable_is_never_reported_as_zero():
    results = {item.code: item for item in calculate_indicators(SERVICE_COMPANY_NO_INVENTORY)}
    for item in results.values():
        if not item.is_applicable:
            assert item.value is None
            assert item.note is not None


def test_negative_equity_makes_debt_to_equity_not_applicable():
    negative_equity = SOUND_COMPANY.model_copy(update={"total_equity": -50_000})
    assert calculate_debt_to_equity(negative_equity) is None
