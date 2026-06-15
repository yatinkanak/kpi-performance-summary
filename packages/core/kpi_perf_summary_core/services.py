"""Business logic shared by the FastAPI and FastMCP adapters.

This is the single source of truth for series assembly, summary math (QoQ/YoY),
and the publish path. Both adapters call these functions; neither re-implements them.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from kpi_perf_summary_core import schemas
from kpi_perf_summary_core.repositories import NotFoundError, Repository


def _pct_change(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


class KpiService:
    def __init__(self, session: AsyncSession):
        self.repo = Repository(session)
        self.session = session

    # ----- catalog / discovery ------------------------------------------
    async def list_sectors(self) -> list[schemas.SectorOut]:
        return [schemas.SectorOut(**r) for r in await self.repo.list_sectors()]

    async def list_kpis(self) -> list[schemas.KpiOut]:
        return [
            schemas.KpiOut(id=k.id, name=k.name, unit=k.unit, description=k.description)
            for k in await self.repo.list_kpis()
        ]

    async def search_companies(
        self,
        search: str | None = None,
        sector: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[schemas.CompanyOut]:
        rows = await self.repo.search_companies(search, sector, limit, offset)
        return [schemas.CompanyOut(**r) for r in rows]

    async def get_company_detail(self, ticker: str) -> schemas.CompanyDetailOut:
        c = await self.repo.get_company(ticker)
        kpis = await self.repo.kpis_for_company(c["id"])
        last = await self.repo.company_last_updated(c["id"])
        return schemas.CompanyDetailOut(
            ticker=c["ticker"],
            name=c["name"],
            sector=c["sector"],
            kpis=[
                schemas.KpiOut(id=k.id, name=k.name, unit=k.unit, description=k.description)
                for k in kpis
            ],
            last_updated=last,
        )

    async def search(self, q: str) -> schemas.SearchResultOut:
        ql = q.lower()
        sectors = [
            schemas.SectorOut(**s)
            for s in await self.repo.list_sectors()
            if ql in s["name"].lower()
        ]
        companies = await self.search_companies(search=q, limit=10)
        kpis = [k for k in await self.list_kpis() if ql in k.name.lower()]
        return schemas.SearchResultOut(sectors=sectors, companies=companies, kpis=kpis)

    # ----- series --------------------------------------------------------
    async def _resolve_kpi(self, kpi_ref: str | int):
        """Accept a KPI id or a KPI name (the MCP-friendly path)."""
        if isinstance(kpi_ref, int) or (isinstance(kpi_ref, str) and kpi_ref.isdigit()):
            kpi = await self.repo.get_kpi(int(kpi_ref))
        else:
            kpi = await self.repo.get_kpi_by_name(str(kpi_ref))
        if not kpi:
            raise NotFoundError(f"KPI '{kpi_ref}' not found")
        return kpi

    async def get_series(
        self,
        ticker: str,
        kpi_ref: str | int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> schemas.KpiSeriesOut:
        company = await self.repo.get_company(ticker)
        kpi = await self._resolve_kpi(kpi_ref)
        rows = await self.repo.series(ticker, kpi.id, date_from, date_to)

        historical, qtd = [], []
        last_updated = None
        for r in rows:
            pt = schemas.SeriesPoint(
                fiscal_period=r["fiscal_period"],
                period_start=r["period_start"],
                period_end=r["period_end"],
                est_type=r["est_type"],
                value=float(r["value"]),
                as_of=r["as_of"],
            )
            (qtd if r["est_type"] == "qtd" else historical).append(pt)
            if last_updated is None or r["published_at"] > last_updated:
                last_updated = r["published_at"]

        return schemas.KpiSeriesOut(
            ticker=company["ticker"],
            company_name=company["name"],
            kpi=kpi.name,
            unit=kpi.unit,
            historical=historical,
            qtd=qtd,
            last_updated=last_updated,
            qtd_as_of=qtd[-1].as_of if qtd else None,
        )

    # ----- summary (the at-a-glance dashboard) ---------------------------
    async def get_company_summary(self, ticker: str) -> schemas.CompanySummaryOut:
        company = await self.repo.get_company(ticker)
        kpis = await self.repo.kpis_for_company(company["id"])
        last_updated = await self.repo.company_last_updated(company["id"])

        summaries: list[schemas.KpiSummary] = []
        for kpi in kpis:
            rows = await self.repo.series(ticker, kpi.id, None, None)
            hist = [r for r in rows if r["est_type"] == "historical"]
            qtd = [r for r in rows if r["est_type"] == "qtd"]

            latest = hist[-1] if hist else None
            prev_q = hist[-2] if len(hist) >= 2 else None
            prev_y = hist[-5] if len(hist) >= 5 else None  # 4 quarters back
            latest_val = float(latest["value"]) if latest else None

            summaries.append(
                schemas.KpiSummary(
                    kpi=kpi.name,
                    unit=kpi.unit,
                    latest_period=latest["fiscal_period"] if latest else None,
                    latest_value=latest_val,
                    qoq_pct=_pct_change(latest_val, float(prev_q["value"]) if prev_q else None),
                    yoy_pct=_pct_change(latest_val, float(prev_y["value"]) if prev_y else None),
                    qtd_value=float(qtd[-1]["value"]) if qtd else None,
                    qtd_as_of=qtd[-1]["as_of"] if qtd else None,
                )
            )

        return schemas.CompanySummaryOut(
            ticker=company["ticker"],
            company_name=company["name"],
            sector=company["sector"],
            last_updated=last_updated,
            kpis=summaries,
        )

    # ----- publish (append-only write) -----------------------------------
    async def publish_estimate(
        self, ticker: str, kpi_ref: str | int, payload: schemas.PublishEstimateIn
    ) -> schemas.PublishEstimateOut:
        company = await self.repo.get_company(ticker)
        kpi = await self._resolve_kpi(kpi_ref)

        if payload.est_type == "qtd" and payload.as_of is None:
            raise ValueError("QTD estimates require an 'as_of' snapshot date")
        if payload.est_type == "historical" and payload.as_of is not None:
            raise ValueError("Historical estimates must not include 'as_of'")

        est = await self.repo.insert_estimate(
            company["id"],
            kpi.id,
            {
                "period_start": payload.period_start,
                "period_end": payload.period_end,
                "fiscal_period": payload.fiscal_period,
                "est_type": payload.est_type,
                "value": payload.value,
                "as_of": payload.as_of,
            },
        )
        await self.session.commit()
        return schemas.PublishEstimateOut(
            id=est.id,
            ticker=company["ticker"],
            kpi=kpi.name,
            fiscal_period=est.fiscal_period,
            est_type=payload.est_type,
            value=float(est.value),
            as_of=est.as_of,
            published_at=est.published_at,
        )
