"""Dashboard route.

Returns everything one dashboard view needs in a single response, so the
frontend does not have to assemble it from several calls.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_company, get_owned_period
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.schemas.assessment import DashboardResponse, TrendPoint
from app.services.assessment_service import assess_financial_inputs
from app.utils.presenters import (
    build_assessment_response,
    build_financial_summary,
    record_to_inputs,
)
from app.utils.records import get_current_record, get_previous_indicator_values

router = APIRouter(prefix="/companies", tags=["dashboard"])


def _build_score_trend(db: Session, company: Company) -> list[TrendPoint]:
    """Overall score for every period that has a financial record.

    Each point is recalculated from that period's own stored record, so the
    trend line is consistent with the assessment shown for each period.
    """
    periods = list(
        db.execute(
            select(ReportingPeriod)
            .where(ReportingPeriod.company_id == company.id)
            .order_by(ReportingPeriod.period_end)
        ).scalars()
    )

    trend: list[TrendPoint] = []
    for period in periods:
        record = get_current_record(db, period.id)
        if record is None:
            continue
        output = assess_financial_inputs(db, record_to_inputs(record))
        trend.append(
            TrendPoint(
                reporting_period_id=period.id,
                period_label=period.label,
                period_end=period.period_end.isoformat(),
                overall_score=output.assessment.overall_score,
                classification=output.assessment.classification,
            )
        )
    return trend


@router.get(
    "/{company_id}/dashboard/{reporting_period_id}",
    response_model=DashboardResponse,
    summary="Full dashboard payload for one reporting period",
)
def read_dashboard(
    reporting_period_id: int,
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    period = get_owned_period(db, company, reporting_period_id)
    record = get_current_record(db, period.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No financial record has been entered for this reporting period.",
        )

    inputs = record_to_inputs(record)
    output = assess_financial_inputs(
        db, inputs, previous_values=get_previous_indicator_values(db, company, period)
    )

    return DashboardResponse(
        assessment=build_assessment_response(output, company.id, period, record),
        financial_summary=build_financial_summary(inputs),
        score_trend=_build_score_trend(db, company),
    )
