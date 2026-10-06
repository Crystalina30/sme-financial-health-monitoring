"""Response schemas for indicator, score and dashboard output."""

from pydantic import BaseModel

from app.models.enums import (
    AttentionReason,
    HealthClassification,
    IndicatorCategory,
    IndicatorStatus,
)


class ThresholdInfo(BaseModel):
    """Threshold context shown alongside an indicator."""

    direction: str
    concern_threshold: float
    distress_threshold: float
    source_reference: str
    description: str


class PeriodChangeInfo(BaseModel):
    """Movement of an indicator since the previous reporting period."""

    previous_value: float | None
    change: float | None
    change_percent: float | None
    is_unfavourable: bool


class IndicatorResponse(BaseModel):
    """One indicator, with everything the dashboard needs to display it."""

    code: str
    display_name: str
    category: IndicatorCategory
    unit: str
    value: float | None
    score: float | None
    status: IndicatorStatus
    is_applicable: bool
    note: str | None
    threshold: ThresholdInfo | None
    change: PeriodChangeInfo | None = None


class CategoryScoreResponse(BaseModel):
    category: IndicatorCategory
    score: float | None
    applicable_indicator_count: int


class AttentionResponse(BaseModel):
    code: str
    display_name: str
    priority: int
    reason: AttentionReason | None
    status: IndicatorStatus


class AssessmentResponse(BaseModel):
    """Full assessment of one reporting period."""

    company_id: int
    reporting_period_id: int
    period_label: str
    overall_score: float | None
    classification: HealthClassification
    category_scores: list[CategoryScoreResponse]
    indicators: list[IndicatorResponse]
    attention: list[AttentionResponse]
    accounting_identity_ok: bool
    validation_notes: str | None


class TrendPoint(BaseModel):
    """One period's position on a trend line."""

    reporting_period_id: int
    period_label: str
    period_end: str
    overall_score: float | None
    classification: HealthClassification


class FinancialSummary(BaseModel):
    """Headline statement figures shown on the dashboard."""

    revenue: float
    gross_profit: float
    operating_profit: float
    net_profit: float
    total_assets: float
    total_liabilities: float
    total_equity: float


class DashboardResponse(BaseModel):
    """Everything the dashboard renders for one reporting period."""

    assessment: AssessmentResponse
    financial_summary: FinancialSummary
    score_trend: list[TrendPoint]
