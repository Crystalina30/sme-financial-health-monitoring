"""trial balance input

Lets financial data be entered as a raw trial balance (one row per account)
instead of finished statement totals.

* financial_records.source records how the figures were obtained. Existing
  records were typed in as statement totals, so they are set to "statement".
* trial_balance_lines holds the account balances behind a record derived from
  a trial balance, so each figure can be traced back to its accounts.

Revision ID: 8c4f2b6d9a31
Revises: 5a1d9c3e7f20
Create Date: 2026-11-22 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "8c4f2b6d9a31"
down_revision = "5a1d9c3e7f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_records",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="statement"),
    )
    op.create_table(
        "trial_balance_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "financial_record_id",
            sa.Integer(),
            sa.ForeignKey("financial_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("category", sa.String(length=40), nullable=False),
    )
    op.create_index(
        "ix_trial_balance_lines_financial_record_id",
        "trial_balance_lines",
        ["financial_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_trial_balance_lines_financial_record_id", table_name="trial_balance_lines")
    op.drop_table("trial_balance_lines")
    op.drop_column("financial_records", "source")
