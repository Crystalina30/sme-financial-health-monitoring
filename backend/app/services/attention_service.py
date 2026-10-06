"""Identification of indicators requiring attention.

Attention is determined by two mechanisms only: the indicator's *threshold
status*, and its *reporting-period change*. No statistical procedure selects a
subset of indicators, and the ten indicators themselves never change — this
service decides the order and prominence in which they are presented, nothing
more.
"""

from dataclasses import dataclass

from app.models.enums import (
    AttentionReason,
    IndicatorCode,
    IndicatorStatus,
    ThresholdDirection,
)
from app.services.scoring_service import ScoredIndicator

#: An indicator must move by at least this proportion against the enterprise
#: before the movement alone draws attention. Expressed as a fraction of the
#: previous period's value.
DEFAULT_MOVEMENT_THRESHOLD = 0.10

#: Display priority: lower sorts first.
REASON_PRIORITY = {
    AttentionReason.DISTRESS_BREACH: 1,
    AttentionReason.CONCERN_BREACH: 2,
    AttentionReason.UNFAVOURABLE_MOVEMENT: 3,
}
NO_ATTENTION_PRIORITY = 4


@dataclass(frozen=True)
class PeriodChange:
    """Movement of one indicator between the two most recent periods."""

    previous_value: float | None
    change: float | None
    change_percent: float | None
    is_unfavourable: bool


@dataclass(frozen=True)
class AttentionItem:
    """An indicator with its attention reason and display priority."""

    code: IndicatorCode
    display_name: str
    priority: int
    reason: AttentionReason | None
    status: IndicatorStatus
    change: PeriodChange | None


def calculate_period_change(
    current_value: float | None,
    previous_value: float | None,
    direction: ThresholdDirection,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
) -> PeriodChange:
    """Compare an indicator with its value in the previous reporting period.

    A movement counts as unfavourable when it runs against the enterprise — a
    fall for a higher-is-better indicator, a rise for a lower-is-better one —
    and exceeds the configured proportion of the previous value.
    """
    if current_value is None or previous_value is None:
        return PeriodChange(previous_value, None, None, False)

    change = current_value - previous_value
    if abs(previous_value) < 1e-9:
        # No meaningful proportional comparison against a zero baseline.
        return PeriodChange(previous_value, change, None, False)

    change_percent = change / abs(previous_value)

    if direction is ThresholdDirection.HIGHER_IS_BETTER:
        unfavourable = change_percent <= -movement_threshold
    else:
        unfavourable = change_percent >= movement_threshold

    return PeriodChange(
        previous_value=previous_value,
        change=change,
        change_percent=round(change_percent * 100, 2),
        is_unfavourable=unfavourable,
    )


def identify_attention(
    scored: list[ScoredIndicator],
    previous_values: dict[IndicatorCode, float | None] | None = None,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
) -> list[AttentionItem]:
    """Rank all ten indicators by how much attention they require.

    Threshold breaches come first (distress before concern), then indicators
    showing unfavourable reporting-period change, then the remainder. Every
    indicator is returned; none is dropped.
    """
    previous_values = previous_values or {}
    items: list[AttentionItem] = []

    for indicator in scored:
        change: PeriodChange | None = None
        if indicator.threshold is not None:
            change = calculate_period_change(
                current_value=indicator.value,
                previous_value=previous_values.get(indicator.code),
                direction=indicator.threshold.direction,
                movement_threshold=movement_threshold,
            )

        if indicator.status is IndicatorStatus.DISTRESS:
            reason = AttentionReason.DISTRESS_BREACH
        elif indicator.status is IndicatorStatus.CONCERN:
            reason = AttentionReason.CONCERN_BREACH
        elif change is not None and change.is_unfavourable:
            reason = AttentionReason.UNFAVOURABLE_MOVEMENT
        else:
            reason = None

        items.append(
            AttentionItem(
                code=indicator.code,
                display_name=indicator.display_name,
                priority=REASON_PRIORITY.get(reason, NO_ATTENTION_PRIORITY)
                if reason
                else NO_ATTENTION_PRIORITY,
                reason=reason,
                status=indicator.status,
                change=change,
            )
        )

    # Stable sort, so indicators of equal priority keep their fixed order.
    return sorted(items, key=lambda item: item.priority)
