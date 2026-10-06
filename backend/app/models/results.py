"""Persisted assessment results.

Indicator results and health scores are stored so that historical assessments
are preserved exactly as they were produced, rather than being recomputed from
possibly revised inputs.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IndicatorResult(Base):
    """One calculated indicator for one financial record."""

    __tablename__ = "indicator_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    financial_record_id: Mapped[int] = mapped_column(
        ForeignKey("financial_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    indicator_code: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Null when the indicator is not applicable for this record.
    value: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class FinancialHealthScore(Base):
    """Category and overall scores for one financial record."""

    __tablename__ = "financial_health_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    financial_record_id: Mapped[int] = mapped_column(
        ForeignKey("financial_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    liquidity_score: Mapped[float | None] = mapped_column(Float)
    profitability_score: Mapped[float | None] = mapped_column(Float)
    solvency_score: Mapped[float | None] = mapped_column(Float)
    efficiency_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
