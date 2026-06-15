"""Publish new estimates (the only write path). Gated by a service token."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from kpi_perf_summary_core import schemas

from app.deps import ServiceDep, require_publish_token

router = APIRouter()


@router.post(
    "/companies/{ticker}/kpis/{kpi_id}/estimates",
    response_model=schemas.PublishEstimateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_publish_token)],
)
async def publish_estimate(
    ticker: str,
    kpi_id: str,
    payload: schemas.PublishEstimateIn,
    svc: ServiceDep,
):
    """Append a new estimate for a (ticker, KPI) pair.

    Never updates in place — every publish is a new immutable row, so the full
    revision history is auditable. ``kpi_id`` accepts a numeric id or KPI name.
    """
    return await svc.publish_estimate(ticker, kpi_id, payload)
