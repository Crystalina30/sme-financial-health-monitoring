"""Response schemas for indicator, score and dashboard output."""

from pydantic import BaseModel

from app.models.enums import (
    AssessmentStatus,
    AttentionReason,
    HealthClassification,
    IndicatorCategory,
    IndicatorStatus,
)


class ThresholdInfo(BaseModel):
    """Threshold context shown alongside an indicator.

    The four reference points score 0 (floor), 40 (distress), 60 (concern) and
    100 (target).
    """

    direction: str
    concern_threshold: float
    distress_threshold: float
    floor_value: float | None = None
    target_value: float | None = None
    source_reference: str
    basis: str | None = None
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
    # Share of the overall score this indicator carries; null when not scored.
    effective_weight: float | None = None


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


class RobustnessResponse(BaseModel):
    """The primary (arithmetic) score beside a geometric-mean alternative.

    A robustness comparison only, not a second validated model.
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


class BenchmarkResponse(BaseModel):
    """Altman Z'' distress benchmark, reported separately from the score."""

    model: str
    source: str
    available: bool
    value: float | None
    components: dict[str, float]
    coefficients: dict[str, float]
    distress_cutoff: float
    below_distress_cutoff: bool | None
    missing_inputs: list[str]
    reason: str | None


class DataQualityIssueResponse(BaseModel):
    """A finding about the data behind an assessment.

    severity: "material" (makes the assessment provisional) or "info"."""

    severity: str
    code: str
    message: str


class IncomeStatementReconciliationResponse(BaseModel):
    """Net profit rebuilt from the statement's lines, against the reported one."""

    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    other_operating_income: float
    operating_expenses: float
    operating_profit: float
    other_income: float
    other_expenses: float
    interest_expense: float
    profit_before_tax: float
    tax_expense: float
    calculated_net_profit: float
    reported_net_profit: float
    # reported − calculated
    difference: float
    tolerance: float
    reconciled: bool


class CheckResponse(BaseModel):
    """One check that was run on the data. passed is null when it did not apply."""

    name: str
    passed: bool | None
    detail: str


class AssessmentResponse(BaseModel):
    """Full assessment of one reporting period."""

    company_id: int
    reporting_period_id: int
    period_label: str
    period_days: int
    methodology_version: str
    overall_score: float | None
    classification: HealthClassification
    category_scores: list[CategoryScoreResponse]
    indicators: list[IndicatorResponse]
    scored_indicator_count: int
    total_indicator_count: int
    attention: list[AttentionResponse]
    robustness: RobustnessResponse
    benchmark: BenchmarkResponse
    data_quality_notes: list[str]
    accounting_identity_ok: bool
    validation_notes: str | None
    # Reliability of the assessment, separate from the health classification.
    assessment_status: AssessmentStatus
    is_provisional: bool
    data_quality_issues: list[DataQualityIssueResponse]
    income_statement_reconciliation: IncomeStatementReconciliationResponse | None
    reported_net_profit: float | None
    calculated_net_profit: float | None
    reconciliation_difference: float | None
    # Exactly what "checks passed" covers; not an audit.
    checks_performed: list[CheckResponse]
    presentation_unit: float


class TrendPoint(BaseModel):
    """One period's position on a trend line."""

    reporting_period_id: int
    period_label: str
    period_end: str
    overall_score: float | None
    classification: HealthClassification
    # A provisional score is shown on the trend, but marked as such.
    assessment_status: AssessmentStatus


class FinancialSummary(BaseModel):
    """Statement figures shown on the dashboard.

    The headline figures, plus every input the score was calculated from, so
    the dashboard can show the calculation from start to finish.
    """

    revenue: float
    gross_profit: float
    operating_profit: float
    net_profit: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    cost_of_goods_sold: float
    operating_expenses: float
    interest_expense: float
    accounts_receivable: float
    inventory: float | None
    current_assets: float
    current_liabilities: float
    retained_earnings: float | None


class DashboardResponse(BaseModel):
    """Everything the dashboard renders for one reporting period."""

    assessment: AssessmentResponse
    financial_summary: FinancialSummary
    score_trend: list[TrendPoint]
