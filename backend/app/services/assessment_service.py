"""Assessment orchestration.

Ties together the calculation engine, the scoring service and the attention
service. This is the single entry point the API layer uses, so that no route
handler contains financial logic of its own.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.enums import IndicatorCode
from app.schemas.financial_inputs import FinancialInputs
from app.services.attention_service import AttentionItem, identify_attention
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import HealthAssessment, assess
from app.services.threshold_service import load_threshold_settings


@dataclass(frozen=True)
class AssessmentOutput:
    """A complete assessment of one reporting period."""

    assessment: HealthAssessment
    attention: list[AttentionItem]


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
    return AssessmentOutput(assessment=health, attention=attention)
