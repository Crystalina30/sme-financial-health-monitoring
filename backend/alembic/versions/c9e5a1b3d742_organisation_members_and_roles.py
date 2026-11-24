"""organisation members and roles

One organisation can now have several users, each a CEO/Admin ("admin") or a
Finance Clerk ("clerk").

* Creates organisation_members (company, user, email, role, status).
* Every existing organisation (a primary company) gets its owner as an
  active admin, so current accounts keep full access to their data.
* Companies of accounts that never chose an organisation (not primary) get
  no member; their owner becomes admin when they choose, as before.
* No company, period or financial record is changed.

Revision ID: c9e5a1b3d742
Revises: b8d4f0a2c631
Create Date: 2026-11-25 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "c9e5a1b3d742"
down_revision = "b8d4f0a2c631"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organisation_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organisation_members_company_id", "organisation_members",
                    ["company_id"])
    op.execute(
        """
        INSERT INTO organisation_members (company_id, user_id, email, role, status)
        SELECT c.id, u.id, lower(u.email), 'admin', 'active'
        FROM companies c JOIN users u ON u.id = c.owner_id
        WHERE c.is_primary
        """
    )


def downgrade() -> None:
    op.drop_index("ix_organisation_members_company_id", table_name="organisation_members")
    op.drop_table("organisation_members")
