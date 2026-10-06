"""Loading and seeding of threshold configuration.

Threshold values are held in the database, not in the application code, so
they can be revised without a code change and so the documented source of each
value travels with it to the user interface.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import INDICATOR_CATEGORIES, IndicatorCode, ThresholdDirection
from app.models.threshold import ThresholdConfiguration
from app.services.scoring_service import ThresholdSetting

#: Default threshold values applied when the database is first seeded.
#:
#: Each value is a conventional threshold drawn from published financial
#: distress research and standard financial-analysis guidance. They are
#: deliberately *not* derived from sector benchmark distributions or
#: percentiles; the source of each is stored and displayed so that a reader
#: can see where it came from and substitute a different documented value.
DEFAULT_THRESHOLDS: list[dict] = [
    {
        "indicator_code": IndicatorCode.CURRENT_RATIO,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.5,
        "distress_threshold": 1.0,
        "source_reference": "Conventional working-capital guidance: a current ratio below 1.0 means current liabilities exceed current assets.",
        "description": "Current assets divided by current liabilities.",
    },
    {
        "indicator_code": IndicatorCode.QUICK_RATIO,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.0,
        "distress_threshold": 0.7,
        "source_reference": "Conventional liquidity guidance: a quick ratio below 1.0 indicates reliance on inventory conversion to meet short-term obligations.",
        "description": "Current assets excluding inventory, divided by current liabilities.",
    },
    {
        "indicator_code": IndicatorCode.GROSS_PROFIT_MARGIN,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 20.0,
        "distress_threshold": 10.0,
        "source_reference": "General small-business profitability guidance on the margin required to cover operating costs.",
        "description": "Gross profit as a percentage of revenue.",
    },
    {
        "indicator_code": IndicatorCode.NET_PROFIT_MARGIN,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 5.0,
        "distress_threshold": 0.0,
        "source_reference": "Sustained losses are a recognised symptom of financial distress; a margin at or below zero marks the distress point.",
        "description": "Net profit as a percentage of revenue.",
    },
    {
        "indicator_code": IndicatorCode.RETURN_ON_ASSETS,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 5.0,
        "distress_threshold": 0.0,
        "source_reference": "Return on assets is a standard component of financial distress models; a negative return marks the distress point.",
        "description": "Net profit as a percentage of total assets.",
    },
    {
        "indicator_code": IndicatorCode.DEBT_TO_EQUITY,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 1.5,
        "distress_threshold": 2.5,
        "source_reference": "Conventional leverage guidance: liabilities exceeding equity by more than about 1.5 times indicates elevated gearing.",
        "description": "Total liabilities divided by total equity.",
    },
    {
        "indicator_code": IndicatorCode.DEBT_RATIO,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 0.6,
        "distress_threshold": 0.8,
        "source_reference": "Conventional solvency guidance: liabilities funding more than about 60 per cent of assets indicates elevated balance-sheet risk.",
        "description": "Total liabilities divided by total assets.",
    },
    {
        "indicator_code": IndicatorCode.INTEREST_COVERAGE,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 3.0,
        "distress_threshold": 1.5,
        "source_reference": "Credit-analysis convention: coverage below about 1.5 times leaves little margin for meeting interest obligations.",
        "description": "Operating profit divided by interest expense.",
    },
    {
        "indicator_code": IndicatorCode.ASSET_TURNOVER,
        "direction": ThresholdDirection.HIGHER_IS_BETTER,
        "concern_threshold": 1.0,
        "distress_threshold": 0.5,
        "source_reference": "General efficiency guidance on revenue generated per unit of assets employed.",
        "description": "Revenue divided by total assets.",
    },
    {
        "indicator_code": IndicatorCode.DAYS_SALES_OUTSTANDING,
        "direction": ThresholdDirection.LOWER_IS_BETTER,
        "concern_threshold": 60.0,
        "distress_threshold": 90.0,
        "source_reference": "Common commercial credit terms are 30 to 60 days; collection beyond 90 days indicates a material collection problem.",
        "description": "Average number of days taken to collect receivables.",
    },
]


def seed_default_thresholds(db: Session) -> int:
    """Insert any missing default thresholds. Existing rows are left alone.

    Returns the number of rows inserted, so the caller can report whether the
    seed had any effect.
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
        db.add(
            ThresholdConfiguration(
                indicator_code=code.value,
                category=INDICATOR_CATEGORIES[code].value,
                direction=entry["direction"].value,
                concern_threshold=entry["concern_threshold"],
                distress_threshold=entry["distress_threshold"],
                source_reference=entry["source_reference"],
                description=entry["description"],
                is_active=True,
            )
        )
        inserted += 1
    db.commit()
    return inserted


def load_threshold_settings(db: Session) -> dict[IndicatorCode, ThresholdSetting]:
    """Load active thresholds in the form the scoring service expects."""
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
        )
    return settings
