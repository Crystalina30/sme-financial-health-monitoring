"""Financial record routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_company, get_owned_period
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.models.financial_record import FinancialRecord
from app.models.user import User
from app.schemas.financial_record import (
    FinancialRecordCreateRequest,
    FinancialRecordResponse,
    FinancialRecordUpdateRequest,
)
from app.services.validation_service import validate_financial_inputs
from app.utils.records import get_current_record

router = APIRouter(tags=["financial records"])


def _apply_values(record: FinancialRecord, payload) -> None:
    """Copy statement values from a request payload onto a record."""
    for field_name in (
        "revenue",
        "cost_of_goods_sold",
        "operating_expenses",
        "interest_expense",
        "tax_expense",
        "net_profit",
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "current_assets",
        "total_assets",
        "current_liabilities",
        "total_liabilities",
        "total_equity",
    ):
        setattr(record, field_name, getattr(payload, field_name))


@router.post(
    "/companies/{company_id}/financial-records",
    response_model=FinancialRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enter financial data for a reporting period",
)
def create_financial_record(
    payload: FinancialRecordCreateRequest,
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> FinancialRecord:
    """Store financial statement values for one reporting period.

    Cross-field validation runs before the record is stored. A record that
    fails a blocking check — the accounting identity above all — is rejected
    rather than stored, so incorrect financial data is never silently
    accepted. Non-blocking findings are stored as notes against the record.
    """
    period = get_owned_period(db, company, payload.reporting_period_id)

    if get_current_record(db, period.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reporting period already has a financial record. "
            "Use the update endpoint to store a correction.",
        )

    validation = validate_financial_inputs(payload.to_financial_inputs())
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Financial data failed validation.", "errors": validation.errors},
        )

    record = FinancialRecord(
        reporting_period_id=period.id,
        revision=1,
        is_current=True,
        accounting_identity_ok=validation.accounting_identity_ok,
        validation_notes=validation.notes,
    )
    _apply_values(record, payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "/companies/{company_id}/financial-records",
    response_model=list[FinancialRecordResponse],
    summary="List current financial records for a company",
)
def list_financial_records(
    company: Company = Depends(get_owned_company), db: Session = Depends(get_db)
) -> list[FinancialRecord]:
    return list(
        db.execute(
            select(FinancialRecord)
            .join(ReportingPeriod)
            .where(
                ReportingPeriod.company_id == company.id,
                FinancialRecord.is_current.is_(True),
            )
            .order_by(ReportingPeriod.period_end)
        ).scalars()
    )


@router.put(
    "/financial-records/{record_id}",
    response_model=FinancialRecordResponse,
    summary="Correct a financial record",
)
def update_financial_record(
    record_id: int,
    payload: FinancialRecordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialRecord:
    """Store a correction as a new revision.

    The superseded revision is kept, so an assessment produced earlier can
    still be traced to the figures it was based on.
    """
    record = db.get(FinancialRecord, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Financial record not found."
        )

    period = db.get(ReportingPeriod, record.reporting_period_id)
    company = db.get(Company, period.company_id) if period else None
    if company is None or company.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Financial record not found."
        )

    validation = validate_financial_inputs(payload.to_financial_inputs())
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Financial data failed validation.", "errors": validation.errors},
        )

    record.is_current = False
    revision = FinancialRecord(
        reporting_period_id=record.reporting_period_id,
        revision=record.revision + 1,
        is_current=True,
        accounting_identity_ok=validation.accounting_identity_ok,
        validation_notes=validation.notes,
    )
    _apply_values(revision, payload)
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision
