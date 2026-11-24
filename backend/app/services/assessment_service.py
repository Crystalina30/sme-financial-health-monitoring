"""Assessment orchestration.

Ties together the calculation engine, the scoring service, the attention
service and the separate distress benchmark. This is the single entry point the
API layer uses, so that no route handler contains financial logic of its own.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.enums import IndicatorCode
from app.schemas.financial_inputs import FinancialInputs
from app.services.attention_service import AttentionItem, identify_attention
from app.services.benchmark_service import BenchmarkResult, calculate_altman_z_double_prime
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import HealthAssessment, assess
from app.services.threshold_service import load_threshold_settings

#: A period this long counts as a full year for the data-quality note.
ANNUAL_PERIOD_DAYS = range(360, 371)


@dataclass(frozen=True)
class AssessmentOutput:
    """A complete assessment of one reporting period."""

    assessment: HealthAssessment
    attention: list[AttentionItem]
    benchmark: BenchmarkResult
    # Plain-language notes on anything that limits how far the score can be
    # relied on: missing indicators, an unusual period length, and so on.
    data_quality_notes: list[str] = field(default_factory=list)


def describe_data_quality(data: FinancialInputs, health: HealthAssessment) -> list[str]:
    """Explain what, in the data, limits the reliability of this assessment."""
    notes: list[str] = []

    if data.period_days is None:
        notes.append(
            "The reporting period's length is unknown, so a full year (365 days) is "
            "assumed for days sales outstanding and asset turnover."
        )
    elif data.period_days not in ANNUAL_PERIOD_DAYS:
        notes.append(
            f"This reporting period covers {data.period_days} days. Days sales outstanding "
            "and asset turnover are scaled to that length. If the figures entered are for "
            "a full year, the period's dates should be corrected."
        )

    total = len(health.indicators)
    scored = sum(1 for item in health.indicators if item.score is not None)
    if scored == 0:
        notes.append(
            "No indicator could be calculated from the figures entered, so no health score "
            "can be given."
        )
        return notes
    if scored < total:
        notes.append(
            f"{scored} of {total} indicators could be scored. Indicators that cannot be "
            "calculated are left out rather than counted as zero, so the others in their "
            "category carry more weight."
        )

    missing_categories = [
        category.value for category, score in health.category_scores.items() if score is None
    ]
    if missing_categories:
        names = ", ".join(name.capitalize() for name in missing_categories)
        remaining = len(health.category_scores) - len(missing_categories)
        notes.append(
            f"No indicator in {names} could be scored, so the overall score is the average "
            f"of the other {remaining} categories."
        )
    return notes


def assess_financial_inputs(
    db: Session,
    data: FinancialInputs,
    previous_values: dict[IndicatorCode, float | None] | None = None,
) -> AssessmentOutput:
    """Calculate, score and prioritise one set of financial inputs.

    Note that the input is a plain ``FinancialInputs`` object rather than a
    database row. The FYP2 simulation layer will produce a *projected* set of
    inputs and pass it through this same path, so the simulated position is
    assessed by exactly the engine that assesses the reported one.
    """
    thresholds = load_threshold_settings(db)
    indicators = calculate_indicators(data)
    health = assess(indicators, thresholds)
    attention = identify_attention(health.indicators, previous_values)
    return AssessmentOutput(
        assessment=health,
        attention=attention,
        benchmark=calculate_altman_z_double_prime(data),
        data_quality_notes=describe_data_quality(data, health),
    )
