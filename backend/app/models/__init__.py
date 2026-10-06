"""ORM models.

Importing this package registers every model with the declarative base, which
Alembic relies on for autogeneration.
"""

from app.models.company import Company, ReportingPeriod
from app.models.financial_record import FinancialRecord
from app.models.results import FinancialHealthScore, IndicatorResult
from app.models.threshold import ThresholdConfiguration
from app.models.user import User

__all__ = [
    "Company",
    "FinancialHealthScore",
    "FinancialRecord",
    "IndicatorResult",
    "ReportingPeriod",
    "ThresholdConfiguration",
    "User",
]
