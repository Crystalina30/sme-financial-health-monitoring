"""Organisation membership: who works in the SME, and in what role.

One organisation (an SME) has several users. Each user belongs to at most one
organisation, with one role:

* ``admin``  CEO / Admin: full access, including the financial health
             dashboard, scores and analysis, deleting data, company settings,
             and managing users and roles.
* ``clerk``  Finance Clerk: maintains the accounting data (trial balance
             import, financial records, reporting periods) but cannot see the
             confidential health assessment, delete data, or manage the
             organisation.

People join only by accepting an invitation (``OrganisationInvitation``):
a single-use, random token that expires, issued by an admin for one email
address and accepted by a signed-in user with that email. Nobody is added to
an organisation without accepting, and admins never handle passwords.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ADMIN = "admin"
CLERK = "clerk"
ROLES = (ADMIN, CLERK)

ACTIVE = "active"
INVITED = "invited"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrganisationMember(Base):
    __tablename__ = "organisation_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Unique: a user belongs to one organisation. Empty while invited.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # Lower-case; unique, so an email can be in only one organisation.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    company: Mapped["Company"] = relationship()  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821


#: How long an invitation link stays valid.
INVITATION_LIFETIME = timedelta(days=7)


def new_invitation_token() -> tuple[str, str]:
    """A random token for the link, and the hash that is stored instead."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OrganisationInvitation(Base):
    """An invitation to join an organisation in a role.

    Only the SHA-256 hash of the token is stored; the token itself is shown
    once to the admin who creates it. An invitation is used at most once,
    expires, and can be revoked. Rows are kept after use as a record.
    """

    __tablename__ = "organisation_invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship()  # noqa: F821

    def state(self, now: datetime | None = None) -> str:
        now = now or _utcnow()
        expires = self.expires_at
        if expires.tzinfo is None:  # SQLite returns naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        if self.revoked_at is not None:
            return "revoked"
        if self.accepted_at is not None:
            return "accepted"
        if expires <= now:
            return "expired"
        return "pending"

