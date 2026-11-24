"""Tests for scoring methodology 2.0.

Covers the explicit four-point normalisation (and its exact equivalence with
methodology 1.0 under the default reference points), negative equity, missing
data, reporting-period scaling, the geometric-mean robustness comparison,
effective indicator weights and the data-quality notes.
"""

import importlib.util
import math
from pathlib import Path

import pytest

from app.models.enums import (
    HealthClassification,
    IndicatorCategory,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.assessment_service import describe_data_quality
from app.services.financial_calculation_service import (
    calculate_asset_turnover,
    calculate_days_sales_outstanding,
    calculate_indicators,
)
from app.services.scoring_service import (
    InvalidThresholdError,
    ReferencePoints,
    ThresholdSetting,
    assess,
    calculate_geometric_overall_score,
    calculate_indicator_weights,
    classify,
    compare_aggregations,
    default_reference_points,
    reference_points_for,
    score_indicator_value,
    score_indicators,
    validate_reference_points,
)
from app.services.threshold_service import DEFAULT_THRESHOLDS
from tests.fixtures.financial_data import (
    DISTRESSED_COMPANY,
    SERVICE_COMPANY_NO_INVENTORY,
    SOUND_COMPANY,
)

HIGHER = ThresholdDirection.HIGHER_IS_BETTER
LOWER = ThresholdDirection.LOWER_IS_BETTER


def _settings() -> dict[IndicatorCode, ThresholdSetting]:
    return {
        entry["indicator_code"]: ThresholdSetting(
            indicator_code=entry["indicator_code"],
            direction=entry["direction"],
            concern_threshold=entry["concern_threshold"],
            distress_threshold=entry["distress_threshold"],
            source_reference=entry["source_reference"],
            description=entry["description"],
        )
        for entry in DEFAULT_THRESHOLDS
    }


def _methodology_1_score(value: float, threshold: ThresholdSetting) -> float:
    """The methodology-1.0 formula, kept here only to prove equivalence."""
    concern, distress = threshold.concern_threshold, threshold.distress_threshold
    span = abs(concern - distress)
    if threshold.direction is HIGHER:
        offset = (value - concern) / span
    else:
        offset = (concern - value) / span
    raw = 60 + offset * 40 if offset >= 0 else 60 + offset * 20
    return max(0.0, min(100.0, raw))


def _custom(direction, floor, distress, concern, target) -> ThresholdSetting:
    return ThresholdSetting(
        indicator_code=IndicatorCode.CURRENT_RATIO,
        direction=direction,
        concern_threshold=concern,
        distress_threshold=distress,
        source_reference="test",
        description="test",
        floor_value=floor,
        target_value=target,
    )


# ---------------------------------------------------------------------------
# Four-point normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", DEFAULT_THRESHOLDS, ids=lambda e: e["indicator_code"].value)
def test_default_reference_points_reproduce_methodology_1(entry):
    threshold = _settings()[entry["indicator_code"]]
    c, d = entry["concern_threshold"], entry["distress_threshold"]
    span = abs(c - d)
    # Sweep well past both ends of the scale, including every anchor.
    for step in range(-80, 81):
        value = c + step * span / 20
        assert score_indicator_value(value, threshold) == pytest.approx(
            _methodology_1_score(value, threshold), abs=1e-9
        ), value


def test_default_reference_points_higher_is_better():
    # Current ratio: concern 1.5, distress 1.0, span 0.5.
    assert default_reference_points(HIGHER, 1.5, 1.0) == pytest.approx((0.0, 2.0))


def test_default_reference_points_lower_is_better():
    # Days sales outstanding: concern 60, distress 90, span 30.
    assert default_reference_points(LOWER, 60.0, 90.0) == pytest.approx((150.0, 30.0))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1.0, 0.0), (0.0, 0.0), (0.5, 20.0), (1.0, 40.0), (1.25, 50.0), (1.5, 60.0),
     (2.0, 80.0), (2.5, 100.0), (9.0, 100.0)],
)
def test_explicit_points_higher_is_better(value, expected):
    threshold = _custom(HIGHER, floor=0.0, distress=1.0, concern=1.5, target=2.5)
    assert score_indicator_value(value, threshold) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(200.0, 0.0), (150.0, 0.0), (120.0, 20.0), (90.0, 40.0), (75.0, 50.0), (60.0, 60.0),
     (45.0, 80.0), (30.0, 100.0), (0.0, 100.0)],
)
def test_explicit_points_lower_is_better(value, expected):
    threshold = _custom(LOWER, floor=150.0, distress=90.0, concern=60.0, target=30.0)
    assert score_indicator_value(value, threshold) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("direction", "points"),
    [
        (HIGHER, (1.0, 1.0, 1.5, 2.0)),  # floor equals distress
        (HIGHER, (0.0, 1.5, 1.0, 2.0)),  # distress above concern
        (HIGHER, (0.0, 1.0, 1.5, 1.5)),  # target equals concern
        (LOWER, (30.0, 90.0, 60.0, 150.0)),  # floor and target swapped
        (LOWER, (150.0, 60.0, 60.0, 30.0)),  # distress equals concern
    ],
)
def test_reference_points_must_be_strictly_ordered(direction, points):
    with pytest.raises(InvalidThresholdError):
        validate_reference_points(direction, ReferencePoints(*points))


def test_invalid_configuration_makes_only_that_indicator_not_applicable():
    settings = _settings()
    settings[IndicatorCode.CURRENT_RATIO] = _custom(HIGHER, 2.0, 1.0, 1.5, 3.0)
    scored = score_indicators(calculate_indicators(SOUND_COMPANY), settings)
    current = next(item for item in scored if item.code is IndicatorCode.CURRENT_RATIO)
    assert current.score is None
    assert current.status is IndicatorStatus.NOT_APPLICABLE
    assert "invalid" in current.note
    assert sum(1 for item in scored if item.score is not None) == 9


def test_reference_points_for_fills_only_missing_values():
    threshold = _custom(HIGHER, floor=None, distress=1.0, concern=1.5, target=3.0)
    points = reference_points_for(threshold)
    assert points.floor == pytest.approx(0.0)
    assert points.target == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Negative equity and missing data
# ---------------------------------------------------------------------------


def test_negative_equity_scores_debt_to_equity_as_worst_case():
    insolvent = SOUND_COMPANY.model_copy(
        update={"total_equity": -50_000, "total_liabilities": 850_000}
    )
    scored = score_indicators(calculate_indicators(insolvent), _settings())
    debt_to_equity = next(item for item in scored if item.code is IndicatorCode.DEBT_TO_EQUITY)
    assert debt_to_equity.value is None
    assert debt_to_equity.score == 0.0
    assert debt_to_equity.status is IndicatorStatus.DISTRESS
    assert "negative" in debt_to_equity.note


def test_negative_equity_cannot_raise_the_solvency_score():
    insolvent = SOUND_COMPANY.model_copy(
        update={"total_equity": -50_000, "total_liabilities": 850_000}
    )
    result = assess(calculate_indicators(insolvent), _settings())
    solvency_indicators = [
        item.score for item in result.indicators if item.category is IndicatorCategory.SOLVENCY
    ]
    # All three count, and the worst case is included at zero.
    assert len(solvency_indicators) == 3
    assert result.category_scores[IndicatorCategory.SOLVENCY] == pytest.approx(
        round(sum(solvency_indicators) / 3, 2)
    )


def test_zero_equity_with_no_liabilities_stays_not_applicable():
    empty = SOUND_COMPANY.model_copy(update={"total_equity": 0, "total_liabilities": 0})
    indicators = calculate_indicators(empty)
    debt_to_equity = next(item for item in indicators if item.code is IndicatorCode.DEBT_TO_EQUITY)
    assert not debt_to_equity.is_applicable
    assert not debt_to_equity.worst_case


def test_no_score_classifies_as_insufficient_data_not_distressed():
    assert classify(None) is HealthClassification.INSUFFICIENT_DATA


def test_figures_that_support_no_indicator_give_insufficient_data():
    nothing = SOUND_COMPANY.model_copy(
        update={
            "revenue": 0, "cost_of_goods_sold": 0, "operating_expenses": 0,
            "interest_expense": 0, "net_profit": 0, "accounts_receivable": 0,
            "inventory": None, "current_assets": 0, "total_assets": 0,
            "current_liabilities": 0, "total_liabilities": 0, "total_equity": 0,
        }
    )
    result = assess(calculate_indicators(nothing), _settings())
    assert result.overall_score is None
    assert result.classification is HealthClassification.INSUFFICIENT_DATA
    assert result.robustness.geometric_score is None


# ---------------------------------------------------------------------------
# Reporting-period length
# ---------------------------------------------------------------------------


def test_unknown_period_length_assumes_a_year():
    assert calculate_days_sales_outstanding(SOUND_COMPANY) == pytest.approx(
        90_000 / 1_000_000 * 365
    )
    assert calculate_asset_turnover(SOUND_COMPANY) == pytest.approx(1_000_000 / 800_000)


def test_days_sales_outstanding_uses_the_period_length():
    quarter = SOUND_COMPANY.model_copy(update={"period_days": 91})
    assert calculate_days_sales_outstanding(quarter) == pytest.approx(90_000 / 1_000_000 * 91)


def test_asset_turnover_is_annualised_from_the_period_length():
    quarter = SOUND_COMPANY.model_copy(update={"period_days": 91})
    assert calculate_asset_turnover(quarter) == pytest.approx(
        1_000_000 * 365 / 91 / 800_000
    )


def test_a_365_day_period_matches_the_annual_assumption():
    year = SOUND_COMPANY.model_copy(update={"period_days": 365})
    assert calculate_days_sales_outstanding(year) == pytest.approx(
        calculate_days_sales_outstanding(SOUND_COMPANY)
    )
    assert calculate_asset_turnover(year) == pytest.approx(calculate_asset_turnover(SOUND_COMPANY))


def test_period_length_only_affects_the_two_flow_ratios():
    quarter = SOUND_COMPANY.model_copy(update={"period_days": 91})
    yearly = {item.code: item.value for item in calculate_indicators(SOUND_COMPANY)}
    quarterly = {item.code: item.value for item in calculate_indicators(quarter)}
    changed = {code for code in yearly if yearly[code] != pytest.approx(quarterly[code])}
    assert changed == {IndicatorCode.DAYS_SALES_OUTSTANDING, IndicatorCode.ASSET_TURNOVER}


# ---------------------------------------------------------------------------
# Robustness comparison and weights
# ---------------------------------------------------------------------------


def _categories(liquidity, profitability, solvency, efficiency):
    return {
        IndicatorCategory.LIQUIDITY: liquidity,
        IndicatorCategory.PROFITABILITY: profitability,
        IndicatorCategory.SOLVENCY: solvency,
        IndicatorCategory.EFFICIENCY: efficiency,
    }


def test_geometric_mean_of_equal_scores_equals_the_arithmetic_mean():
    assert calculate_geometric_overall_score(_categories(70, 70, 70, 70)) == pytest.approx(70)


def test_geometric_mean_formula():
    expected = math.exp((math.log(50.16) + math.log(79.54) + math.log(62.36) + math.log(61.57)) / 4)
    assert calculate_geometric_overall_score(
        _categories(50.16, 79.54, 62.36, 61.57)
    ) == pytest.approx(round(expected, 2))


def test_zero_category_makes_the_geometric_mean_zero_and_is_flagged():
    comparison = compare_aggregations(_categories(0.0, 90.0, 90.0, 90.0))
    assert comparison.geometric_score == 0.0
    assert comparison.has_zero_category
    assert comparison.arithmetic_score == pytest.approx(67.5)
    assert comparison.classifications_differ


def test_geometric_mean_ignores_not_applicable_categories():
    assert calculate_geometric_overall_score(_categories(64, None, 81, None)) == pytest.approx(72)


def test_weakest_category_ties_go_to_the_first_in_order():
    comparison = compare_aggregations(_categories(55, 80, 55, 70))
    assert comparison.weakest_category is IndicatorCategory.LIQUIDITY
    assert comparison.weakest_category_score == 55


def test_arithmetic_is_never_below_geometric():
    comparison = compare_aggregations(_categories(50.16, 79.54, 62.36, 61.57))
    assert comparison.difference >= 0
    assert comparison.classifications_differ is False


def test_effective_weights_with_all_ten_indicators():
    scored = score_indicators(calculate_indicators(SOUND_COMPANY), _settings())
    weights = calculate_indicator_weights(scored)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights[IndicatorCode.CURRENT_RATIO] == pytest.approx(0.125)
    assert weights[IndicatorCode.NET_PROFIT_MARGIN] == pytest.approx(1 / 12)
    assert weights[IndicatorCode.DAYS_SALES_OUTSTANDING] == pytest.approx(0.125)


def test_effective_weights_shift_when_an_indicator_is_missing():
    scored = score_indicators(calculate_indicators(SERVICE_COMPANY_NO_INVENTORY), _settings())
    weights = calculate_indicator_weights(scored)
    assert IndicatorCode.QUICK_RATIO not in weights
    # The current ratio now carries the whole liquidity quarter.
    assert weights[IndicatorCode.CURRENT_RATIO] == pytest.approx(0.25)
    assert sum(weights.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Data-quality notes
# ---------------------------------------------------------------------------


def test_short_period_is_flagged():
    month = SOUND_COMPANY.model_copy(update={"period_days": 31})
    notes = describe_data_quality(month, assess(calculate_indicators(month), _settings()))
    assert any("31 days" in note for note in notes)


def test_annual_period_is_not_flagged():
    year = SOUND_COMPANY.model_copy(update={"period_days": 366})
    notes = describe_data_quality(year, assess(calculate_indicators(year), _settings()))
    assert notes == []


def test_missing_indicators_are_explained():
    data = SERVICE_COMPANY_NO_INVENTORY.model_copy(update={"period_days": 365})
    notes = describe_data_quality(data, assess(calculate_indicators(data), _settings()))
    assert any("8 of 10 indicators" in note for note in notes)


def test_distressed_fixture_still_classifies_below_sound():
    result = assess(calculate_indicators(DISTRESSED_COMPANY), _settings())
    assert result.classification is not HealthClassification.SOUND


# ---------------------------------------------------------------------------
# Migration and seed data agree
# ---------------------------------------------------------------------------


def test_migration_texts_match_the_seeded_defaults():
    path = Path(__file__).parents[2] / "alembic" / "versions" / "5a1d9c3e7f20_scoring_methodology_v2.py"
    spec = importlib.util.spec_from_file_location("migration_v2", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    for entry in DEFAULT_THRESHOLDS:
        _old, new_source, basis, description = migration._TEXTS[entry["indicator_code"].value]
        assert new_source == entry["source_reference"]
        assert basis == entry["basis"]
        if description is not None:
            assert description == entry["description"]
