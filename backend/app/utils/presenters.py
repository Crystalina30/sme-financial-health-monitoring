"""Conversion from service dataclasses to API response schemas.

Keeping this mapping in one place stops presentation details leaking into the
calculation services and stops route handlers assembling responses by hand.
"""

from app.models.company import ReportingPeriod
from app.models.enums import IndicatorCategory, IndicatorCode
from app.models.financial_record import FinancialRecord
from app.schemas.assessment import (
    AssessmentResponse,
    AttentionResponse,
    CategoryScoreResponse,
    FinancialSummary,
    IndicatorResponse,
    PeriodChangeInfo,
    ThresholdInfo,
)
from app.schemas.financial_inputs import FinancialInputs
from app.services.assessment_service import AssessmentOutput
from app.services.attention_service import AttentionItem
from app.services.scoring_service import ScoredIndicator


def record_to_inputs(record: FinancialRecord) -> FinancialInputs:
    """Map a stored record onto the engine's input model."""
    return FinancialInputs(
        revenue=float(record.revenue),
        cost_of_goods_sold=float(record.cost_of_goods_sold),
        operating_expenses=float(record.operating_expenses),
        interest_expense=float(record.interest_expense),
        tax_expense=float(record.tax_expense),
        net_profit=float(record.net_profit),
        cash_and_equivalents=float(record.cash_and_equivalents),
        accounts_receivable=float(record.accounts_receivable),
        inventory=None if record.inventory is None else float(record.inventory),
        current_assets=float(record.current_assets),
        total_assets=float(record.total_assets),
        current_liabilities=float(record.current_liabilities),
        total_liabilities=float(record.total_liabilities),
        total_equity=float(record.total_equity),
    )


def _threshold_info(indicator: ScoredIndicator) -> ThresholdInfo | None:
    if indicator.threshold is None:
        return None
    return ThresholdInfo(
        direction=indicator.threshold.direction.value,
        concern_threshold=indicator.threshold.concern_threshold,
        distress_threshold=indicator.threshold.distress_threshold,
        source_reference=indicator.threshold.source_reference,
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


def build_assessment_response(
    output: AssessmentOutput,
    company_id: int,
    period: ReportingPeriod,
    record: FinancialRecord,
) -> AssessmentResponse:
    """Assemble the full assessment payload for one reporting period."""
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

    return AssessmentResponse(
        company_id=company_id,
        reporting_period_id=period.id,
        period_label=period.label,
        overall_score=output.assessment.overall_score,
        classification=output.assessment.classification,
        category_scores=category_scores,
        indicators=indicators,
        attention=attention,
        accounting_identity_ok=record.accounting_identity_ok,
        validation_notes=record.validation_notes,
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
    )
