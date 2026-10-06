"""Tests for cross-field validation of financial data."""

import pytest
from pydantic import ValidationError

from app.schemas.financial_inputs import FinancialInputs
from app.services.validation_service import (
    check_accounting_identity,
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


def test_small_rounding_difference_is_tolerated():
    rounded = SOUND_COMPANY.model_copy(update={"total_assets": 800_000.50})
    result = validate_financial_inputs(rounded)
    assert result.accounting_identity_ok


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


def test_cost_above_revenue_is_a_warning_not_an_error():
    loss_making = SOUND_COMPANY.model_copy(update={"cost_of_goods_sold": 1_100_000})
    result = validate_financial_inputs(loss_making)
    assert result.warnings
    assert any("negative gross profit" in warning for warning in result.warnings)


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
