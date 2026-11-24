"""Tests for the Altman Z'' distress benchmark."""

import pytest

from app.services.benchmark_service import (
    COEFFICIENTS,
    DISTRESS_CUTOFF,
    calculate_altman_z_double_prime,
)
from tests.fixtures.financial_data import SOUND_COMPANY


def test_coefficients_match_the_published_model():
    # Altman (2002), pp. 17-18.
    assert COEFFICIENTS == {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05}
    assert DISTRESS_CUTOFF == 1.10


def test_z_double_prime_by_hand():
    data = SOUND_COMPANY.model_copy(update={"retained_earnings": 200_000})
    # X1 = (300000 - 120000) / 800000 = 0.225
    # X2 = 200000 / 800000            = 0.25
    # X3 = 180000 / 800000            = 0.225   (operating profit as EBIT)
    # X4 = 500000 / 300000            = 1.6667
    expected = 6.56 * 0.225 + 3.26 * 0.25 + 6.72 * 0.225 + 1.05 * (500_000 / 300_000)
    result = calculate_altman_z_double_prime(data)
    assert result.available
    assert result.value == pytest.approx(round(expected, 2))
    assert result.components["x3"] == pytest.approx(0.225)
    assert result.below_distress_cutoff is False


def test_missing_retained_earnings_is_never_treated_as_zero():
    result = calculate_altman_z_double_prime(SOUND_COMPANY)
    assert not result.available
    assert result.value is None
    assert result.missing_inputs == ["retained_earnings"]


def test_negative_retained_earnings_are_allowed():
    data = SOUND_COMPANY.model_copy(update={"retained_earnings": -2_000_000})
    result = calculate_altman_z_double_prime(data)
    assert result.available
    assert result.components["x2"] == pytest.approx(-2.5)
    assert result.below_distress_cutoff is True


def test_zero_total_assets_makes_the_benchmark_unavailable():
    data = SOUND_COMPANY.model_copy(update={"retained_earnings": 0, "total_assets": 0})
    result = calculate_altman_z_double_prime(data)
    assert not result.available
    assert "Total assets" in result.reason


def test_zero_liabilities_makes_the_benchmark_unavailable():
    data = SOUND_COMPANY.model_copy(update={"retained_earnings": 0, "total_liabilities": 0})
    result = calculate_altman_z_double_prime(data)
    assert not result.available
    assert "X4" in result.reason


def test_cutoff_is_judged_on_the_value_shown():
    # Retained earnings chosen so Z'' rounds to exactly 1.10: shown as 1.10,
    # it must be reported as not below the cut-off.
    data = SOUND_COMPANY.model_copy(update={"retained_earnings": 0})
    base = calculate_altman_z_double_prime(data).value
    needed = (1.10 - base) / 3.26 * 800_000
    result = calculate_altman_z_double_prime(
        SOUND_COMPANY.model_copy(update={"retained_earnings": needed})
    )
    assert result.value == pytest.approx(1.10)
    assert result.below_distress_cutoff is False
