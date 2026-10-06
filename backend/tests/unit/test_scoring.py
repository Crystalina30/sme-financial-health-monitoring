"""Tests for threshold-based scoring, category and overall scores."""

import pytest

from app.models.enums import (
    HealthClassification,
    IndicatorCategory,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import (
    SCORE_AT_CONCERN,
    SCORE_AT_DISTRESS,
    ThresholdSetting,
    assess,
    calculate_category_scores,
    calculate_overall_score,
    classify,
    determine_status,
    score_indicator_value,
    score_indicators,
)
from app.services.threshold_service import DEFAULT_THRESHOLDS
from tests.fixtures.financial_data import (
    DISTRESSED_COMPANY,
    SERVICE_COMPANY_NO_INVENTORY,
    SOUND_COMPANY,
)

HIGHER_IS_BETTER = ThresholdSetting(
    indicator_code=IndicatorCode.CURRENT_RATIO,
    direction=ThresholdDirection.HIGHER_IS_BETTER,
    concern_threshold=1.5,
    distress_threshold=1.0,
    source_reference="test",
    description="test",
)

LOWER_IS_BETTER = ThresholdSetting(
    indicator_code=IndicatorCode.DEBT_RATIO,
    direction=ThresholdDirection.LOWER_IS_BETTER,
    concern_threshold=0.6,
    distress_threshold=0.8,
    source_reference="test",
    description="test",
)


def _default_settings() -> dict[IndicatorCode, ThresholdSetting]:
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


# ---------------------------------------------------------------------------
# Score anchors
# ---------------------------------------------------------------------------


def test_score_at_concern_threshold_is_sixty():
    assert score_indicator_value(1.5, HIGHER_IS_BETTER) == pytest.approx(SCORE_AT_CONCERN)


def test_score_at_distress_threshold_is_forty():
    assert score_indicator_value(1.0, HIGHER_IS_BETTER) == pytest.approx(SCORE_AT_DISTRESS)


def test_healthy_value_scores_above_sixty():
    assert score_indicator_value(2.0, HIGHER_IS_BETTER) == pytest.approx(100.0)


def test_score_is_clamped_to_one_hundred():
    assert score_indicator_value(99.0, HIGHER_IS_BETTER) == 100.0


def test_score_is_clamped_to_zero():
    assert score_indicator_value(-50.0, HIGHER_IS_BETTER) == 0.0


def test_lower_is_better_anchors_match():
    assert score_indicator_value(0.6, LOWER_IS_BETTER) == pytest.approx(SCORE_AT_CONCERN)
    assert score_indicator_value(0.8, LOWER_IS_BETTER) == pytest.approx(SCORE_AT_DISTRESS)


def test_lower_is_better_rewards_smaller_values():
    assert score_indicator_value(0.3, LOWER_IS_BETTER) > score_indicator_value(
        0.5, LOWER_IS_BETTER
    )


def test_higher_is_better_rewards_larger_values():
    assert score_indicator_value(1.8, HIGHER_IS_BETTER) > score_indicator_value(
        1.6, HIGHER_IS_BETTER
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_sound_concern_distress_higher_is_better():
    assert determine_status(2.0, HIGHER_IS_BETTER) is IndicatorStatus.SOUND
    assert determine_status(1.2, HIGHER_IS_BETTER) is IndicatorStatus.CONCERN
    assert determine_status(0.8, HIGHER_IS_BETTER) is IndicatorStatus.DISTRESS


def test_status_at_threshold_counts_as_reached():
    assert determine_status(1.5, HIGHER_IS_BETTER) is IndicatorStatus.CONCERN
    assert determine_status(1.0, HIGHER_IS_BETTER) is IndicatorStatus.DISTRESS


def test_status_sound_concern_distress_lower_is_better():
    assert determine_status(0.3, LOWER_IS_BETTER) is IndicatorStatus.SOUND
    assert determine_status(0.7, LOWER_IS_BETTER) is IndicatorStatus.CONCERN
    assert determine_status(0.9, LOWER_IS_BETTER) is IndicatorStatus.DISTRESS


# ---------------------------------------------------------------------------
# Not applicable handling
# ---------------------------------------------------------------------------


def test_not_applicable_indicator_scores_none_not_zero():
    indicators = calculate_indicators(SERVICE_COMPANY_NO_INVENTORY)
    scored = {item.code: item for item in score_indicators(indicators, _default_settings())}

    quick = scored[IndicatorCode.QUICK_RATIO]
    assert quick.score is None
    assert quick.status is IndicatorStatus.NOT_APPLICABLE


def test_category_score_uses_applicable_indicators_only():
    indicators = calculate_indicators(SERVICE_COMPANY_NO_INVENTORY)
    scored = score_indicators(indicators, _default_settings())
    categories = calculate_category_scores(scored)

    current_ratio = next(
        item for item in scored if item.code is IndicatorCode.CURRENT_RATIO
    )
    # Quick ratio is N/A, so liquidity is the current ratio alone.
    assert categories[IndicatorCategory.LIQUIDITY] == pytest.approx(current_ratio.score)


def test_category_with_no_applicable_indicators_scores_none():
    categories = calculate_category_scores([])
    assert all(score is None for score in categories.values())


# ---------------------------------------------------------------------------
# Aggregation and classification
# ---------------------------------------------------------------------------


def test_overall_score_is_the_mean_of_category_scores():
    categories = {
        IndicatorCategory.LIQUIDITY: 80.0,
        IndicatorCategory.PROFITABILITY: 60.0,
        IndicatorCategory.SOLVENCY: 40.0,
        IndicatorCategory.EFFICIENCY: 20.0,
    }
    assert calculate_overall_score(categories) == pytest.approx(50.0)


def test_overall_score_ignores_not_applicable_categories():
    categories = {
        IndicatorCategory.LIQUIDITY: 80.0,
        IndicatorCategory.PROFITABILITY: 60.0,
        IndicatorCategory.SOLVENCY: None,
        IndicatorCategory.EFFICIENCY: None,
    }
    assert calculate_overall_score(categories) == pytest.approx(70.0)


def test_overall_score_is_none_when_nothing_applies():
    categories = dict.fromkeys(IndicatorCategory, None)
    assert calculate_overall_score(categories) is None


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, HealthClassification.SOUND),
        (60.0, HealthClassification.SOUND),
        (59.99, HealthClassification.VULNERABLE),
        (40.0, HealthClassification.VULNERABLE),
        (39.99, HealthClassification.DISTRESSED),
        (0.0, HealthClassification.DISTRESSED),
    ],
)
def test_classification_bands(score, expected):
    assert classify(score) is expected


def test_sound_company_classifies_as_sound():
    result = assess(calculate_indicators(SOUND_COMPANY), _default_settings())
    assert result.classification is HealthClassification.SOUND
    assert result.overall_score >= 60


def test_distressed_company_does_not_classify_as_sound():
    result = assess(calculate_indicators(DISTRESSED_COMPANY), _default_settings())
    assert result.classification is not HealthClassification.SOUND
