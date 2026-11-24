"""Schemas for the account's organisation and its financial overview."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import AssessmentStatus, HealthClassification
from app.schemas.assessment import CategoryScoreResponse
from app.schemas.company import CompanyResponse


class OrganisationStatusResponse(BaseModel):
    """Which organisation the account works with.

    * ``ready``: the organisation is known.
    * ``setup_required``: the account has no organisation yet.
    * ``selection_required``: the account owned several companies before
      the single-organisation change; the owner must choose one. The others
      are kept but not used.
    """

    status: Literal["ready", "setup_required", "selection_required"]
    organisation: CompanyResponse | None
    candidates: list[CompanyResponse]
    # The user's role in the organisation: "admin" (CEO / Admin) or "clerk"
    # (Finance Clerk). None until they belong to one.
    role: Literal["admin", "clerk"] | None = None


class OrganisationSelectRequest(BaseModel):
    company_id: int


class MemberResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: Literal["admin", "clerk"]
    # "active": has an account and has joined; "invited": joins on registering.
    status: Literal["active", "invited"]
    is_you: bool
    is_owner: bool


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_email: str
    action: str
    entity_type: str
    entity_id: int | None
    detail: dict


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: Literal["admin", "clerk"]


class InvitationResponse(BaseModel):
    id: int
    email: str
    role: Literal["admin", "clerk"]
    state: Literal["pending", "accepted", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime


class InvitationCreatedResponse(InvitationResponse):
    # Shown once, here only: the database keeps a hash of it.
    token: str


class InvitationPreviewResponse(BaseModel):
    organisation_name: str
    role: Literal["admin", "clerk"]
    email: str
    state: Literal["pending", "accepted", "expired", "revoked"]


class InvitationAcceptRequest(BaseModel):
    token: str


class MemberUpdateRequest(BaseModel):
    role: Literal["admin", "clerk"]


class OverviewRecord(BaseModel):
    id: int
    revision: int
    source: str
    accounting_identity_ok: bool
    validation_notes: str | None


class OverviewPeriod(BaseModel):
    """One reporting period, with its assessment when one can be made."""

    id: int
    label: str
    period_start: date
    period_end: date
    period_days: int
    # no_data: no financial record yet; assessed: a score was calculated;
    # insufficient_data: a record exists but no category could be scored.
    status: Literal["no_data", "assessed", "insufficient_data"]
    record: OverviewRecord | None
    overall_score: float | None
    classification: HealthClassification | None
    category_scores: list[CategoryScoreResponse]
    scored_indicator_count: int
    total_indicator_count: int
    revenue: float | None
    net_profit: float | None
    # Reliability of the assessment (None when there is no data), separate
    # from the health classification.
    assessment_status: AssessmentStatus | None
    is_provisional: bool
    # The material problems that make the assessment provisional, then the
    # informational notes (missing indicators, an unusual period, ...).
    data_quality_warnings: list[str]
    reconciliation_difference: float | None


class OverviewResponse(BaseModel):
    organisation: CompanyResponse
    # Newest first, by end date then start date (never by label).
    periods: list[OverviewPeriod]
    latest_period_id: int | None
    latest_assessed_period_id: int | None
