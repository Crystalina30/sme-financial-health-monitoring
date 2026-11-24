"""Tests for cross-field validation of financial data."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.financial_inputs import FinancialInputs
from app.services.validation_service import (
    check_accounting_identity,
    reconcile_income_statement,
    rounding_tolerance,
    validate_financial_inputs,
)
from tests.fixtures.financial_data import SOUND_COMPANY


def test_accounting_identity_holds_for_valid_data():
    ok, difference = check_accounting_identity(SOUND_COMPANY)
    assert ok
    assert difference == pytest.approx(0.0)


def test_accounting_identity_failure_is_detected():
    broken = SOUND_COMPANY.model_copy(update={"total_assets": 900_000})
    ok, difference = check_accounting_identity(broken)
    assert not ok
    assert difference == pytest.approx(100_000)


def test_accounting_identity_failure_blocks_the_record():
    broken = SOUND_COMPANY.model_copy(update={"total_assets": 900_000})
    result = validate_financial_inputs(broken)
    assert not result.is_valid
    assert not result.accounting_identity_ok
    assert any("Accounting identity" in message for message in result.errors)


# ---- Accounting identity: exact to RM0.01 ------------------------------------
# Total assets must equal total liabilities plus equity. There is no
# percentage tolerance: a RM1,000 gap on RM110,000 of assets is an error.


def _balance(assets, liabilities, equity):
    return SOUND_COMPANY.model_copy(update={
        "total_assets": assets,
        "total_liabilities": liabilities,
        "total_equity": equity,
        # Keep the other balance-sheet checks out of the way: current assets
        # and their parts are scaled to fit inside total assets.
        "current_assets": min(SOUND_COMPANY.current_assets, max(assets, 0)),
        "cash_and_equivalents": min(SOUND_COMPANY.current_assets, max(assets, 0)) * 0.4,
        "accounts_receivable": min(SOUND_COMPANY.current_assets, max(assets, 0)) * 0.3,
        "inventory": min(SOUND_COMPANY.current_assets, max(assets, 0)) * 0.2,
        "current_liabilities": min(SOUND_COMPANY.current_liabilities, max(liabilities, 0)),
    })


@pytest.mark.parametrize(
    "assets,liabilities,equity,holds",
    [
        (110_000, 60_000, 50_000, True),         # equal
        (110_000, 60_000, 49_000, False),        # RM1,000 short (passed under the old 1% rule)
        (110_000, 60_000, 49_999.99, True),      # RM0.01 short
        (110_000, 60_000, 49_999.98, False),     # RM0.02 short
        (110_000, 130_000, -20_000, True),       # negative equity, balanced
        (110_000, 130_000, -20_000.02, False),   # negative equity, out by RM0.02
        (800_000.50, 300_000, 500_000, False),   # RM0.50: no longer tolerated
    ],
)
def test_accounting_identity_to_the_cent(assets, liabilities, equity, holds):
    ok, _ = check_accounting_identity(_balance(assets, liabilities, equity))
    assert ok is holds
    result = validate_financial_inputs(_balance(assets, liabilities, equity))
    assert result.accounting_identity_ok is holds
    assert result.is_valid is holds


def test_difference_is_exact_despite_floating_point():
    # 60,000 + 49,999.99 in binary floating point is not exactly 109,999.99;
    # the check works on decimals, so the gap is exactly 0.01.
    ok, difference = check_accounting_identity(_balance(110_000, 60_000, 49_999.99))
    assert ok
    assert difference == 0.01


def test_failure_message_states_the_exact_discrepancy():
    result = validate_financial_inputs(_balance(110_000, 60_000, 49_000))
    message = next(m for m in result.errors if "Accounting identity" in m)
    assert "110,000.00" in message
    assert "109,000.00" in message
    assert "difference 1,000.00" in message
    assert "within 0.01" in message


def test_failing_figures_are_not_adjusted():
    data = _balance(110_000, 60_000, 49_000)
    validate_financial_inputs(data)
    assert (data.total_assets, data.total_liabilities, data.total_equity) == (
        110_000, 60_000, 49_000,
    )


def test_rounded_statements_need_an_explicit_presentation_unit():
    # A statement published in RM'000, entered as full amounts: three rounded
    # figures can be out by up to 3 x 500 = 1,500. Accepted only when the
    # unit is stated; exact figures stay at RM0.01.
    rounded = _balance(110_000, 60_000, 49_000)
    assert not check_accounting_identity(rounded)[0]
    assert check_accounting_identity(rounded, presentation_unit=Decimal("1000"))[0]
    assert check_accounting_identity(
        _balance(110_000, 60_000, 48_500), presentation_unit=Decimal("1000"))[0]
    assert not check_accounting_identity(
        _balance(110_000, 60_000, 48_499), presentation_unit=Decimal("1000"))[0]
    # Whole-ringgit statements: up to 1.50.
    assert check_accounting_identity(
        _balance(110_000, 60_000, 49_998.50), presentation_unit=Decimal("1"))[0]
    assert not check_accounting_identity(
        _balance(110_000, 60_000, 49_998.49), presentation_unit=Decimal("1"))[0]
    with pytest.raises(ValueError, match="Unsupported presentation unit"):
        check_accounting_identity(rounded, presentation_unit=Decimal("0.05"))


def test_valid_data_produces_no_errors():
    result = validate_financial_inputs(SOUND_COMPANY)
    assert result.is_valid
    assert result.errors == []


def test_current_assets_above_total_assets_is_rejected():
    broken = SOUND_COMPANY.model_copy(
        update={"current_assets": 900_000, "total_assets": 800_000}
    )
    assert not validate_financial_inputs(broken).is_valid


def test_inventory_above_current_assets_is_rejected():
    broken = SOUND_COMPANY.model_copy(update={"inventory": 400_000})
    assert not validate_financial_inputs(broken).is_valid


def test_receivables_above_current_assets_is_rejected():
    broken = SOUND_COMPANY.model_copy(update={"accounts_receivable": 400_000})
    assert not validate_financial_inputs(broken).is_valid


def test_a_loss_is_information_not_a_data_problem():
    # Cost above revenue gives a negative gross profit. With net profit
    # consistent with its lines, that is a loss, not an inconsistency.
    loss_making = SOUND_COMPANY.model_copy(update={"cost_of_goods_sold": 1_100_000})
    implied = reconcile_income_statement(loss_making).calculated_net_profit
    loss_making = loss_making.model_copy(update={"net_profit": float(implied)})
    result = validate_financial_inputs(loss_making)
    assert result.is_valid
    assert result.warnings == []
    assert any("Gross profit is negative" in note for note in result.info)


def test_negative_revenue_is_rejected_at_the_field_level():
    with pytest.raises(ValidationError):
        FinancialInputs(
            revenue=-1,
            cost_of_goods_sold=0,
            operating_expenses=0,
            net_profit=0,
            current_assets=0,
            total_assets=0,
            current_liabilities=0,
            total_liabilities=0,
            total_equity=0,
        )


def test_negative_asset_balance_is_rejected_at_the_field_level():
    with pytest.raises(ValidationError):
        FinancialInputs(
            revenue=0,
            cost_of_goods_sold=0,
            operating_expenses=0,
            net_profit=0,
            current_assets=-5,
            total_assets=0,
            current_liabilities=0,
            total_liabilities=0,
            total_equity=0,
        )


def test_validation_notes_are_joined_for_storage():
    broken = SOUND_COMPANY.model_copy(update={"total_assets": 900_000})
    result = validate_financial_inputs(broken)
    assert result.notes is not None
    assert "Accounting identity" in result.notes


# ---- Income statement reconciliation ------------------------------------------


def test_reconciliation_of_the_reported_inconsistency():
    data = SOUND_COMPANY.model_copy(update={
        "revenue": 1_200, "cost_of_goods_sold": 780_000, "operating_expenses": 260_000,
        "interest_expense": 30_000, "tax_expense": 30_000, "net_profit": 100_000,
    })
    rec = reconcile_income_statement(data)
    assert rec.gross_profit == Decimal("-778800.00")
    assert rec.operating_profit == Decimal("-1038800.00")
    assert rec.calculated_net_profit == Decimal("-1098800.00")
    assert rec.difference == Decimal("1198800.00")
    assert not rec.reconciled
    result = validate_financial_inputs(data)
    assert result.is_valid  # stored for correction, not blocked
    assert any("1,198,800.00" in w for w in result.warnings)


def test_reconciliation_uses_every_supported_line():
    data = SOUND_COMPANY.model_copy(update={
        "revenue": 1_000_000, "cost_of_goods_sold": 600_000, "other_operating_income": 15_000,
        "operating_expenses": 250_000, "other_income": 8_000, "other_expenses": 3_000,
        "interest_expense": 20_000, "tax_expense": -5_000,  # a tax credit
        "net_profit": 155_000,
    })
    rec = reconcile_income_statement(data)
    assert rec.operating_profit == Decimal("165000.00")
    assert rec.profit_before_tax == Decimal("150000.00")
    assert rec.calculated_net_profit == Decimal("155000.00")
    assert rec.reconciled


def test_reconciliation_is_exact_in_decimals():
    data = SOUND_COMPANY.model_copy(update={
        "revenue": 0.3, "cost_of_goods_sold": 0.1, "operating_expenses": 0.1,
        "interest_expense": 0, "tax_expense": 0, "net_profit": 0.1,
    })
    rec = reconcile_income_statement(data)
    assert rec.difference == Decimal("0.00")


def test_rounding_tolerance_policy():
    assert rounding_tolerance(Decimal("0.01"), 9) == Decimal("0.01")  # exact stays exact
    assert rounding_tolerance(Decimal("1000"), 3) == Decimal("1500")
    assert rounding_tolerance(Decimal("1000000"), 5) == Decimal("2500000")


def test_net_profit_tolerance_counts_the_rounded_lines():
    # Six non-zero lines plus the reported net profit, rounded to RM'000:
    # up to 7 x 500 = 3,500 can be rounding.
    data = SOUND_COMPANY.model_copy(update={
        "revenue": 1_235_000, "cost_of_goods_sold": 801_000, "operating_expenses": 262_000,
        "interest_expense": 31_000, "tax_expense": 29_000,
    })
    implied = 1_235_000 - 801_000 - 262_000 - 31_000 - 29_000
    off_by_rounding = data.model_copy(update={"net_profit": implied + 2_000})
    off_by_more = data.model_copy(update={"net_profit": implied + 3_501})
    assert reconcile_income_statement(off_by_rounding, Decimal("1000")).reconciled
    assert not reconcile_income_statement(off_by_more, Decimal("1000")).reconciled
    assert not reconcile_income_statement(off_by_rounding).reconciled  # exact: RM0.01


# ---- Audit items 4 and 6 -----------------------------------------------------------------


def test_current_asset_parts_cannot_exceed_current_assets():
    # The audit's reproduction: cash 80k + receivables 70k > current assets 100k.
    data = SOUND_COMPANY.model_copy(update={
        "cash_and_equivalents": 80_000, "accounts_receivable": 70_000, "inventory": None,
        "current_assets": 100_000, "total_assets": 200_000, "current_liabilities": 50_000,
        "total_liabilities": 100_000, "total_equity": 100_000})
    result = validate_financial_inputs(data)
    assert not result.is_valid
    message = next(e for e in result.errors if "together" in e)
    assert "150,000.00" in message and "100,000.00" in message


def test_parts_equal_to_current_assets_are_fine():
    data = SOUND_COMPANY.model_copy(update={
        "cash_and_equivalents": 50_000, "accounts_receivable": 30_000, "inventory": 20_000,
        "current_assets": 100_000, "total_assets": 200_000, "current_liabilities": 50_000,
        "total_liabilities": 100_000, "total_equity": 100_000})
    assert not [e for e in validate_financial_inputs(data).errors if "together" in e]


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_inputs_are_refused_by_the_model(value):
    with pytest.raises(ValidationError):
        SOUND_COMPANY.model_copy(update={}).__class__(
            **{**SOUND_COMPANY.model_dump(), "revenue": value})


def test_to_money_refuses_non_finite_values():
    from app.services.validation_service import to_money
    with pytest.raises(ValueError):
        to_money(float("inf"))
