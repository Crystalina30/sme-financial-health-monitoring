"""income statement reconciliation

Adds the lines that sit between operating profit and net profit, so that a
statement with legitimate other income or expenses can reconcile:

* financial_records.other_operating_income
* financial_records.other_income        (non-operating income)
* financial_records.other_expenses      (non-operating expenses and losses)

Existing records get 0 for each, which is what they implicitly assumed; no
existing figure is changed.

Revision ID: a7c3e91f5b20
Revises: f3a9c2d4e816
Create Date: 2026-11-24 15:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "a7c3e91f5b20"
down_revision = "f3a9c2d4e816"
branch_labels = None
depends_on = None

_COLUMNS = ("other_operating_income", "other_income", "other_expenses")


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column(
            "financial_records",
            sa.Column(name, sa.Numeric(18, 2), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("financial_records", name)
