"""Shared FastAPI dependencies.

These enforce authentication, organisation isolation and roles:

* every company lookup goes through ``get_owned_company`` (any member of the
  organisation) or ``get_admin_company`` (CEO/Admin only), so a user can never
  read or change another organisation's data by guessing an identifier;
* a Finance Clerk who calls an admin-only endpoint gets 403, whatever the
  interface shows. The permission table is in ``PERMISSIONS`` below.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.company import Company, ReportingPeriod
from app.models.membership import ACTIVE, ADMIN, CLERK, OrganisationMember
from app.models.user import User

#: Who may do what. Enforced by the dependencies used on each route.
PERMISSIONS = {
    "view financial dashboard, health scores, indicators and analysis": (ADMIN,),
    "view the financial overview": (ADMIN,),
    "view thresholds and scoring methodology": (ADMIN,),
    "view financial statements and trial balances": (ADMIN, CLERK),
    "import a trial balance": (ADMIN, CLERK),
    "create and update financial records": (ADMIN, CLERK),
    "create, read and update reporting periods": (ADMIN, CLERK),
    "delete reporting periods and their financial records": (ADMIN,),
    "change company settings": (ADMIN,),
    "manage users and roles": (ADMIN,),
}

FORBIDDEN_FOR_CLERK = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Only the CEO / Admin can do this. Finance Clerks can maintain the financial "
    "data but cannot view the health assessment, delete data or manage the organisation.",
)

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


def find_membership(db: Session, user: User) -> OrganisationMember | None:
    """The user's membership, if they have accepted one.

    An invitation never turns into a membership by itself: the signed-in
    recipient must accept it with its token (see the organisation routes).
    """
    return db.execute(
        select(OrganisationMember).where(
            OrganisationMember.user_id == user.id, OrganisationMember.status == ACTIVE
        )
    ).scalar_one_or_none()


def find_organisation(db: Session, user: User) -> tuple[Company | None, list[Company]]:
    """The user's organisation, and any companies they own without one.

    Returns (organisation, owned). The organisation is None when the user is
    in no organisation: setup is needed, or (for an account that held several
    companies before the single-organisation change) a choice.
    """
    membership = find_membership(db, user)
    if membership is not None:
        return membership.company, [membership.company]
    has_members = select(OrganisationMember.id).where(
        OrganisationMember.company_id == Company.id
    ).exists()
    owned = list(
        db.execute(
            select(Company)
            .where(Company.owner_id == user.id, ~has_members)
            .order_by(Company.id)
        ).scalars()
    )
    return None, owned


def user_role(db: Session, user: User) -> str | None:
    membership = find_membership(db, user)
    return membership.role if membership else None


def company_for_member(db: Session, user: User, company_id: int) -> tuple[Company, str]:
    """The company and the user's role in it, or 404 if they are not a member.

    A company the user is not a member of is reported as not found rather
    than forbidden, so the API does not confirm that the identifier exists.
    """
    membership = find_membership(db, user)
    if membership is None or membership.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return membership.company, membership.role


def get_owned_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """The organisation, for any of its members (CEO/Admin or Finance Clerk)."""
    company, _ = company_for_member(db, current_user, company_id)
    return company


def get_admin_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """The organisation, for its CEO/Admin only (403 for a Finance Clerk)."""
    company, role = company_for_member(db, current_user, company_id)
    if role != ADMIN:
        raise FORBIDDEN_FOR_CLERK
    return company


def require_admin(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    """Any admin-only action that is not tied to a company in the URL."""
    if user_role(db, current_user) != ADMIN:
        raise FORBIDDEN_FOR_CLERK
    return current_user


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
