"""KPI catalog."""
from __future__ import annotations

from fastapi import APIRouter

from kpi_perf_summary_core import schemas

from app.deps import ServiceDep

router = APIRouter()


@router.get("/kpis", response_model=list[schemas.KpiOut])
async def list_kpis(svc: ServiceDep):
    return await svc.list_kpis()
