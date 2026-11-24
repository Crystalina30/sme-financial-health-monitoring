"""Threshold-based scoring.

Scoring is deliberately transparent and deterministic: an indicator's score is
a function of its value relative to four configured reference points, and
nothing else. No weighting is derived from the data, and every indicator and
every category carries equal weight.

Normalisation (OECD/JRC, 2008: distance to a reference). Each indicator has
four reference points, stored per indicator:

* the floor, which scores 0;
* the distress threshold, which scores 40;
* the concern threshold, which scores 60;
* the target, which scores 100.

Between consecutive points the score is linear; beyond the floor or the target
it is clamped to 0 or 100. The anchor scores 40 and 60 are this project's own
design: they place the concern threshold at the start of the "Sound" band and
the distress threshold at the start of the "Vulnerable" band. They are not a
published standard.

When a configuration gives no floor or target, the defaults reproduce the
methodology-1.0 behaviour exactly: the target lies one span (the gap between
the concern and distress thresholds) beyond the concern threshold, and the
floor two spans beyond the distress threshold.

The *status* of an indicator is a separate, categorical judgement made by
comparing the value with the concern and distress thresholds directly. Status
is not derived from the score.
"""

import math
from dataclasses import dataclass, field

from app.models.enums import (
    HealthClassification,
    IndicatorCategory,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.financial_calculation_service import CalculatedIndicator

#: Identifies the scoring rules a result was produced under, so a reported
#: score can always be traced to the method that produced it. 1.0 was the
#: original FYP1 method; 2.0 added explicit reference points, negative-equity
#: handling, period-length scaling and "Insufficient data".
METHODOLOGY_VERSION = "2.0"

# Score anchors at the four reference points.
SCORE_AT_FLOOR = 0.0
SCORE_AT_DISTRESS = 40.0
SCORE_AT_CONCERN = 60.0
SCORE_AT_TARGET = 100.0
SCORE_MIN = SCORE_AT_FLOOR
SCORE_MAX = SCORE_AT_TARGET

# Default reference points, in multiples of the concern-distress span.
DEFAULT_TARGET_SPANS = 1.0
DEFAULT_FLOOR_SPANS = 2.0

# Overall classification bands. Project-defined, tied to the anchors above.
DEFAULT_SOUND_FLOOR = 60.0
DEFAULT_VULNERABLE_FLOOR = 40.0


class InvalidThresholdError(ValueError):
    """Reference points that are not strictly ordered from worst to best."""


@dataclass(frozen=True)
class ThresholdSetting:
    """Threshold configuration for one indicator, as used by the scorer.

    ``floor_value`` and ``target_value`` are optional; when absent, the
    defaults described in the module docstring apply.
    """

    indicator_code: IndicatorCode
    direction: ThresholdDirection
    concern_threshold: float
    distress_threshold: float
    source_reference: str
    description: str
    floor_value: float | None = None
    target_value: float | None = None
    basis: str | None = None


@dataclass(frozen=True)
class ReferencePoints:
    """The four reference points of one indicator, in the ratio's own units."""

    floor: float
    distress: float
    concern: float
    target: float


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
    reference_points: ReferencePoints | None = None


@dataclass(frozen=True)
class RobustnessComparison:
    """The primary score set beside a geometric-mean alternative.

    The geometric mean is a robustness check, not a second validated model.
    It lets a weak category pull the result down more than the arithmetic
    mean does, so a large gap shows that strong categories are compensating
    for a weak one.
    """

    arithmetic_score: float | None
    geometric_score: float | None
    difference: float | None
    arithmetic_classification: HealthClassification
    geometric_classification: HealthClassification
    classifications_differ: bool
    has_zero_category: bool
    weakest_category: IndicatorCategory | None
    weakest_category_score: float | None


@dataclass(frozen=True)
class HealthAssessment:
    """Scores for every indicator, each category and the company overall."""

    indicators: list[ScoredIndicator]
    category_scores: dict[IndicatorCategory, float | None]
    overall_score: float | None
    classification: HealthClassification
    robustness: RobustnessComparison | None = None
    # Share of the overall score each scored indicator carries.
    indicator_weights: dict[IndicatorCode, float] = field(default_factory=dict)
    methodology_version: str = METHODOLOGY_VERSION


def _clamp(value: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def _orientation(direction: ThresholdDirection) -> float:
    """+1 when higher is better, -1 when lower is better."""
    return 1.0 if direction is ThresholdDirection.HIGHER_IS_BETTER else -1.0


def default_reference_points(
    direction: ThresholdDirection, concern: float, distress: float
) -> tuple[float, float]:
    """Default (floor, target) for a concern and distress threshold.

    The target lies one span beyond the concern threshold and the floor two
    spans beyond the distress threshold, both in the "better" and "worse"
    direction respectively. These reproduce the methodology-1.0 scores.
    """
    sign = _orientation(direction)
    span = abs(concern - distress)
    target = concern + sign * DEFAULT_TARGET_SPANS * span
    floor = distress - sign * DEFAULT_FLOOR_SPANS * span
    return floor, target


def validate_reference_points(direction: ThresholdDirection, points: ReferencePoints) -> None:
    """Raise InvalidThresholdError unless the points run worst to best.

    Oriented so that higher is better, the floor must be below the distress
    threshold, which must be below the concern threshold, which must be below
    the target. Strict ordering also rules out every division by zero in the
    scoring formula.
    """
    sign = _orientation(direction)
    oriented = [sign * p for p in (points.floor, points.distress, points.concern, points.target)]
    if not all(a < b for a, b in zip(oriented, oriented[1:])):
        better = "higher" if sign > 0 else "lower"
        raise InvalidThresholdError(
            "Reference points must run floor, distress, concern, target from worst "
            f"to best ({better} is better); got {points.floor}, {points.distress}, "
            f"{points.concern}, {points.target}."
        )


def reference_points_for(threshold: ThresholdSetting) -> ReferencePoints:
    """The four validated reference points of a threshold configuration."""
    default_floor, default_target = default_reference_points(
        threshold.direction, threshold.concern_threshold, threshold.distress_threshold
    )
    points = ReferencePoints(
        floor=default_floor if threshold.floor_value is None else threshold.floor_value,
        distress=threshold.distress_threshold,
        concern=threshold.concern_threshold,
        target=default_target if threshold.target_value is None else threshold.target_value,
    )
    validate_reference_points(threshold.direction, points)
    return points


def score_indicator_value(value: float, threshold: ThresholdSetting) -> float:
    """Score one indicator value from 0 to 100 against its reference points.

    Values and points are first oriented so that higher is better (multiplied
    by -1 for lower-is-better indicators); the score is then linear between
    consecutive reference points and clamped to 0-100.
    """
    points = reference_points_for(threshold)
    sign = _orientation(threshold.direction)
    v = sign * value
    f, d, c, t = (sign * p for p in (points.floor, points.distress, points.concern, points.target))

    if v <= f:
        return SCORE_AT_FLOOR
    if v <= d:
        return SCORE_AT_FLOOR + (SCORE_AT_DISTRESS - SCORE_AT_FLOOR) * (v - f) / (d - f)
    if v <= c:
        return SCORE_AT_DISTRESS + (SCORE_AT_CONCERN - SCORE_AT_DISTRESS) * (v - d) / (c - d)
    if v < t:
        return SCORE_AT_CONCERN + (SCORE_AT_TARGET - SCORE_AT_CONCERN) * (v - c) / (t - c)
    return _clamp(SCORE_AT_TARGET)


def determine_status(value: float, threshold: ThresholdSetting) -> IndicatorStatus:
    """Classify a value against its thresholds.

    A value at a threshold counts as having reached it, so an indicator
    exactly at its distress threshold is reported as distressed, and one
    exactly at its concern threshold as concern (although it scores 60).
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


def _not_scored(
    indicator: CalculatedIndicator, threshold: ThresholdSetting | None, note: str | None
) -> ScoredIndicator:
    return ScoredIndicator(
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


def score_indicators(
    indicators: list[CalculatedIndicator],
    thresholds: dict[IndicatorCode, ThresholdSetting],
) -> list[ScoredIndicator]:
    """Attach a score, status and threshold context to each indicator.

    An indicator that is not applicable, or that has no valid threshold
    configured, receives a score of ``None`` and the status
    ``not_applicable``. It is never scored as zero, which would wrongly drag
    down its category average. The exception is an indicator marked
    ``worst_case`` (debt-to-equity at zero or negative equity), which is
    scored 0 with the status ``distress``.
    """
    scored: list[ScoredIndicator] = []
    for indicator in indicators:
        threshold = thresholds.get(indicator.code)

        if threshold is None:
            note = indicator.note
            if indicator.is_applicable:
                note = "No threshold configured for this indicator."
            scored.append(_not_scored(indicator, None, note))
            continue

        try:
            points = reference_points_for(threshold)
        except InvalidThresholdError as error:
            note = f"Threshold configuration is invalid: {error}"
            scored.append(_not_scored(indicator, threshold, note))
            continue

        if indicator.worst_case:
            scored.append(
                ScoredIndicator(
                    code=indicator.code,
                    display_name=indicator.display_name,
                    category=indicator.category,
                    unit=indicator.unit,
                    value=None,
                    score=SCORE_AT_FLOOR,
                    status=IndicatorStatus.DISTRESS,
                    is_applicable=True,
                    note=indicator.note,
                    threshold=threshold,
                    reference_points=points,
                )
            )
            continue

        if not indicator.is_applicable or indicator.value is None:
            scored.append(_not_scored(indicator, threshold, indicator.note))
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
                reference_points=points,
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


def calculate_geometric_overall_score(
    category_scores: dict[IndicatorCategory, float | None],
) -> float | None:
    """Geometric mean of the applicable category scores.

    No floor is applied: if any category scores 0, the geometric mean is 0.
    That is the method's defining, non-compensatory behaviour (one failing
    category cannot be offset), so it is reported as such rather than hidden
    by substituting a small positive value.
    """
    applicable = [score for score in category_scores.values() if score is not None]
    if not applicable:
        return None
    if any(score <= 0 for score in applicable):
        return 0.0
    return round(math.exp(sum(math.log(score) for score in applicable) / len(applicable)), 2)


def calculate_indicator_weights(
    scored: list[ScoredIndicator],
) -> dict[IndicatorCode, float]:
    """Share of the overall score carried by each scored indicator.

    With equal weights at both levels, indicator i in category k carries
    1 / (m * n_k), where m is the number of scored categories and n_k the
    number of scored indicators in category k. The weights always sum to 1,
    and change when an indicator or category is not applicable.
    """
    scored_by_category: dict[IndicatorCategory, list[ScoredIndicator]] = {}
    for item in scored:
        if item.score is not None:
            scored_by_category.setdefault(item.category, []).append(item)
    m = len(scored_by_category)
    return {
        item.code: 1 / (m * len(items))
        for items in scored_by_category.values()
        for item in items
    }


def classify(
    overall_score: float | None,
    sound_floor: float = DEFAULT_SOUND_FLOOR,
    vulnerable_floor: float = DEFAULT_VULNERABLE_FLOOR,
) -> HealthClassification:
    """Place an overall score in its health band.

    No score at all means there was nothing to assess, which is reported as
    insufficient data rather than as distress.
    """
    if overall_score is None:
        return HealthClassification.INSUFFICIENT_DATA
    if overall_score >= sound_floor:
        return HealthClassification.SOUND
    if overall_score >= vulnerable_floor:
        return HealthClassification.VULNERABLE
    return HealthClassification.DISTRESSED


def compare_aggregations(
    category_scores: dict[IndicatorCategory, float | None],
) -> RobustnessComparison:
    """Set the arithmetic-mean score beside the geometric-mean alternative."""
    arithmetic = calculate_overall_score(category_scores)
    geometric = calculate_geometric_overall_score(category_scores)
    applicable = [
        (category, score) for category, score in category_scores.items() if score is not None
    ]
    # Ties go to the first category in the fixed order.
    weakest = min(applicable, key=lambda pair: pair[1]) if applicable else (None, None)
    arithmetic_class = classify(arithmetic)
    geometric_class = classify(geometric)
    return RobustnessComparison(
        arithmetic_score=arithmetic,
        geometric_score=geometric,
        difference=None if arithmetic is None else round(arithmetic - geometric, 2),
        arithmetic_classification=arithmetic_class,
        geometric_classification=geometric_class,
        classifications_differ=arithmetic_class is not geometric_class,
        has_zero_category=any(score <= 0 for _, score in applicable),
        weakest_category=weakest[0],
        weakest_category_score=weakest[1],
    )


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
        robustness=compare_aggregations(category_scores),
        indicator_weights=calculate_indicator_weights(scored),
    )
