"""Shared FastAPI dependencies.

These enforce authentication and, just as importantly, user data isolation:
every company lookup goes through ``get_owned_company``, so a user can never
read or change another user's data by guessing an identifier.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.company import Company, ReportingPeriod
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if credentials is None:
        raise CREDENTIALS_EXCEPTION

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise CREDENTIALS_EXCEPTION

    try:
        user_id = int(subject)
    except ValueError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user


def get_owned_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """Fetch a company, but only if the current user owns it.

    A company belonging to another user is reported as not found rather than
    forbidden, so the API does not confirm that the identifier exists.
    """
    company = db.get(Company, company_id)
    if company is None or company.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found."
        )
    return company


def get_owned_period(
    db: Session, company: Company, reporting_period_id: int
) -> ReportingPeriod:
    """Fetch a reporting period belonging to the given company."""
    period = db.execute(
        select(ReportingPeriod).where(
            ReportingPeriod.id == reporting_period_id,
            ReportingPeriod.company_id == company.id,
        )
    ).scalar_one_or_none()
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reporting period not found."
        )
    return period
