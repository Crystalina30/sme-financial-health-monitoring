"""Helpers for retrieving financial records and previous-period values."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, ReportingPeriod
from app.models.enums import IndicatorCode
from app.models.financial_record import FinancialRecord
from app.services.financial_calculation_service import calculate_indicators


def get_current_record(
    db: Session, reporting_period_id: int
) -> FinancialRecord | None:
    """Return the current revision of the record for a reporting period."""
    return db.execute(
        select(FinancialRecord)
        .where(
            FinancialRecord.reporting_period_id == reporting_period_id,
            FinancialRecord.is_current.is_(True),
        )
        .order_by(FinancialRecord.revision.desc())
    ).scalars().first()


def get_previous_period(
    db: Session, company: Company, period: ReportingPeriod
) -> ReportingPeriod | None:
    """Return the reporting period immediately preceding the given one."""
    return db.execute(
        select(ReportingPeriod)
        .where(
            ReportingPeriod.company_id == company.id,
            ReportingPeriod.period_end < period.period_end,
        )
        .order_by(ReportingPeriod.period_end.desc())
    ).scalars().first()


def get_previous_indicator_values(
    db: Session, company: Company, period: ReportingPeriod
) -> dict[IndicatorCode, float | None]:
    """Indicator values from the previous reporting period, if there is one.

    Used for the reporting-period change comparison. Returns an empty mapping
    when there is no earlier period or it holds no financial record, in which
    case no movement is reported rather than a movement against zero.
    """
    # Imported here to avoid a circular import at module load time.
    from app.utils.presenters import record_to_inputs

    previous_period = get_previous_period(db, company, period)
    if previous_period is None:
        return {}

    previous_record = get_current_record(db, previous_period.id)
    if previous_record is None:
        return {}

    return {
        indicator.code: indicator.value
        for indicator in calculate_indicators(record_to_inputs(previous_record))
    }
