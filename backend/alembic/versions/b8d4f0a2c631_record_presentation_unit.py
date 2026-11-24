"""record presentation unit

The precision the source figures of a record were rounded to: 0.01 (exact,
to the sen), 1, 1000 (RM'000) or 1000000 (RM million). It sets the tolerance
of the reconciliation checks (see validation_service). Existing records were
entered as exact figures, so they get 0.01 and their checks are unchanged.

Revision ID: b8d4f0a2c631
Revises: a7c3e91f5b20
Create Date: 2026-11-24 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "b8d4f0a2c631"
down_revision = "a7c3e91f5b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_records",
        sa.Column("presentation_unit", sa.Numeric(12, 2), nullable=False, server_default="0.01"),
    )


def downgrade() -> None:
    op.drop_column("financial_records", "presentation_unit")
