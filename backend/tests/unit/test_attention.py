"""Tests for identification of indicators requiring attention."""

from app.models.enums import (
    AttentionReason,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.attention_service import (
    calculate_period_change,
    identify_attention,
)
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import ThresholdSetting, score_indicators
from app.services.threshold_service import DEFAULT_THRESHOLDS
from tests.fixtures.financial_data import DISTRESSED_COMPANY, SOUND_COMPANY

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


# ---------------------------------------------------------------------------
# Reporting-period change
# ---------------------------------------------------------------------------


def test_fall_in_higher_is_better_indicator_is_unfavourable():
    change = calculate_period_change(1.8, 2.5, HIGHER)
    assert change.is_unfavourable
    assert change.change_percent < 0


def test_rise_in_higher_is_better_indicator_is_favourable():
    assert not calculate_period_change(2.5, 1.8, HIGHER).is_unfavourable


def test_rise_in_lower_is_better_indicator_is_unfavourable():
    assert calculate_period_change(0.9, 0.5, LOWER).is_unfavourable


def test_fall_in_lower_is_better_indicator_is_favourable():
    assert not calculate_period_change(0.5, 0.9, LOWER).is_unfavourable


def test_small_movement_is_below_the_threshold():
    # A 4 per cent fall, under the 10 per cent default.
    assert not calculate_period_change(2.40, 2.50, HIGHER).is_unfavourable


def test_movement_exactly_at_the_threshold_counts():
    # A 10 per cent fall.
    assert calculate_period_change(2.25, 2.50, HIGHER).is_unfavourable


def test_no_previous_value_reports_no_movement():
    change = calculate_period_change(2.5, None, HIGHER)
    assert change.change is None
    assert not change.is_unfavourable


def test_zero_previous_value_reports_no_proportional_change():
    change = calculate_period_change(2.5, 0.0, HIGHER)
    assert change.change_percent is None
    assert not change.is_unfavourable


# ---------------------------------------------------------------------------
# Prioritisation
# ---------------------------------------------------------------------------


def test_every_indicator_is_returned():
    scored = score_indicators(calculate_indicators(SOUND_COMPANY), _settings())
    assert len(identify_attention(scored)) == 10


def test_distress_breach_outranks_concern_breach():
    scored = score_indicators(calculate_indicators(DISTRESSED_COMPANY), _settings())
    items = identify_attention(scored)
    priorities = [item.priority for item in items]
    assert priorities == sorted(priorities)

    distress_items = [
        item for item in items if item.reason is AttentionReason.DISTRESS_BREACH
    ]
    concern_items = [
        item for item in items if item.reason is AttentionReason.CONCERN_BREACH
    ]
    if distress_items and concern_items:
        assert items.index(distress_items[0]) < items.index(concern_items[0])


def test_sound_indicator_with_unfavourable_movement_is_flagged():
    scored = score_indicators(calculate_indicators(SOUND_COMPANY), _settings())
    previous = {IndicatorCode.CURRENT_RATIO: 5.0}  # fell to 2.5, a 50% drop
    items = {item.code: item for item in identify_attention(scored, previous)}

    current_ratio = items[IndicatorCode.CURRENT_RATIO]
    assert current_ratio.status is IndicatorStatus.SOUND
    assert current_ratio.reason is AttentionReason.UNFAVOURABLE_MOVEMENT


def test_breach_takes_precedence_over_movement_as_the_reason():
    scored = score_indicators(calculate_indicators(DISTRESSED_COMPANY), _settings())
    items = identify_attention(scored, {IndicatorCode.CURRENT_RATIO: 10.0})
    current_ratio = next(
        item for item in items if item.code is IndicatorCode.CURRENT_RATIO
    )
    assert current_ratio.reason is not AttentionReason.UNFAVOURABLE_MOVEMENT


def test_indicators_needing_no_attention_come_last():
    scored = score_indicators(calculate_indicators(SOUND_COMPANY), _settings())
    items = identify_attention(scored)
    assert all(item.reason is None for item in items[-1:])
