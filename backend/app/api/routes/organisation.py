"""The account's organisation and its financial overview.

Each account belongs to one SME. These routes find it, set it up once for a
new account, and summarise its reporting periods for the overview page. The
summary reuses the same assessment engine as the dashboard; nothing is
scored differently here.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    find_membership,
    find_organisation,
    get_current_user,
    require_admin,
)
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.models.enums import AssessmentStatus
from app.models.membership import (
    ACTIVE,
    ADMIN,
    INVITATION_LIFETIME,
    OrganisationInvitation,
    OrganisationMember,
    hash_token,
    new_invitation_token,
)
from app.models.audit import AuditEvent
from app.services.audit_service import record_event
from app.models.user import User
from app.schemas.company import CompanyCreateRequest, CompanyResponse
from app.schemas.organisation import (
    AuditEventResponse,
    InvitationAcceptRequest,
    InvitationCreatedResponse,
    InvitationCreateRequest,
    InvitationPreviewResponse,
    InvitationResponse,
    MemberResponse,
    MemberUpdateRequest,
    OrganisationSelectRequest,
    OrganisationStatusResponse,
    OverviewPeriod,
    OverviewRecord,
    OverviewResponse,
)
from app.services.assessment_service import assess_financial_inputs
from app.utils.presenters import build_assessment_response, period_length_days, record_to_inputs
from app.utils.records import get_current_record, get_previous_indicator_values

router = APIRouter(prefix="/organisation", tags=["organisation"])


def _status(db: Session, user: User) -> OrganisationStatusResponse:
    organisation, owned = find_organisation(db, user)
    if organisation is not None:
        return OrganisationStatusResponse(
            status="ready",
            organisation=CompanyResponse.model_validate(organisation),
            candidates=[],
            role=find_membership(db, user).role,
        )
    if not owned:
        return OrganisationStatusResponse(status="setup_required", organisation=None, candidates=[])
    return OrganisationStatusResponse(
        status="selection_required",
        organisation=None,
        candidates=[CompanyResponse.model_validate(company) for company in owned],
    )


def create_organisation(db: Session, user: User, payload: CompanyCreateRequest) -> Company:
    """Create the account's one organisation, refusing a second.

    The check here gives a clear message; the partial unique index on
    companies(owner_id) WHERE is_primary is the guarantee, including against
    two requests arriving at once.
    """
    _, owned = find_organisation(db, user)
    if owned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already has an organisation. Each account manages one SME.",
        )
    company = Company(
        owner_id=user.id,
        name=payload.name.strip(),
        registration_number=payload.registration_number,
        industry=payload.industry.strip() if payload.industry else None,
        currency_code=payload.currency_code.upper(),
        is_primary=True,
    )
    db.add(company)
    try:
        db.flush()
        # Whoever sets the organisation up is its first CEO / Admin.
        db.add(OrganisationMember(company_id=company.id, user_id=user.id,
                                  email=user.email.lower(), role=ADMIN, status=ACTIVE))
        record_event(db, company_id=company.id, actor=user, action="organisation.created",
                     entity_type="company", entity_id=company.id,
                     detail={"name": company.name})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already has an organisation. Each account manages one SME.",
        ) from exc
    db.refresh(company)
    return company


@router.get("", response_model=OrganisationStatusResponse, summary="The account's organisation")
def read_organisation(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> OrganisationStatusResponse:
    return _status(db, current_user)


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set up the account's organisation (once)",
)
def set_up_organisation(
    payload: CompanyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    return create_organisation(db, current_user, payload)


@router.post(
    "/select",
    response_model=CompanyResponse,
    summary="Choose the organisation, for an account that owned several companies",
)
def select_organisation(
    payload: OrganisationSelectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """Mark one of the user's own companies as their organisation.

    Only possible while none is chosen. The other companies are left exactly
    as they are; nothing is deleted or moved to another account.
    """
    organisation, owned = find_organisation(db, current_user)
    if organisation is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organisation for this account has already been chosen.",
        )
    chosen = next((company for company in owned if company.id == payload.company_id), None)
    if chosen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    chosen.is_primary = True
    db.add(OrganisationMember(company_id=chosen.id, user_id=current_user.id,
                              email=current_user.email.lower(), role=ADMIN, status=ACTIVE))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organisation for this account has already been chosen.",
        ) from exc
    db.refresh(chosen)
    return chosen


def _require_organisation(db: Session, user: User) -> Company:
    organisation, owned = find_organisation(db, user)
    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose your organisation first." if owned else "Set up your organisation first.",
        )
    return organisation


def _overview_period(db: Session, company: Company, period: ReportingPeriod) -> OverviewPeriod:
    base = dict(
        id=period.id,
        label=period.label,
        period_start=period.period_start,
        period_end=period.period_end,
        period_days=period_length_days(period),
    )
    record = get_current_record(db, period.id)
    if record is None:
        return OverviewPeriod(
            **base, status="no_data", record=None, overall_score=None, classification=None,
            category_scores=[], scored_indicator_count=0, total_indicator_count=0,
            revenue=None, net_profit=None, data_quality_warnings=[],
            assessment_status=None, is_provisional=False, reconciliation_difference=None,
        )

    inputs = record_to_inputs(record)
    output = assess_financial_inputs(
        db, inputs, previous_values=get_previous_indicator_values(db, company, period)
    )
    assessment = build_assessment_response(output, company.id, period, record)

    # The same reliability findings as the dashboard, material ones first.
    issues = sorted(assessment.data_quality_issues, key=lambda i: i.severity != "material")
    warnings = [issue.message for issue in issues]
    insufficient = assessment.assessment_status == AssessmentStatus.INSUFFICIENT_DATA

    return OverviewPeriod(
        **base,
        status="insufficient_data" if insufficient else "assessed",
        assessment_status=assessment.assessment_status,
        is_provisional=assessment.is_provisional,
        reconciliation_difference=assessment.reconciliation_difference,
        record=OverviewRecord(
            id=record.id,
            revision=record.revision,
            source=record.source,
            accounting_identity_ok=record.accounting_identity_ok,
            validation_notes=record.validation_notes,
        ),
        overall_score=assessment.overall_score,
        classification=assessment.classification,
        category_scores=assessment.category_scores,
        scored_indicator_count=assessment.scored_indicator_count,
        total_indicator_count=assessment.total_indicator_count,
        revenue=inputs.revenue,
        net_profit=inputs.net_profit,
        data_quality_warnings=list(dict.fromkeys(warnings)),
    )


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Financial overview of the account's organisation",
)
def read_overview(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> OverviewResponse:
    company = _require_organisation(db, current_user)
    periods = list(
        db.execute(
            select(ReportingPeriod)
            .where(ReportingPeriod.company_id == company.id)
            .order_by(ReportingPeriod.period_end.desc(), ReportingPeriod.period_start.desc())
        ).scalars()
    )
    summaries = [_overview_period(db, company, period) for period in periods]
    return OverviewResponse(
        organisation=CompanyResponse.model_validate(company),
        periods=summaries,
        latest_period_id=summaries[0].id if summaries else None,
        latest_assessed_period_id=next(
            (item.id for item in summaries if item.status == "assessed"), None
        ),
    )


# ---------------------------------------------------------------------------
# Users and roles (CEO / Admin only)
# ---------------------------------------------------------------------------


def _member_response(member: OrganisationMember, you: User, company: Company) -> MemberResponse:
    return MemberResponse(
        id=member.id,
        email=member.email,
        full_name=member.user.full_name if member.user else None,
        role=member.role,
        status=member.status,
        is_you=member.user_id == you.id,
        is_owner=member.user_id is not None and member.user_id == company.owner_id,
    )


def _members(db: Session, company: Company) -> list[OrganisationMember]:
    return list(db.execute(
        select(OrganisationMember)
        .where(OrganisationMember.company_id == company.id)
        .order_by(OrganisationMember.role, OrganisationMember.email)
    ).scalars())


def _member_of(db: Session, company: Company, member_id: int) -> OrganisationMember:
    member = db.get(OrganisationMember, member_id)
    if member is None or member.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    return member


def _guard_owner_and_last_admin(db: Session, company: Company, member: OrganisationMember,
                                action: str) -> None:
    if member.user_id is not None and member.user_id == company.owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The account that set up the organisation cannot be {action}.",
        )
    if member.role == ADMIN:
        admins = [m for m in _members(db, company) if m.role == ADMIN and m.status == ACTIVE]
        if len(admins) <= 1 and member.status == ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The organisation must keep at least one CEO / Admin; this one cannot be {action}.",
            )


@router.get("/members", response_model=list[MemberResponse], summary="Users and their roles")
def list_members(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[MemberResponse]:
    company = _require_organisation(db, current_user)
    return [_member_response(m, current_user, company) for m in _members(db, company)]


@router.patch("/members/{member_id}", response_model=MemberResponse, summary="Change a role")
def change_role(
    member_id: int,
    payload: MemberUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MemberResponse:
    company = _require_organisation(db, current_user)
    member = _member_of(db, company, member_id)
    if member.role != payload.role:
        if member.role == ADMIN:
            _guard_owner_and_last_admin(db, company, member, "made a Finance Clerk")
        old_role = member.role
        member.role = payload.role
        record_event(db, company_id=company.id, actor=current_user, action="member.role_changed",
                     entity_type="member", entity_id=member.id,
                     detail={"email": member.email, "from": old_role, "to": payload.role})
        db.commit()
        db.refresh(member)
    return _member_response(member, current_user, company)


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a user from the organisation",
)
def remove_member(
    member_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Remove someone's access. Their account and the financial data they
    entered are kept; only their membership ends."""
    company = _require_organisation(db, current_user)
    member = _member_of(db, company, member_id)
    _guard_owner_and_last_admin(db, company, member, "removed")
    record_event(db, company_id=company.id, actor=current_user, action="member.removed",
                 entity_type="member", entity_id=member.id,
                 detail={"email": member.email, "role": member.role})
    db.delete(member)
    db.commit()


# ---------------------------------------------------------------------------
# Invitations: the only way to join an organisation
# ---------------------------------------------------------------------------


def _invitation_response(invitation: OrganisationInvitation) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id, email=invitation.email, role=invitation.role,
        state=invitation.state(), created_at=invitation.created_at,
        expires_at=invitation.expires_at,
    )


@router.get("/invitations", response_model=list[InvitationResponse], summary="Invitations")
def list_invitations(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[InvitationResponse]:
    company = _require_organisation(db, current_user)
    rows = db.execute(
        select(OrganisationInvitation)
        .where(OrganisationInvitation.company_id == company.id)
        .order_by(OrganisationInvitation.created_at.desc())
    ).scalars()
    return [_invitation_response(row) for row in rows]


@router.post(
    "/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone by email (returns a single-use link token, once)",
)
def create_invitation(
    payload: InvitationCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> InvitationCreatedResponse:
    """Create a single-use invitation that expires after seven days.

    The token is returned once and stored only as a hash. The recipient must
    sign in with the invited email address and accept it explicitly; nothing
    happens until they do. A new invitation for the same email replaces
    (revokes) any pending one.
    """
    company = _require_organisation(db, current_user)
    email = payload.email.lower()
    if db.execute(select(OrganisationMember).where(OrganisationMember.email == email)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email already belongs to an organisation.",
        )
    now = datetime.now(timezone.utc)
    for pending in db.execute(
        select(OrganisationInvitation).where(
            OrganisationInvitation.company_id == company.id,
            OrganisationInvitation.email == email,
            OrganisationInvitation.accepted_at.is_(None),
            OrganisationInvitation.revoked_at.is_(None),
        )
    ).scalars():
        pending.revoked_at = now
    token, token_hash = new_invitation_token()
    invitation = OrganisationInvitation(
        company_id=company.id, email=email, role=payload.role, token_hash=token_hash,
        created_by_user_id=current_user.id, created_at=now,
        expires_at=now + INVITATION_LIFETIME,
    )
    db.add(invitation)
    db.flush()
    record_event(db, company_id=company.id, actor=current_user, action="invitation.created",
                 entity_type="invitation", entity_id=invitation.id,
                 detail={"email": email, "role": payload.role,
                         "expires_at": invitation.expires_at.isoformat()})
    db.commit()
    db.refresh(invitation)
    return InvitationCreatedResponse(**_invitation_response(invitation).model_dump(), token=token)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an invitation",
)
def revoke_invitation(
    invitation_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    company = _require_organisation(db, current_user)
    invitation = db.get(OrganisationInvitation, invitation_id)
    if invitation is None or invitation.company_id != company.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")
    if invitation.state() == "pending":
        invitation.revoked_at = datetime.now(timezone.utc)
        record_event(db, company_id=company.id, actor=current_user,
                     action="invitation.revoked", entity_type="invitation",
                     entity_id=invitation.id, detail={"email": invitation.email})
        db.commit()


def _invitation_for_token(db: Session, token: str) -> OrganisationInvitation:
    invitation = db.execute(
        select(OrganisationInvitation).where(
            OrganisationInvitation.token_hash == hash_token(token.strip())
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="This invitation link is not valid.")
    return invitation


@router.get(
    "/invitations/preview",
    response_model=InvitationPreviewResponse,
    summary="What an invitation link is for",
)
def preview_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationPreviewResponse:
    invitation = _invitation_for_token(db, token)
    return InvitationPreviewResponse(
        organisation_name=invitation.company.name, role=invitation.role,
        email=invitation.email, state=invitation.state(),
    )


@router.post(
    "/invitations/accept",
    response_model=OrganisationStatusResponse,
    summary="Accept an invitation as the signed-in user",
)
def accept_invitation(
    payload: InvitationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganisationStatusResponse:
    """Join the organisation, if every condition holds.

    The token must be pending (not used, revoked or expired), the signed-in
    account's email must be the invited email, and the account must not
    already belong to or own an organisation. The token then cannot be used
    again.
    """
    invitation = _invitation_for_token(db, payload.token)
    state = invitation.state()
    if state != "pending":
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail=f"This invitation has been {state}. Ask for a new one.")
    if current_user.email.lower() != invitation.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was issued to a different email address. Sign in with "
            "the invited email to accept it.",
        )
    if find_membership(db, current_user) is not None or db.execute(
        select(Company).where(Company.owner_id == current_user.id)
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This account already belongs to an organisation.")
    now = datetime.now(timezone.utc)
    invitation.accepted_at = now
    invitation.accepted_by_user_id = current_user.id
    member = OrganisationMember(company_id=invitation.company_id, user_id=current_user.id,
                                email=current_user.email.lower(), role=invitation.role,
                                status=ACTIVE)
    db.add(member)
    db.flush()
    record_event(db, company_id=invitation.company_id, actor=current_user,
                 action="invitation.accepted", entity_type="member", entity_id=member.id,
                 detail={"email": member.email, "role": member.role,
                         "invitation_id": invitation.id})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This invitation has already been used.") from exc
    return _status(db, current_user)


@router.get(
    "/audit-log",
    response_model=list[AuditEventResponse],
    summary="Who changed what (newest first; read-only)",
)
def read_audit_log(
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    company = _require_organisation(db, current_user)
    return list(db.execute(
        select(AuditEvent)
        .where(AuditEvent.company_id == company.id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(max(1, min(limit, 500)))
    ).scalars())

