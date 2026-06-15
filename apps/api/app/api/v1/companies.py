"""Company browse, detail, summary, and KPI series endpoints."""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from kpi_perf_summary_core import schemas

from app.deps import ServiceDep

router = APIRouter()


@router.get("/companies", response_model=list[schemas.CompanyOut])
async def list_companies(
    svc: ServiceDep,
    search: Optional[str] = Query(None, description="Match ticker or name"),
    sector: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    return await svc.search_companies(search, sector, limit, offset)


@router.get("/companies/{ticker}", response_model=schemas.CompanyDetailOut)
async def get_company(ticker: str, svc: ServiceDep):
    return await svc.get_company_detail(ticker)


@router.get("/companies/{ticker}/summary", response_model=schemas.CompanySummaryOut)
async def get_summary(ticker: str, svc: ServiceDep):
    """At-a-glance dashboard: latest value, QoQ %, YoY %, and latest QTD per KPI."""
    return await svc.get_company_summary(ticker)


@router.get(
    "/companies/{ticker}/kpis/{kpi_id}/series", response_model=schemas.KpiSeriesOut
)
async def get_series(
    ticker: str,
    kpi_id: str,
    svc: ServiceDep,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
):
    """Historical series + QTD trajectory. ``kpi_id`` accepts a numeric id or KPI name."""
    return await svc.get_series(ticker, kpi_id, date_from, date_to)


@router.get("/companies/{ticker}/kpis/{kpi_id}/series/export")
async def export_series(
    ticker: str,
    kpi_id: str,
    svc: ServiceDep,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
):
    """Export the current series view as CSV (the frontend 'Export' action)."""
    s = await svc.get_series(ticker, kpi_id, date_from, date_to)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fiscal_period", "period_start", "period_end", "est_type", "value", "unit", "as_of"])
    for pt in s.historical + s.qtd:
        w.writerow(
            [pt.fiscal_period, pt.period_start, pt.period_end, pt.est_type, pt.value, s.unit, pt.as_of or ""]
        )
    buf.seek(0)
    fname = f"{s.ticker}_{s.kpi}.csv".replace(" ", "_").replace("/", "-")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
