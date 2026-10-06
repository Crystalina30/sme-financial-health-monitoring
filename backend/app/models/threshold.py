"""Threshold configuration model.

Thresholds are stored in the database rather than hard-coded, so that they can
be updated without changing application code, and so that the documented
source of each threshold is preserved and can be shown to the user.
"""

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ThresholdConfiguration(Base):
    """Concern and distress thresholds for one indicator."""

    __tablename__ = "threshold_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    concern_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    distress_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # Reference for the threshold value, displayed alongside the indicator.
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
