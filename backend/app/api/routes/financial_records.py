"""Financial record routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    company_for_member,
    get_current_user,
    get_owned_company,
    get_owned_period,
)
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
from app.services.audit_service import record_event
from app.utils.records import commit_revision, get_current_record, lock_period

router = APIRouter(tags=["financial records"])


_FIELDS = (
        "revenue",
        "cost_of_goods_sold",
        "operating_expenses",
        "interest_expense",
        "tax_expense",
        "net_profit",
        "other_operating_income",
        "other_income",
        "other_expenses",
        "presentation_unit",
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "current_assets",
        "total_assets",
        "current_liabilities",
        "total_liabilities",
        "total_equity",
        "retained_earnings",
    )


def _apply_values(record: FinancialRecord, payload) -> None:
    """Copy statement values from a request payload onto a record."""
    for field_name in _FIELDS:
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialRecord:
    """Store financial statement values for one reporting period.

    Cross-field validation runs before the record is stored. A record that
    fails a blocking check — the accounting identity above all — is rejected
    rather than stored, so incorrect financial data is never silently
    accepted. Non-blocking findings are stored as notes against the record.
    """
    period = get_owned_period(db, company, payload.reporting_period_id)
    lock_period(db, period.id)

    if get_current_record(db, period.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reporting period already has a financial record. "
            "Use the update endpoint to store a correction.",
        )

    validation = validate_financial_inputs(
        payload.to_financial_inputs(), Decimal(str(payload.presentation_unit))
    )
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
        created_by_user_id=current_user.id,
    )
    _apply_values(record, payload)
    db.add(record)
    db.flush()
    record_event(db, company_id=company.id, actor=current_user, action="record.created",
                 entity_type="financial_record", entity_id=record.id,
                 detail={"period": period.label, "revision": 1, "source": "statement"})
    commit_revision(db)
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
    try:
        company_for_member(db, current_user, period.company_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Financial record not found."
        ) from exc

    validation = validate_financial_inputs(
        payload.to_financial_inputs(), Decimal(str(payload.presentation_unit))
    )
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Financial data failed validation.", "errors": validation.errors},
        )

    # Only the current revision can be corrected. Lock the period first and
    # re-read, so a correction saved a moment ago by someone else is seen.
    lock_period(db, period.id)
    db.refresh(record)
    if not record.is_current:
        current = get_current_record(db, period.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Revision {record.revision} has been superseded by revision "
            f"{current.revision if current else '?'}. Reload the latest figures and make "
            "your correction to those.",
        )

    changed = {
        name: {"from": float(getattr(record, name)) if getattr(record, name) is not None else None,
               "to": getattr(payload, name)}
        for name in _FIELDS
        if (float(getattr(record, name)) if getattr(record, name) is not None else None)
        != (float(getattr(payload, name)) if getattr(payload, name) is not None else None)
    }
    record.is_current = False
    revision = FinancialRecord(
        reporting_period_id=record.reporting_period_id,
        revision=record.revision + 1,
        is_current=True,
        accounting_identity_ok=validation.accounting_identity_ok,
        validation_notes=validation.notes,
        created_by_user_id=current_user.id,
    )
    _apply_values(revision, payload)
    db.add(revision)
    db.flush()
    record_event(db, company_id=period.company_id, actor=current_user,
                 action="record.corrected", entity_type="financial_record",
                 entity_id=revision.id,
                 detail={"period": period.label, "from_revision": record.revision,
                         "to_revision": revision.revision, "changed": changed})
    commit_revision(db)
    db.refresh(revision)
    return revision
