"""Threshold configuration route.

Read-only in FYP1. The frontend uses it to show where each threshold came
from, which is why the source reference is stored with the value.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.threshold import ThresholdConfiguration
from app.models.user import User

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


@router.get("", summary="List the configured indicator thresholds")
def list_thresholds(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
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
            "floor_value": row.floor_value,
            "target_value": row.target_value,
            "source_reference": row.source_reference,
            "basis": row.basis,
            "description": row.description,
        }
        for row in rows
    ]
