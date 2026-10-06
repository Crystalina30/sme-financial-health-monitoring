"""Service health endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service and database health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Report whether the API is up and the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:  # noqa: BLE001 - reported, never raised to the caller
        database_status = "unavailable"

    return {
        "status": "ok" if database_status == "connected" else "degraded",
        "application": settings.app_name,
        "environment": settings.environment,
        "database": database_status,
    }
