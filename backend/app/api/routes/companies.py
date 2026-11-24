"""Company and reporting period routes."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    find_organisation,
    get_current_user,
    get_admin_company,
    get_owned_company,
    get_owned_period,
)
from app.api.routes.organisation import create_organisation
from app.models.financial_record import FinancialRecord
from app.services.audit_service import record_event
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.models.user import User
from app.schemas.company import (
    CompanyCreateRequest,
    CompanyResponse,
    CompanyUpdateRequest,
    ReportingPeriodCreateRequest,
    ReportingPeriodResponse,
    ReportingPeriodUpdateRequest,
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post(
    "", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED,
    summary="Create the account's organisation (same as POST /organisation)",
)
def create_company(
    payload: CompanyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """Kept for compatibility. An account has one organisation, so a second
    company is refused with 409, exactly as POST /organisation does."""
    return create_organisation(db, current_user, payload)


@router.get("", response_model=list[CompanyResponse], summary="Your organisation, as a list")
def list_companies(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Company]:
    """Kept for compatibility: a list holding the account's one organisation."""
    organisation, _ = find_organisation(db, current_user)
    return [organisation] if organisation else []


@router.get("/{company_id}", response_model=CompanyResponse, summary="Company details")
def read_company(company: Company = Depends(get_owned_company)) -> Company:
    return company


@router.put("/{company_id}", response_model=CompanyResponse, summary="Update a company")
def update_company(
    payload: CompanyUpdateRequest,
    company: Company = Depends(get_admin_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "currency_code" in updates:
        updates["currency_code"] = updates["currency_code"].upper()
    changed = {name: {"from": getattr(company, name), "to": value}
               for name, value in updates.items() if getattr(company, name) != value}
    for field_name, value in updates.items():
        setattr(company, field_name, value)
    if changed:
        record_event(db, company_id=company.id, actor=current_user, action="company.updated",
                     entity_type="company", entity_id=company.id, detail={"changed": changed})
    db.commit()
    db.refresh(company)
    return company


@router.post(
    "/{company_id}/reporting-periods",
    response_model=ReportingPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reporting period",
)
def create_reporting_period(
    payload: ReportingPeriodCreateRequest,
    company: Company = Depends(get_owned_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportingPeriod:
    period = ReportingPeriod(
        company_id=company.id,
        label=payload.label.strip(),
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    db.add(period)
    try:
        db.flush()
        record_event(db, company_id=company.id, actor=current_user, action="period.created",
                     entity_type="period", entity_id=period.id,
                     detail={"label": period.label, "start": str(period.period_start),
                             "end": str(period.period_end)})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This company already has a reporting period labelled "
            f"'{payload.label.strip()}'.",
        ) from exc
    db.refresh(period)
    return period


@router.get(
    "/{company_id}/reporting-periods",
    response_model=list[ReportingPeriodResponse],
    summary="List reporting periods, oldest first",
)
def list_reporting_periods(
    company: Company = Depends(get_owned_company), db: Session = Depends(get_db)
) -> list[ReportingPeriod]:
    return list(
        db.execute(
            select(ReportingPeriod)
            .where(ReportingPeriod.company_id == company.id)
            .order_by(ReportingPeriod.period_end)
        ).scalars()
    )


@router.put(
    "/{company_id}/reporting-periods/{period_id}",
    response_model=ReportingPeriodResponse,
    summary="Correct a reporting period's label or dates",
)
def update_reporting_period(
    period_id: int,
    payload: ReportingPeriodUpdateRequest,
    company: Company = Depends(get_owned_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportingPeriod:
    """Change the label and dates of a period.

    The financial data entered for the period is kept. Ratios that depend on
    the period's length (days sales outstanding, asset turnover) are
    recalculated from the new dates the next time they are shown.
    """
    period = get_owned_period(db, company, period_id)
    before = {"label": period.label, "start": str(period.period_start),
              "end": str(period.period_end)}
    period.label = payload.label.strip()
    period.period_start = payload.period_start
    period.period_end = payload.period_end
    after = {"label": period.label, "start": str(period.period_start),
             "end": str(period.period_end)}
    if before != after:
        record_event(db, company_id=company.id, actor=current_user, action="period.updated",
                     entity_type="period", entity_id=period.id,
                     detail={"from": before, "to": after})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This company already has a reporting period labelled "
            f"'{payload.label.strip()}'.",
        ) from exc
    db.refresh(period)
    return period


@router.delete(
    "/{company_id}/reporting-periods/{period_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reporting period and all of its financial data",
)
def delete_reporting_period(
    period_id: int,
    confirm_label: str,
    company: Company = Depends(get_admin_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Permanently delete a period with everything entered for it.

    This removes the period, every revision of its financial record, and the
    trial balance lines behind them (ORM cascade, backed by ON DELETE
    CASCADE in the database). It cannot be undone; the interface asks for
    confirmation first.
    """
    period = get_owned_period(db, company, period_id)
    # The caller must name the period being deleted, so a mistyped id or a
    # replayed request cannot delete the wrong one.
    if confirm_label.strip() != period.label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"To delete this period, confirm it by its label ('{period.label}').",
        )
    revisions = db.execute(
        select(FinancialRecord)
        .where(FinancialRecord.reporting_period_id == period.id)
        .order_by(FinancialRecord.revision)
    ).scalars().all()
    # A snapshot of what is deleted, kept in the audit trail.
    record_event(
        db, company_id=company.id, actor=current_user, action="period.deleted",
        entity_type="period", entity_id=period.id,
        detail={
            "label": period.label, "start": str(period.period_start),
            "end": str(period.period_end),
            "revisions": [
                {"revision": r.revision, "source": r.source, "revenue": float(r.revenue),
                 "net_profit": float(r.net_profit), "total_assets": float(r.total_assets),
                 "created_at": r.created_at.isoformat() if r.created_at else None}
                for r in revisions
            ],
        },
    )
    db.delete(period)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
