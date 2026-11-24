"""scoring methodology 2.0

Adds the explicit four-point reference system for indicator scoring, the
documented basis of each threshold, and the retained earnings input used by
the Altman Z'' benchmark.

* threshold_configurations.floor_value and target_value are back-filled with
  the defaults that reproduce methodology-1.0 scores exactly: target one span
  beyond the concern threshold, floor two spans beyond the distress threshold.
* threshold_configurations.basis is filled for the ten standard indicators.
  Source and description texts are updated only where they still hold the
  original seeded wording, so any edits made since are kept.
* financial_records.retained_earnings is added as nullable. Existing records
  have no value, which is shown as "benchmark unavailable", never as zero.

Revision ID: 5a1d9c3e7f20
Revises: bc237d07506a
Create Date: 2026-11-21 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "5a1d9c3e7f20"
down_revision = "bc237d07506a"
branch_labels = None
depends_on = None

_REFERENCE_BASIS = (
    " Floor and target: project-defined defaults (target one span beyond the concern "
    "threshold, floor two spans beyond the distress threshold)."
)

# indicator code -> (original source text, new source text, basis, new description or None)
_TEXTS = {
    "current_ratio": (
        "Conventional working-capital guidance: a current ratio below 1.0 means current "
        "liabilities exceed current assets.",
        "At 1.0, current liabilities equal current assets. 1.5 is a conventional "
        "working-capital cushion. No universal threshold exists; the ratio's link to "
        "failure is strongest at low levels (Li, 2024).",
        "Distress: definitional (current assets equal current liabilities). "
        "Concern: conventional.",
        None,
    ),
    "quick_ratio": (
        "Conventional liquidity guidance: a quick ratio below 1.0 indicates reliance on "
        "inventory conversion to meet short-term obligations.",
        "Conventional 'acid test': below 1.0, short-term obligations cannot be met "
        "without selling inventory. The 0.7 distress level is a project-defined default.",
        "Concern: conventional (acid test of 1.0). Distress: project-defined.",
        None,
    ),
    "gross_profit_margin": (
        "General small-business profitability guidance on the margin required to cover "
        "operating costs.",
        "Project-defined default. Typical gross margins differ widely between industries "
        "(Platt & Platt, 1991, on industry-relative ratios), so these values should be "
        "set per sector where possible.",
        "Concern and distress: project-defined; strongly industry-dependent.",
        None,
    ),
    "net_profit_margin": (
        "Sustained losses are a recognised symptom of financial distress; a margin at or "
        "below zero marks the distress point.",
        "A margin at or below zero means the period made a loss; profitability is a core "
        "dimension of distress research (Beaver, 1966; Altman, 1968). 5% is a "
        "conventional concern level.",
        "Distress: definitional (break-even). Concern: conventional.",
        None,
    ),
    "return_on_assets": (
        "Return on assets is a standard component of financial distress models; a "
        "negative return marks the distress point.",
        "A return at or below zero means the assets produced a loss; earnings relative to "
        "assets is a standard distress-model component (Beaver, 1966; Altman, 1968). 5% "
        "is a conventional concern level.",
        "Distress: definitional (break-even). Concern: conventional.",
        None,
    ),
    "debt_to_equity": (
        "Conventional leverage guidance: liabilities exceeding equity by more than about "
        "1.5 times indicates elevated gearing.",
        "Conventional leverage guidance: liabilities above about 1.5 times equity indicate "
        "elevated gearing, above 2.5 times high gearing. Zero or negative equity is "
        "scored as the worst case. Suitable gearing varies by industry.",
        "Concern and distress: conventional.",
        None,
    ),
    "debt_ratio": (
        "Conventional solvency guidance: liabilities funding more than about 60 per cent "
        "of assets indicates elevated balance-sheet risk.",
        "Conventional solvency guidance: liabilities funding more than about 60% of assets "
        "indicate elevated risk, more than 80% high risk. At 1.0, liabilities equal "
        "assets (zero equity).",
        "Concern and distress: conventional. 1.0 (zero equity) is the definitional "
        "insolvency point.",
        None,
    ),
    "interest_coverage": (
        "Credit-analysis convention: coverage below about 1.5 times leaves little margin "
        "for meeting interest obligations.",
        "Credit-analysis convention: operating profit below about 1.5 times interest "
        "leaves little margin; below 1.0 it does not cover interest at all.",
        "Concern and distress: conventional. 1.0 (break-even) is definitional.",
        None,
    ),
    "asset_turnover": (
        "General efficiency guidance on revenue generated per unit of assets employed.",
        "Project-defined default. Asset turnover is strongly industry-dependent; Altman "
        "removed it from the Z'' model to reduce industry effects (Altman, 2002). Should "
        "be set per sector.",
        "Concern and distress: project-defined; strongly industry-dependent.",
        "Annualised revenue divided by total assets.",
    ),
    "days_sales_outstanding": (
        "Common commercial credit terms are 30 to 60 days; collection beyond 90 days "
        "indicates a material collection problem.",
        "Common commercial credit terms are 30 to 60 days; collection beyond 90 days "
        "indicates a material collection problem. Credit terms vary by industry and "
        "country.",
        "Concern and distress: conventional.",
        "Receivables expressed as days of the period's revenue.",
    ),
}


def upgrade() -> None:
    op.add_column(
        "financial_records", sa.Column("retained_earnings", sa.Numeric(18, 2), nullable=True)
    )

    op.add_column("threshold_configurations", sa.Column("floor_value", sa.Float(), nullable=True))
    op.add_column("threshold_configurations", sa.Column("target_value", sa.Float(), nullable=True))
    op.add_column("threshold_configurations", sa.Column("basis", sa.String(500), nullable=True))

    # Defaults that reproduce the methodology-1.0 scores exactly.
    op.execute(
        """
        UPDATE threshold_configurations SET
          target_value = CASE WHEN direction = 'higher_is_better'
            THEN concern_threshold + ABS(concern_threshold - distress_threshold)
            ELSE concern_threshold - ABS(concern_threshold - distress_threshold) END,
          floor_value = CASE WHEN direction = 'higher_is_better'
            THEN distress_threshold - 2 * ABS(concern_threshold - distress_threshold)
            ELSE distress_threshold + 2 * ABS(concern_threshold - distress_threshold) END
        """
    )
    with op.batch_alter_table("threshold_configurations") as batch:
        batch.alter_column("floor_value", existing_type=sa.Float(), nullable=False)
        batch.alter_column("target_value", existing_type=sa.Float(), nullable=False)

    table = sa.table(
        "threshold_configurations",
        sa.column("indicator_code", sa.String),
        sa.column("source_reference", sa.String),
        sa.column("basis", sa.String),
        sa.column("description", sa.String),
    )
    for code, (old_source, new_source, basis, new_description) in _TEXTS.items():
        op.execute(
            table.update()
            .where(table.c.indicator_code == code)
            .values(basis=basis + _REFERENCE_BASIS)
        )
        op.execute(
            table.update()
            .where(table.c.indicator_code == code)
            .where(table.c.source_reference == old_source)
            .values(source_reference=new_source)
        )
        if new_description is not None:
            op.execute(
                table.update()
                .where(table.c.indicator_code == code)
                .values(description=new_description)
            )


def downgrade() -> None:
    table = sa.table(
        "threshold_configurations",
        sa.column("indicator_code", sa.String),
        sa.column("source_reference", sa.String),
    )
    for code, (old_source, new_source, _basis, _description) in _TEXTS.items():
        op.execute(
            table.update()
            .where(table.c.indicator_code == code)
            .where(table.c.source_reference == new_source)
            .values(source_reference=old_source)
        )
    with op.batch_alter_table("threshold_configurations") as batch:
        batch.drop_column("basis")
        batch.drop_column("target_value")
        batch.drop_column("floor_value")
    op.drop_column("financial_records", "retained_earnings")
