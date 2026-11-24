"""audit fixes: invitations, audit trail, revision safety

* organisation_invitations: single-use, expiring invitation tokens (stored
  as SHA-256 hashes). Joining now requires accepting one.
* Membership rows still marked "invited" from the earlier email-only scheme
  are removed: they never granted access and could be claimed by anyone who
  registered with that email. (There were none in the live database.)
* audit_events: append-only record of who changed what.
* financial_records.created_by_user_id: who entered each revision.
* uq_record_one_current_per_period: at most one current revision per
  reporting period, so simultaneous corrections cannot both become current.

No financial figure is changed.

Revision ID: d4f6b2c8e953
Revises: c9e5a1b3d742
Create Date: 2026-11-26 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "d4f6b2c8e953"
down_revision = "c9e5a1b3d742"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organisation_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_organisation_invitations_company_id", "organisation_invitations",
                    ["company_id"])
    op.create_index("ix_organisation_invitations_email", "organisation_invitations", ["email"])
    op.execute("DELETE FROM organisation_members WHERE status = 'invited' OR user_id IS NULL")

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_email", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.add_column(
        "financial_records",
        sa.Column("created_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index(
        "uq_record_one_current_per_period", "financial_records", ["reporting_period_id"],
        unique=True, postgresql_where=sa.text("is_current"), sqlite_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_record_one_current_per_period", table_name="financial_records")
    op.drop_column("financial_records", "created_by_user_id")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_company_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_organisation_invitations_email", table_name="organisation_invitations")
    op.drop_index("ix_organisation_invitations_company_id", table_name="organisation_invitations")
    op.drop_table("organisation_invitations")
