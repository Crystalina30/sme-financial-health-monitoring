"""Threshold configuration route.

Read-only in FYP1. The frontend uses it to show where each threshold came
from, which is why the source reference is stored with the value.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.threshold import ThresholdConfiguration
from app.models.user import User

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


@router.get("", summary="List the configured indicator thresholds")
def list_thresholds(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.execute(
        select(ThresholdConfiguration)
        .where(ThresholdConfiguration.is_active.is_(True))
        .order_by(ThresholdConfiguration.category, ThresholdConfiguration.indicator_code)
    ).scalars()

    return [
        {
            "indicator_code": row.indicator_code,
            "category": row.category,
            "direction": row.direction,
            "concern_threshold": row.concern_threshold,
            "distress_threshold": row.distress_threshold,
            "source_reference": row.source_reference,
            "description": row.description,
        }
        for row in rows
    ]
