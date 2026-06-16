"""Favorite (bookmark) a (company, KPI) pair. Global — no user auth in scope."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status
from kpi_perf_summary_core import schemas

from app.deps import ServiceDep

router = APIRouter()


@router.get("/favorites", response_model=list[schemas.FavoriteOut])
async def list_favorites(svc: ServiceDep):
    """All bookmarked KPIs, most recently added first."""
    return await svc.list_favorites()


@router.post(
    "/favorites",
    response_model=schemas.FavoriteOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_favorite(payload: schemas.FavoriteIn, svc: ServiceDep):
    """Bookmark a KPI for a company. Idempotent: re-adding returns the existing row."""
    return await svc.add_favorite(payload.ticker, payload.kpi)


@router.delete("/favorites", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    svc: ServiceDep,
    ticker: str = Query(...),
    kpi: str = Query(..., description="KPI id or name"),
):
    """Remove a bookmark. No-op if it wasn't favorited."""
    await svc.remove_favorite(ticker, kpi)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
