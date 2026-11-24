"""Regression tests built from an external, previously verified trial balance.

The reference trial balance (tests/fixtures/tally_reference.py) was checked
cell by cell against its published statements; see
ACCOUNTING_DATASET_VALIDATION.md. These tests lock in that agreement, so a
later change to classification, derivation, ratios or scoring cannot
silently change a verified result.

Expected ratio values are worked out here from the published statement
figures with the textbook formulas, not taken from the engine.
"""

import pytest

from app.analysis.sensitivity import _default_thresholds
from app.models.enums import IndicatorCode
from app.schemas.financial_inputs import FinancialInputs
from app.services.benchmark_service import calculate_altman_z_double_prime
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import assess
from app.services.trial_balance_service import Line, derive, suggest
from app.services.validation_service import validate_financial_inputs
from tests.fixtures.tally_reference import (
    EXPECTED_CATEGORIES,
    REFERENCE_STATEMENTS,
    TALLY_TRIAL_BALANCE,
)

REF = REFERENCE_STATEMENTS


def _lines(rows=TALLY_TRIAL_BALANCE, categories=None):
    lines = []
    for number, (name, group, debit, credit) in enumerate(rows, start=1):
        category = (categories or {}).get(name)
        if category is None:
            category, _ = suggest(name, group, debit, credit)
        lines.append(Line(number, "", name, float(debit), float(credit), category, group,
                          f"Trial Balance › row {number + 1}"))
    return lines


@pytest.fixture(scope="module")
def derivation():
    return derive(_lines())


@pytest.fixture(scope="module")
def inputs(derivation):
    return FinancialInputs(**derivation.record_values(), period_days=365)


# ---- Classification --------------------------------------------------------


@pytest.mark.parametrize("name,group,debit,credit", TALLY_TRIAL_BALANCE)
def test_every_ledger_is_classified_from_its_group(name, group, debit, credit):
    category, basis = suggest(name, group, debit, credit)
    assert category == EXPECTED_CATEGORIES[name]
    assert basis == "account_group"


def test_indirect_expenses_are_not_read_as_direct_expenses():
    # Regression: "direct expense" once matched inside "Indirect Expenses",
    # which put transport costs into cost of goods sold.
    assert suggest("Transportation Charges", "Indirect Expenses")[0] == "operating_expense"
    assert suggest("Carriage", "Direct Expenses")[0] == "cost_of_sales"
    assert suggest("Commission received", "Indirect Incomes")[0] == "other_income"


def test_duties_and_taxes_follow_the_name_then_the_balance():
    assert suggest("Input CGST", "Duties & Taxes", 100, 0)[0] == "other_current_asset"
    assert suggest("Output IGST", "Duties & Taxes", 0, 100)[0] == "current_liability"
    assert suggest("TDS", "Duties & Taxes", 0, 100)[0] == "current_liability"
    assert suggest("TDS", "Duties & Taxes", 100, 0)[0] == "other_current_asset"


def test_a_group_can_be_refined_by_the_name_within_the_same_statement():
    assert suggest("Bank interest", "Indirect Expenses")[0] == "interest_expense"
    assert suggest("Stock", "Current Assets")[0] == "inventory"
    assert suggest("Retained earnings", "Capital")[0] == "retained_earnings"


def test_unknown_or_suspense_groups_give_no_suggestion():
    assert suggest("Difference in opening balances", "Suspense A/c") == (None, None)
    assert suggest("Mystery", "Mystery group") == (None, None)


# ---- Statements --------------------------------------------------------------


def test_trial_balance_balances(derivation):
    assert derivation.total_debit == pytest.approx(REF["total_debit"])
    assert derivation.total_credit == pytest.approx(REF["total_credit"])
    assert derivation.errors == []


@pytest.mark.parametrize(
    "figure",
    ["revenue", "cost_of_goods_sold", "gross_profit", "operating_expenses", "net_profit",
     "cash_and_equivalents", "accounts_receivable", "inventory", "total_assets",
     "current_liabilities", "total_liabilities", "total_equity"],
)
def test_statement_figure_matches_the_reference(derivation, figure):
    assert derivation.figures[figure].value == pytest.approx(REF[figure], abs=0.01)


def test_cost_of_goods_sold_is_traced_to_its_ledgers(derivation):
    cogs = derivation.figures["cost_of_goods_sold"]
    assert {c.account_name: c.amount for c in cogs.contributions} == {
        "Opening Stock": 491290.86,
        "Purchases (Taxable Portion)": 1460006.65,
        "Freight Inward": 31810.22,
        "Round Off (Purchases)": 3.5,
    }
    assert all(c.source_ref.startswith("Trial Balance › row") for c in cogs.contributions)


def test_balance_sheet_balances(derivation):
    figures = derivation.figures
    assert figures["total_assets"].value == pytest.approx(
        figures["total_liabilities"].value + figures["total_equity"].value, abs=0.01
    )


def test_missing_closing_stock_is_flagged(derivation):
    # The reference posts no closing stock, so COGS assumes every unit sold.
    assert any("no closing stock" in warning for warning in derivation.warnings)


def test_reference_has_no_retained_earnings_account(derivation):
    # The year's profit sits in equity, but no retained earnings ledger exists,
    # so retained earnings are "not reported", never zero.
    assert derivation.figures["retained_earnings"].value is None


def test_a_balanced_trial_balance_can_still_be_misclassified():
    # Balanced is not the same as correct: classing transport as cost of
    # sales balances perfectly but moves 498,841.10 out of operating expenses.
    wrong = derive(_lines(categories={"Transportation Charges": "cost_of_sales"}))
    assert wrong.is_valid
    assert wrong.figures["net_profit"].value == pytest.approx(REF["net_profit"], abs=0.01)
    assert wrong.figures["gross_profit"].value == pytest.approx(-51617.02, abs=0.01)


# ---- Ratios ------------------------------------------------------------------


def _expected_ratios():
    gross = REF["revenue"] - REF["cost_of_goods_sold"]
    return {
        IndicatorCode.CURRENT_RATIO: REF["total_assets"] / REF["current_liabilities"],
        IndicatorCode.QUICK_RATIO: (REF["total_assets"] - REF["inventory"])
        / REF["current_liabilities"],
        IndicatorCode.GROSS_PROFIT_MARGIN: gross / REF["revenue"] * 100,
        IndicatorCode.NET_PROFIT_MARGIN: REF["net_profit"] / REF["revenue"] * 100,
        IndicatorCode.RETURN_ON_ASSETS: REF["net_profit"] / REF["total_assets"] * 100,
        IndicatorCode.DEBT_TO_EQUITY: REF["total_liabilities"] / REF["total_equity"],
        IndicatorCode.DEBT_RATIO: REF["total_liabilities"] / REF["total_assets"],
        IndicatorCode.INTEREST_COVERAGE: None,  # no interest expense: not applicable
        IndicatorCode.ASSET_TURNOVER: REF["revenue"] / REF["total_assets"],
        IndicatorCode.DAYS_SALES_OUTSTANDING: 0.0,  # receivables are zero
    }


@pytest.mark.parametrize("code,expected", list(_expected_ratios().items()))
def test_ratio_matches_hand_calculation(inputs, code, expected):
    indicator = next(i for i in calculate_indicators(inputs) if i.code is code)
    if expected is None:
        assert indicator.value is None and not indicator.is_applicable
    else:
        assert indicator.value == pytest.approx(expected, rel=1e-6, abs=1e-9)


def test_inputs_pass_validation_with_no_errors(inputs):
    result = validate_financial_inputs(inputs)
    assert result.errors == []
    assert result.accounting_identity_ok


# ---- Scores ------------------------------------------------------------------


def test_scores_are_locked(inputs):
    # Verified by hand in ACCOUNTING_DATASET_VALIDATION.md (section 6). A
    # change here means a change in methodology and must be documented.
    health = assess(calculate_indicators(inputs), _default_thresholds())
    categories = {c.value: s for c, s in health.category_scores.items()}
    assert categories == {
        "liquidity": 100.0,
        "profitability": 40.94,
        "solvency": 100.0,
        "efficiency": 72.87,
    }
    assert health.overall_score == pytest.approx(78.45)
    assert health.classification.value == "sound"


def test_category_and_overall_scores_are_plain_averages(inputs):
    health = assess(calculate_indicators(inputs), _default_thresholds())
    for category, score in health.category_scores.items():
        members = [i.score for i in health.indicators
                   if i.category is category and i.score is not None]
        assert score == pytest.approx(sum(members) / len(members), abs=0.01)
    scored = [s for s in health.category_scores.values() if s is not None]
    assert health.overall_score == pytest.approx(sum(scored) / len(scored), abs=0.01)


def test_altman_benchmark_is_unavailable_without_retained_earnings(inputs):
    benchmark = calculate_altman_z_double_prime(inputs)
    assert benchmark.available is False
    assert benchmark.value is None
    assert "retained_earnings" in benchmark.missing_inputs


# ---- Edge cases ----------------------------------------------------------------


def test_a_shorter_period_scales_flow_ratios(derivation):
    year = FinancialInputs(**derivation.record_values(), period_days=365)
    quarter = FinancialInputs(**derivation.record_values(), period_days=91)
    turnover = {i.code: i.value for i in calculate_indicators(year)}
    quarterly = {i.code: i.value for i in calculate_indicators(quarter)}
    assert quarterly[IndicatorCode.ASSET_TURNOVER] == pytest.approx(
        turnover[IndicatorCode.ASSET_TURNOVER] * 365 / 91
    )
    # Margins do not depend on the period length.
    assert quarterly[IndicatorCode.GROSS_PROFIT_MARGIN] == pytest.approx(
        turnover[IndicatorCode.GROSS_PROFIT_MARGIN]
    )


def test_without_inventory_ledgers_the_quick_ratio_is_not_applicable():
    rows = [row for row in TALLY_TRIAL_BALANCE if row[1] != "Stock-in-Hand"]
    result = derive(_lines(rows))
    assert result.figures["inventory"].value is None
    inputs = FinancialInputs(**result.record_values(), period_days=365)
    quick = next(i for i in calculate_indicators(inputs)
                 if i.code is IndicatorCode.QUICK_RATIO)
    assert quick.value is None


def test_missing_revenue_ledger_is_reported():
    rows = [row for row in TALLY_TRIAL_BALANCE if row[1] != "Sales Accounts"]
    result = derive(_lines(rows))
    assert any("does not balance" in error for error in result.errors)
    assert any("No account is categorised as revenue" in w for w in result.warnings)


def test_an_account_on_the_wrong_side_is_flagged():
    rows = [row if row[0] != "Freight Inward" else ("Freight Inward", "Direct Expenses",
                                                    0, 31810.22)
            for row in TALLY_TRIAL_BALANCE]
    rows.append(("Suspense", "Capital", 63620.44, 0))  # keep it balanced
    result = derive(_lines(rows))
    assert any("opposite side" in w and "Freight Inward" in w for w in result.warnings)
