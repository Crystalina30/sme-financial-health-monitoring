"""Indicator assessment routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_company, get_owned_period
from app.core.database import get_db
from app.models.company import Company
from app.schemas.assessment import AssessmentResponse
from app.services.assessment_service import assess_financial_inputs
from app.utils.presenters import build_assessment_response, record_to_inputs
from app.utils.records import get_current_record, get_previous_indicator_values

router = APIRouter(prefix="/companies", tags=["indicators"])


@router.get(
    "/{company_id}/indicators/{reporting_period_id}",
    response_model=AssessmentResponse,
    summary="Indicators, scores and attention for one reporting period",
)
def read_indicators(
    reporting_period_id: int,
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    period = get_owned_period(db, company, reporting_period_id)
    record = get_current_record(db, period.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No financial record has been entered for this reporting period.",
        )

    output = assess_financial_inputs(
        db,
        record_to_inputs(record),
        previous_values=get_previous_indicator_values(db, company, period),
    )
    return build_assessment_response(output, company.id, period, record)
