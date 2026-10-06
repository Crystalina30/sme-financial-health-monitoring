"""Threshold-based scoring.

Scoring is deliberately transparent and deterministic: an indicator's score is
a function of its position relative to its own two configured thresholds, and
nothing else. No weighting is derived from the data, and every indicator and
every category carries equal weight.

The scale is anchored at the two thresholds:

* at the concern threshold the score is exactly 60;
* at the distress threshold the score is exactly 40;
* beyond either threshold the score continues linearly, measured in units of
  the span between the two thresholds, and is clamped to the range 0-100.

The *status* of an indicator is a separate, categorical judgement made by
comparing the value with the thresholds directly. Status is not derived from
the score, so the two never need to be reconciled.
"""

from dataclasses import dataclass

from app.models.enums import (
    HealthClassification,
    IndicatorCategory,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.financial_calculation_service import CalculatedIndicator

# Score anchors at the two thresholds.
SCORE_AT_CONCERN = 60.0
SCORE_AT_DISTRESS = 40.0
SCORE_MIN = 0.0
SCORE_MAX = 100.0

# Overall classification bands. Configurable, with the FYP1 values as default.
DEFAULT_SOUND_FLOOR = 60.0
DEFAULT_VULNERABLE_FLOOR = 40.0


@dataclass(frozen=True)
class ThresholdSetting:
    """Threshold configuration for one indicator, as used by the scorer."""

    indicator_code: IndicatorCode
    direction: ThresholdDirection
    concern_threshold: float
    distress_threshold: float
    source_reference: str
    description: str


@dataclass(frozen=True)
class ScoredIndicator:
    """An indicator together with its score, status and threshold context."""

    code: IndicatorCode
    display_name: str
    category: IndicatorCategory
    unit: str
    value: float | None
    score: float | None
    status: IndicatorStatus
    is_applicable: bool
    note: str | None
    threshold: ThresholdSetting | None


@dataclass(frozen=True)
class HealthAssessment:
    """Scores for every indicator, each category and the company overall."""

    indicators: list[ScoredIndicator]
    category_scores: dict[IndicatorCategory, float | None]
    overall_score: float | None
    classification: HealthClassification


def _clamp(value: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def score_indicator_value(value: float, threshold: ThresholdSetting) -> float:
    """Score one indicator value from 0 to 100 against its thresholds.

    The span between the concern and distress thresholds is the unit of
    measurement, so an indicator one full span better than its concern
    threshold scores 100, and one full span worse than its distress threshold
    scores 0.
    """
    concern = threshold.concern_threshold
    distress = threshold.distress_threshold
    span = abs(concern - distress)

    # Degenerate configuration: the two thresholds coincide, so there is no
    # span to interpolate over. Fall back to a simple pass/fail judgement.
    if span < 1e-9:
        if threshold.direction is ThresholdDirection.HIGHER_IS_BETTER:
            return SCORE_AT_CONCERN if value >= concern else SCORE_AT_DISTRESS
        return SCORE_AT_CONCERN if value <= concern else SCORE_AT_DISTRESS

    if threshold.direction is ThresholdDirection.HIGHER_IS_BETTER:
        # Distance above the concern threshold, in spans.
        offset = (value - concern) / span
    else:
        # Lower is better, so distance below the concern threshold.
        offset = (concern - value) / span

    if offset >= 0:
        # At or better than concern: 60 rising to 100 one span further on.
        return _clamp(SCORE_AT_CONCERN + offset * (SCORE_MAX - SCORE_AT_CONCERN))
    # Worse than concern: 60 falling to 40 at distress, then on to 0.
    return _clamp(SCORE_AT_CONCERN + offset * (SCORE_AT_CONCERN - SCORE_AT_DISTRESS))


def determine_status(value: float, threshold: ThresholdSetting) -> IndicatorStatus:
    """Classify a value against its thresholds.

    A value at a threshold counts as having reached it, so an indicator
    exactly at its distress threshold is reported as distressed.
    """
    if threshold.direction is ThresholdDirection.HIGHER_IS_BETTER:
        if value <= threshold.distress_threshold:
            return IndicatorStatus.DISTRESS
        if value <= threshold.concern_threshold:
            return IndicatorStatus.CONCERN
        return IndicatorStatus.SOUND

    if value >= threshold.distress_threshold:
        return IndicatorStatus.DISTRESS
    if value >= threshold.concern_threshold:
        return IndicatorStatus.CONCERN
    return IndicatorStatus.SOUND


def score_indicators(
    indicators: list[CalculatedIndicator],
    thresholds: dict[IndicatorCode, ThresholdSetting],
) -> list[ScoredIndicator]:
    """Attach a score, status and threshold context to each indicator.

    An indicator that is not applicable, or that has no threshold configured,
    receives a score of ``None`` and the status ``not_applicable``. It is never
    scored as zero, which would wrongly drag down its category average.
    """
    scored: list[ScoredIndicator] = []
    for indicator in indicators:
        threshold = thresholds.get(indicator.code)
        if not indicator.is_applicable or indicator.value is None or threshold is None:
            note = indicator.note
            if threshold is None and indicator.is_applicable:
                note = "No threshold configured for this indicator."
            scored.append(
                ScoredIndicator(
                    code=indicator.code,
                    display_name=indicator.display_name,
                    category=indicator.category,
                    unit=indicator.unit,
                    value=indicator.value,
                    score=None,
                    status=IndicatorStatus.NOT_APPLICABLE,
                    is_applicable=False,
                    note=note,
                    threshold=threshold,
                )
            )
            continue

        scored.append(
            ScoredIndicator(
                code=indicator.code,
                display_name=indicator.display_name,
                category=indicator.category,
                unit=indicator.unit,
                value=indicator.value,
                score=round(score_indicator_value(indicator.value, threshold), 2),
                status=determine_status(indicator.value, threshold),
                is_applicable=True,
                note=None,
                threshold=threshold,
            )
        )
    return scored


def calculate_category_scores(
    scored: list[ScoredIndicator],
) -> dict[IndicatorCategory, float | None]:
    """Average the applicable indicator scores within each category.

    A category whose indicators are all not applicable scores ``None`` rather
    than zero.
    """
    category_scores: dict[IndicatorCategory, float | None] = {}
    for category in IndicatorCategory:
        applicable = [
            item.score
            for item in scored
            if item.category is category and item.score is not None
        ]
        category_scores[category] = (
            round(sum(applicable) / len(applicable), 2) if applicable else None
        )
    return category_scores


def calculate_overall_score(
    category_scores: dict[IndicatorCategory, float | None],
) -> float | None:
    """Average the applicable category scores, weighting all four equally."""
    applicable = [score for score in category_scores.values() if score is not None]
    if not applicable:
        return None
    return round(sum(applicable) / len(applicable), 2)


def classify(
    overall_score: float | None,
    sound_floor: float = DEFAULT_SOUND_FLOOR,
    vulnerable_floor: float = DEFAULT_VULNERABLE_FLOOR,
) -> HealthClassification:
    """Place an overall score in its health band."""
    if overall_score is None:
        return HealthClassification.DISTRESSED
    if overall_score >= sound_floor:
        return HealthClassification.SOUND
    if overall_score >= vulnerable_floor:
        return HealthClassification.VULNERABLE
    return HealthClassification.DISTRESSED


def assess(
    indicators: list[CalculatedIndicator],
    thresholds: dict[IndicatorCode, ThresholdSetting],
) -> HealthAssessment:
    """Score indicators, categories and the company overall in one step."""
    scored = score_indicators(indicators, thresholds)
    category_scores = calculate_category_scores(scored)
    overall = calculate_overall_score(category_scores)
    return HealthAssessment(
        indicators=scored,
        category_scores=category_scores,
        overall_score=overall,
        classification=classify(overall),
    )
