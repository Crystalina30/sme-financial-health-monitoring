"""trial balance traceability

Keeps, for every trial balance line, the account group given in the source
export and a reference to the file, sheet and row it was imported from.
Existing lines were typed in, so they get empty values.

Revision ID: d2e7a4c1b958
Revises: 8c4f2b6d9a31
Create Date: 2026-11-22 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e7a4c1b958"
down_revision = "8c4f2b6d9a31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trial_balance_lines",
        sa.Column("account_group", sa.String(length=120), nullable=False, server_default=""),
    )
    op.add_column(
        "trial_balance_lines",
        sa.Column("source_ref", sa.String(length=200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("trial_balance_lines", "source_ref")
    op.drop_column("trial_balance_lines", "account_group")
