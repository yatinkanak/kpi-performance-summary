"""Discovery endpoints: unified search and sector listing."""

from __future__ import annotations

from fastapi import APIRouter, Query
from kpi_perf_summary_core import schemas

from app.deps import ServiceDep

router = APIRouter()


@router.get("/sectors", response_model=list[schemas.SectorOut])
async def list_sectors(svc: ServiceDep):
    return await svc.list_sectors()


@router.get("/search", response_model=schemas.SearchResultOut)
async def search(svc: ServiceDep, q: str = Query(min_length=1, description="Free text")):
    return await svc.search(q)
