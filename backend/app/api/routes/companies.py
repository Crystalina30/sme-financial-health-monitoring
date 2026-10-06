"""Company and reporting period routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_company
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.models.user import User
from app.schemas.company import (
    CompanyCreateRequest,
    CompanyResponse,
    CompanyUpdateRequest,
    ReportingPeriodCreateRequest,
    ReportingPeriodResponse,
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post(
    "", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED,
    summary="Create a company",
)
def create_company(
    payload: CompanyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    company = Company(
        owner_id=current_user.id,
        name=payload.name.strip(),
        registration_number=payload.registration_number,
        industry=payload.industry,
        currency_code=payload.currency_code.upper(),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("", response_model=list[CompanyResponse], summary="List your companies")
def list_companies(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Company]:
    return list(
        db.execute(
            select(Company)
            .where(Company.owner_id == current_user.id)
            .order_by(Company.name)
        ).scalars()
    )


@router.get("/{company_id}", response_model=CompanyResponse, summary="Company details")
def read_company(company: Company = Depends(get_owned_company)) -> Company:
    return company


@router.put("/{company_id}", response_model=CompanyResponse, summary="Update a company")
def update_company(
    payload: CompanyUpdateRequest,
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> Company:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "currency_code" in updates:
        updates["currency_code"] = updates["currency_code"].upper()
    for field_name, value in updates.items():
        setattr(company, field_name, value)
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
