"""Loading and seeding of threshold configuration.

Threshold values are held in the database, not in the application code, so
they can be revised without a code change and so the documented source of each
value travels with it to the user interface.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import INDICATOR_CATEGORIES, IndicatorCode, ThresholdDirection
from app.models.threshold import ThresholdConfiguration
from app.services.scoring_service import ThresholdSetting, default_reference_points

#: Explains every default floor and target; stored as part of each basis.
_DEFAULT_REFERENCE_BASIS = (
    "Floor and target: project-defined defaults (target one span beyond the concern "
    "threshold, floor two spans beyond the distress threshold)."
)

#: Default threshold values applied when the database is first seeded.
#:
#: No published source establishes universal threshold values for these
#: ratios: appropriate levels vary by industry (Platt & Platt, 1991) and the
#: link between a ratio and failure can be non-linear (Li, 2024). Each value is
#: therefore labelled with its basis:
#:
#: * definitional - a mathematical break-even point, such as a margin of zero;
#: * conventional - a widely used rule of thumb in financial analysis;
#: * project-defined - chosen for this project, to be validated.
#:
#: Every value is a configurable default, and its source is stored and
#: displayed so a reader can see where it came from and substitute another
#: documented value. Floor and target are derived from the concern and
#: distress thresholds when seeding (see scoring_service.py).
DEFAULT_THRESHOLDS: list[dict] = [
    {
        "indicator_code": IndicatorCode.CURRENT_RATIO,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.5,
        "distress_threshold": 1.0,
        "source_reference": "At 1.0, current liabilities equal current assets. 1.5 is a "
        "conventional working-capital cushion. No universal threshold exists; the "
        "ratio's link to failure is strongest at low levels (Li, 2024).",
        "basis": "Distress: definitional (current assets equal current liabilities). "
        "Concern: conventional.",
        "description": "Current assets divided by current liabilities.",
    },
    {
        "indicator_code": IndicatorCode.QUICK_RATIO,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.0,
        "distress_threshold": 0.7,
        "source_reference": "Conventional 'acid test': below 1.0, short-term obligations "
        "cannot be met without selling inventory. The 0.7 distress level is a "
        "project-defined default.",
        "basis": "Concern: conventional (acid test of 1.0). Distress: project-defined.",
        "description": "Current assets excluding inventory, divided by current liabilities.",
    },
    {
        "indicator_code": IndicatorCode.GROSS_PROFIT_MARGIN,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 20.0,
        "distress_threshold": 10.0,
        "source_reference": "Project-defined default. Typical gross margins differ widely "
        "between industries (Platt & Platt, 1991, on industry-relative ratios), so these "
        "values should be set per sector where possible.",
        "basis": "Concern and distress: project-defined; strongly industry-dependent.",
        "description": "Gross profit as a percentage of revenue.",
    },
    {
        "indicator_code": IndicatorCode.NET_PROFIT_MARGIN,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 5.0,
        "distress_threshold": 0.0,
        "source_reference": "A margin at or below zero means the period made a loss; "
        "profitability is a core dimension of distress research (Beaver, 1966; Altman, "
        "1968). 5% is a conventional concern level.",
        "basis": "Distress: definitional (break-even). Concern: conventional.",
        "description": "Net profit as a percentage of revenue.",
    },
    {
        "indicator_code": IndicatorCode.RETURN_ON_ASSETS,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 5.0,
        "distress_threshold": 0.0,
        "source_reference": "A return at or below zero means the assets produced a loss; "
        "earnings relative to assets is a standard distress-model component (Beaver, "
        "1966; Altman, 1968). 5% is a conventional concern level.",
        "basis": "Distress: definitional (break-even). Concern: conventional.",
        "description": "Net profit as a percentage of total assets.",
    },
    {
        "indicator_code": IndicatorCode.DEBT_TO_EQUITY,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 1.5,
        "distress_threshold": 2.5,
        "source_reference": "Conventional leverage guidance: liabilities above about 1.5 "
        "times equity indicate elevated gearing, above 2.5 times high gearing. Zero or "
        "negative equity is scored as the worst case. Suitable gearing varies by industry.",
        "basis": "Concern and distress: conventional.",
        "description": "Total liabilities divided by total equity.",
    },
    {
        "indicator_code": IndicatorCode.DEBT_RATIO,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 0.6,
        "distress_threshold": 0.8,
        "source_reference": "Conventional solvency guidance: liabilities funding more than "
        "about 60% of assets indicate elevated risk, more than 80% high risk. At 1.0, "
        "liabilities equal assets (zero equity).",
        "basis": "Concern and distress: conventional. 1.0 (zero equity) is the "
        "definitional insolvency point.",
        "description": "Total liabilities divided by total assets.",
    },
    {
        "indicator_code": IndicatorCode.INTEREST_COVERAGE,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 3.0,
        "distress_threshold": 1.5,
        "source_reference": "Credit-analysis convention: operating profit below about 1.5 "
        "times interest leaves little margin; below 1.0 it does not cover interest at all.",
        "basis": "Concern and distress: conventional. 1.0 (break-even) is definitional.",
        "description": "Operating profit divided by interest expense.",
    },
    {
        "indicator_code": IndicatorCode.ASSET_TURNOVER,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.0,
        "distress_threshold": 0.5,
        "source_reference": "Project-defined default. Asset turnover is strongly "
        "industry-dependent; Altman removed it from the Z'' model to reduce industry "
        "effects (Altman, 2002). Should be set per sector.",
        "basis": "Concern and distress: project-defined; strongly industry-dependent.",
        "description": "Annualised revenue divided by total assets.",
    },
    {
        "indicator_code": IndicatorCode.DAYS_SALES_OUTSTANDING,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 60.0,
        "distress_threshold": 90.0,
        "source_reference": "Common commercial credit terms are 30 to 60 days; collection "
        "beyond 90 days indicates a material collection problem. Credit terms vary by "
        "industry and country.",
        "basis": "Concern and distress: conventional.",
        "description": "Receivables expressed as days of the period's revenue.",
    },
]


def _full_basis(entry: dict) -> str:
    return f"{entry['basis']} {_DEFAULT_REFERENCE_BASIS}"


def seed_default_thresholds(db: Session) -> int:
    """Insert any missing default thresholds. Existing rows are left alone.

    All four reference points are stored explicitly; floor and target take
    their default values. Returns the number of rows inserted, so the caller
    can report whether the seed had any effect.
    """
    existing = {
        code
        for (code,) in db.execute(select(ThresholdConfiguration.indicator_code)).all()
    }
    inserted = 0
    for entry in DEFAULT_THRESHOLDS:
        code: IndicatorCode = entry["indicator_code"]
        if code.value in existing:
            continue
        floor, target = default_reference_points(
            entry["direction"], entry["concern_threshold"], entry["distress_threshold"]
        )
        db.add(
            ThresholdConfiguration(
                indicator_code=code.value,
                category=INDICATOR_CATEGORIES[code].value,
                direction=entry["direction"].value,
                concern_threshold=entry["concern_threshold"],
                distress_threshold=entry["distress_threshold"],
                floor_value=floor,
                target_value=target,
                source_reference=entry["source_reference"],
                basis=_full_basis(entry),
                description=entry["description"],
                is_active=True,
            )
        )
        inserted += 1
    db.commit()
    return inserted


def load_threshold_settings(db: Session) -> dict[IndicatorCode, ThresholdSetting]:
    """Load active thresholds in the form the scoring service expects.

    The reference points are not validated here: an invalid configuration
    makes only its own indicator not applicable, with the reason shown,
    rather than breaking the whole assessment (see score_indicators()).
    """
    rows = db.execute(
        select(ThresholdConfiguration).where(ThresholdConfiguration.is_active.is_(True))
    ).scalars()

    settings: dict[IndicatorCode, ThresholdSetting] = {}
    for row in rows:
        try:
            code = IndicatorCode(row.indicator_code)
        except ValueError:
            # A threshold row for an indicator the application does not know
            # about is ignored rather than allowed to break the assessment.
            continue
        settings[code] = ThresholdSetting(
            indicator_code=code,
            direction=ThresholdDirection(row.direction),
            concern_threshold=row.concern_threshold,
            distress_threshold=row.distress_threshold,
            source_reference=row.source_reference,
            description=row.description,
            floor_value=row.floor_value,
            target_value=row.target_value,
            basis=row.basis,
        )
    return settings
