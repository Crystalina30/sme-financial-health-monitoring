"""Conversion from service dataclasses to API response schemas.

Keeping this mapping in one place stops presentation details leaking into the
calculation services and stops route handlers assembling responses by hand.
"""

from app.models.company import ReportingPeriod
from app.models.enums import IndicatorCategory, IndicatorCode
from app.models.financial_record import FinancialRecord
from app.schemas.assessment import (
    AssessmentResponse,
    CheckResponse,
    DataQualityIssueResponse,
    IncomeStatementReconciliationResponse,
    AttentionResponse,
    BenchmarkResponse,
    CategoryScoreResponse,
    FinancialSummary,
    IndicatorResponse,
    PeriodChangeInfo,
    RobustnessResponse,
    ThresholdInfo,
)
from app.schemas.financial_inputs import FinancialInputs
from app.services import benchmark_service
from app.services.assessment_service import AssessmentOutput
from app.services.attention_service import AttentionItem
from app.services.reliability_service import AssessmentReliability, evaluate_reliability
from app.services.validation_service import IncomeStatementReconciliation
from app.services.scoring_service import ScoredIndicator


def period_length_days(period: ReportingPeriod) -> int:
    """Days covered by a reporting period, counting both its first and last day."""
    return (period.period_end - period.period_start).days + 1


def record_to_inputs(record: FinancialRecord) -> FinancialInputs:
    """Map a stored record onto the engine's input model.

    The period length comes from the record's reporting period, so flow-based
    ratios are scaled to the period the figures actually cover.
    """
    period = record.reporting_period
    return FinancialInputs(
        revenue=float(record.revenue),
        cost_of_goods_sold=float(record.cost_of_goods_sold),
        operating_expenses=float(record.operating_expenses),
        interest_expense=float(record.interest_expense),
        tax_expense=float(record.tax_expense),
        net_profit=float(record.net_profit),
        other_operating_income=float(record.other_operating_income or 0),
        other_income=float(record.other_income or 0),
        other_expenses=float(record.other_expenses or 0),
        cash_and_equivalents=float(record.cash_and_equivalents),
        accounts_receivable=float(record.accounts_receivable),
        inventory=None if record.inventory is None else float(record.inventory),
        current_assets=float(record.current_assets),
        total_assets=float(record.total_assets),
        current_liabilities=float(record.current_liabilities),
        total_liabilities=float(record.total_liabilities),
        total_equity=float(record.total_equity),
        retained_earnings=None
        if record.retained_earnings is None
        else float(record.retained_earnings),
        period_days=None if period is None else period_length_days(period),
    )


def _threshold_info(indicator: ScoredIndicator) -> ThresholdInfo | None:
    if indicator.threshold is None:
        return None
    points = indicator.reference_points
    return ThresholdInfo(
        direction=indicator.threshold.direction.value,
        concern_threshold=indicator.threshold.concern_threshold,
        distress_threshold=indicator.threshold.distress_threshold,
        floor_value=None if points is None else points.floor,
        target_value=None if points is None else points.target,
        source_reference=indicator.threshold.source_reference,
        basis=indicator.threshold.basis,
        description=indicator.threshold.description,
    )


def _change_info(item: AttentionItem | None) -> PeriodChangeInfo | None:
    if item is None or item.change is None:
        return None
    return PeriodChangeInfo(
        previous_value=item.change.previous_value,
        change=item.change.change,
        change_percent=item.change.change_percent,
        is_unfavourable=item.change.is_unfavourable,
    )


def reliability_for(record: FinancialRecord, output: AssessmentOutput) -> AssessmentReliability:
    """The reliability of an assessment made from this record, now."""
    return evaluate_reliability(
        record, record_to_inputs(record), output.assessment, output.data_quality_notes
    )


def build_reconciliation(
    reconciliation: IncomeStatementReconciliation | None,
) -> IncomeStatementReconciliationResponse | None:
    if reconciliation is None:
        return None
    values = {
        name: float(getattr(reconciliation, name))
        for name in IncomeStatementReconciliationResponse.model_fields
        if name != "reconciled"
    }
    return IncomeStatementReconciliationResponse(**values, reconciled=reconciliation.reconciled)


def build_assessment_response(
    output: AssessmentOutput,
    company_id: int,
    period: ReportingPeriod,
    record: FinancialRecord,
) -> AssessmentResponse:
    """Assemble the full assessment payload for one reporting period."""
    reliability = reliability_for(record, output)
    reconciliation = build_reconciliation(reliability.reconciliation)
    attention_by_code: dict[IndicatorCode, AttentionItem] = {
        item.code: item for item in output.attention
    }

    indicators = [
        IndicatorResponse(
            code=indicator.code.value,
            display_name=indicator.display_name,
            category=indicator.category,
            unit=indicator.unit,
            value=None if indicator.value is None else round(indicator.value, 4),
            score=indicator.score,
            status=indicator.status,
            is_applicable=indicator.is_applicable,
            note=indicator.note,
            threshold=_threshold_info(indicator),
            change=_change_info(attention_by_code.get(indicator.code)),
            effective_weight=output.assessment.indicator_weights.get(indicator.code),
        )
        for indicator in output.assessment.indicators
    ]

    category_scores = [
        CategoryScoreResponse(
            category=category,
            score=output.assessment.category_scores[category],
            applicable_indicator_count=sum(
                1
                for indicator in output.assessment.indicators
                if indicator.category is category and indicator.score is not None
            ),
        )
        for category in IndicatorCategory
    ]

    attention = [
        AttentionResponse(
            code=item.code.value,
            display_name=item.display_name,
            priority=item.priority,
            reason=item.reason,
            status=item.status,
        )
        for item in output.attention
    ]

    robustness = output.assessment.robustness
    benchmark = output.benchmark

    return AssessmentResponse(
        company_id=company_id,
        reporting_period_id=period.id,
        period_label=period.label,
        period_days=period_length_days(period),
        methodology_version=output.assessment.methodology_version,
        overall_score=output.assessment.overall_score,
        classification=output.assessment.classification,
        category_scores=category_scores,
        indicators=indicators,
        scored_indicator_count=sum(1 for item in indicators if item.score is not None),
        total_indicator_count=len(indicators),
        attention=attention,
        robustness=RobustnessResponse(
            arithmetic_score=robustness.arithmetic_score,
            geometric_score=robustness.geometric_score,
            difference=robustness.difference,
            arithmetic_classification=robustness.arithmetic_classification,
            geometric_classification=robustness.geometric_classification,
            classifications_differ=robustness.classifications_differ,
            has_zero_category=robustness.has_zero_category,
            weakest_category=robustness.weakest_category,
            weakest_category_score=robustness.weakest_category_score,
        ),
        benchmark=BenchmarkResponse(
            model=benchmark_service.MODEL_NAME,
            source=benchmark_service.SOURCE,
            available=benchmark.available,
            value=benchmark.value,
            components=benchmark.components,
            coefficients=benchmark_service.COEFFICIENTS,
            distress_cutoff=benchmark_service.DISTRESS_CUTOFF,
            below_distress_cutoff=benchmark.below_distress_cutoff,
            missing_inputs=benchmark.missing_inputs,
            reason=benchmark.reason,
        ),
        data_quality_notes=output.data_quality_notes,
        accounting_identity_ok=record.accounting_identity_ok,
        validation_notes=record.validation_notes,
        assessment_status=reliability.status,
        is_provisional=reliability.is_provisional,
        data_quality_issues=[
            DataQualityIssueResponse(severity=i.severity, code=i.code, message=i.message)
            for i in reliability.issues
        ],
        income_statement_reconciliation=reconciliation,
        reported_net_profit=reconciliation.reported_net_profit if reconciliation else None,
        calculated_net_profit=reconciliation.calculated_net_profit if reconciliation else None,
        reconciliation_difference=reconciliation.difference if reconciliation else None,
        checks_performed=[
            CheckResponse(name=c.name, passed=c.passed, detail=c.detail)
            for c in reliability.checks
        ],
        presentation_unit=float(record.presentation_unit or 0.01),
    )


def build_financial_summary(data: FinancialInputs) -> FinancialSummary:
    """Headline statement figures for the dashboard summary panel."""
    return FinancialSummary(
        revenue=data.revenue,
        gross_profit=data.gross_profit,
        operating_profit=data.operating_profit,
        net_profit=data.net_profit,
        total_assets=data.total_assets,
        total_liabilities=data.total_liabilities,
        total_equity=data.total_equity,
        cost_of_goods_sold=data.cost_of_goods_sold,
        operating_expenses=data.operating_expenses,
        interest_expense=data.interest_expense,
        accounts_receivable=data.accounts_receivable,
        inventory=data.inventory,
        current_assets=data.current_assets,
        current_liabilities=data.current_liabilities,
        retained_earnings=data.retained_earnings,
    )
