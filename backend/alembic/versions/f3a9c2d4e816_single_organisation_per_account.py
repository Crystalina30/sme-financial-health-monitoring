"""single organisation per account

Each account now belongs to one organisation (SME). The companies table and
every company ID are kept; nothing is deleted or reassigned.

* companies.is_primary marks the account's organisation.
* An account that owns exactly one company has it marked primary
  automatically: there is no doubt which organisation is theirs.
* An account that owns several companies is left with none marked. Which one
  is "the" organisation is the owner's decision, so they are asked to choose
  once at their next login; the others are kept untouched.
* A partial unique index allows at most one primary company per owner, so
  the database itself refuses a second organisation.

Revision ID: f3a9c2d4e816
Revises: d2e7a4c1b958
Create Date: 2026-11-24 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a9c2d4e816"
down_revision = "d2e7a4c1b958"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE companies SET is_primary = true
        WHERE owner_id IN (
            SELECT owner_id FROM companies GROUP BY owner_id HAVING COUNT(*) = 1
        )
        """
    )
    op.create_index(
        "uq_companies_one_organisation_per_owner",
        "companies",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        sqlite_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index("uq_companies_one_organisation_per_owner", table_name="companies")
    op.drop_column("companies", "is_primary")
