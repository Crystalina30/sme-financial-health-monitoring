"""FastAPI application entry point."""

import logging
import math

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    companies,
    dashboard,
    financial_records,
    health,
    indicators,
    organisation,
    thresholds,
    trial_balance,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DESCRIPTION = """
Financial health monitoring for small and medium-sized enterprises.

The API validates submitted financial statement data, calculates ten fixed
financial indicators, scores each against documented concern and distress
thresholds, aggregates those into category scores and an overall financial
health score, and identifies the indicators requiring attention.

This is the FYP1 system. Distress simulation, driver impact analysis, reverse
stress analysis and the language-model explanation layer are planned for FYP2
and are **not** implemented here.
"""

app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="1.0.0",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _json_safe(value):
    """Infinity and NaN cannot be written as JSON; report them as text."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """The standard 422 response, safe for inputs such as Infinity or NaN.

    FastAPI echoes each invalid input back; a non-finite number cannot be
    serialised as JSON, which would otherwise turn a clear 422 into a 500.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _json_safe(jsonable_encoder(exc.errors(), custom_encoder={
            float: lambda v: v if math.isfinite(v) else str(v)}))},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic error, logging the detail rather than exposing it.

    Stack traces and internal messages are never sent to the client.
    """
    logger.exception("Unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred."},
    )


for router in (
    health.router,
    auth.router,
    organisation.router,
    companies.router,
    financial_records.router,
    indicators.router,
    dashboard.router,
    thresholds.router,
    trial_balance.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "application": settings.app_name,
        "stage": "FYP1",
        "documentation": f"{settings.api_prefix}/docs",
    }
