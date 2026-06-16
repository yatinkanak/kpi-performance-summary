"""Data-access layer: SQL only, no business logic.

Reads go through the ``current_estimates`` view (latest publish per logical key);
writes append to the ``estimates`` table.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kpi_perf_summary_core.db.models import Company, Estimate, Favorite, Kpi, Sector


class NotFoundError(Exception):
    """Raised when a ticker or KPI cannot be resolved."""


class Repository:
    def __init__(self, session: AsyncSession):
        self.s = session

    # ----- dimensions ----------------------------------------------------
    async def list_sectors(self) -> list[dict]:
        rows = (
            await self.s.execute(
                select(Sector.id, Sector.name, func.count(Company.id))
                .join(Company, Company.sector_id == Sector.id, isouter=True)
                .group_by(Sector.id, Sector.name)
                .order_by(Sector.name)
            )
        ).all()
        return [{"id": r[0], "name": r[1], "company_count": r[2]} for r in rows]

    async def list_kpis(self) -> list[Kpi]:
        return list((await self.s.execute(select(Kpi).order_by(Kpi.name))).scalars())

    async def search_companies(
        self, search: str | None, sector: str | None, limit: int, offset: int
    ) -> list[dict]:
        q = (
            select(Company.ticker, Company.name, Sector.name)
            .join(Sector, Sector.id == Company.sector_id)
            .order_by(Company.name)
            .limit(limit)
            .offset(offset)
        )
        if search:
            like = f"%{search.lower()}%"
            q = q.where(func.lower(Company.name).like(like) | func.lower(Company.ticker).like(like))
        if sector:
            q = q.where(func.lower(Sector.name) == sector.lower())
        rows = (await self.s.execute(q)).all()
        return [{"ticker": r[0], "name": r[1], "sector": r[2]} for r in rows]

    async def get_company(self, ticker: str) -> dict:
        row = (
            await self.s.execute(
                select(Company.id, Company.ticker, Company.name, Sector.name)
                .join(Sector, Sector.id == Company.sector_id)
                .where(func.lower(Company.ticker) == ticker.lower())
            )
        ).first()
        if not row:
            raise NotFoundError(f"Company '{ticker}' not found")
        return {"id": row[0], "ticker": row[1], "name": row[2], "sector": row[3]}

    async def get_kpi_by_name(self, name: str) -> Kpi | None:
        return (
            await self.s.execute(select(Kpi).where(func.lower(Kpi.name) == name.lower()))
        ).scalar_one_or_none()

    async def get_kpi(self, kpi_id: int) -> Kpi | None:
        return await self.s.get(Kpi, kpi_id)

    async def kpis_for_company(self, company_id: int) -> list[Kpi]:
        """Distinct KPIs that actually have estimates for this company."""
        return list(
            (
                await self.s.execute(
                    select(Kpi)
                    .join(Estimate, Estimate.kpi_id == Kpi.id)
                    .where(Estimate.company_id == company_id)
                    .distinct()
                    .order_by(Kpi.name)
                )
            ).scalars()
        )

    async def company_last_updated(self, company_id: int):
        return (
            await self.s.execute(
                select(func.max(Estimate.published_at)).where(Estimate.company_id == company_id)
            )
        ).scalar_one_or_none()

    # ----- facts (read via current_estimates view) -----------------------
    async def series(
        self,
        ticker: str,
        kpi_id: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict]:
        sql = text(
            """
            SELECT ce.fiscal_period, ce.period_start, ce.period_end,
                   ce.est_type, ce.value, ce.as_of, ce.published_at
            FROM current_estimates ce
            JOIN companies c ON c.id = ce.company_id
            WHERE LOWER(c.ticker) = LOWER(:ticker)
              AND ce.kpi_id = :kpi_id
              AND (CAST(:date_from AS date) IS NULL OR ce.period_end >= CAST(:date_from AS date))
              AND (CAST(:date_to   AS date) IS NULL OR ce.period_start <= CAST(:date_to AS date))
            ORDER BY ce.period_start, ce.as_of NULLS FIRST
            """
        )
        rows = (
            await self.s.execute(
                sql,
                {
                    "ticker": ticker,
                    "kpi_id": kpi_id,
                    "date_from": date_from,
                    "date_to": date_to,
                },
            )
        ).mappings()
        return [dict(r) for r in rows]

    # ----- favorites -----------------------------------------------------
    async def list_favorites(self) -> list[dict]:
        rows = (
            await self.s.execute(
                select(
                    Company.ticker,
                    Company.name,
                    Sector.name,
                    Kpi.id,
                    Kpi.name,
                    Kpi.unit,
                    Favorite.created_at,
                )
                .join(Company, Company.id == Favorite.company_id)
                .join(Sector, Sector.id == Company.sector_id)
                .join(Kpi, Kpi.id == Favorite.kpi_id)
                .order_by(Favorite.created_at.desc())
            )
        ).all()
        return [
            {
                "ticker": r[0],
                "company_name": r[1],
                "sector": r[2],
                "kpi_id": r[3],
                "kpi": r[4],
                "unit": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    async def add_favorite(self, company_id: int, kpi_id: int) -> Favorite:
        """Insert the bookmark, or return the existing one (idempotent)."""
        existing = (
            await self.s.execute(
                select(Favorite).where(Favorite.company_id == company_id, Favorite.kpi_id == kpi_id)
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        fav = Favorite(company_id=company_id, kpi_id=kpi_id)
        self.s.add(fav)
        await self.s.flush()
        await self.s.refresh(fav)  # populate server-side created_at
        return fav

    async def remove_favorite(self, company_id: int, kpi_id: int) -> None:
        await self.s.execute(
            delete(Favorite).where(Favorite.company_id == company_id, Favorite.kpi_id == kpi_id)
        )

    # ----- write (append-only) -------------------------------------------
    async def insert_estimate(self, company_id: int, kpi_id: int, payload: dict) -> Estimate:
        est = Estimate(
            company_id=company_id,
            kpi_id=kpi_id,
            source="api",
            **payload,
        )
        self.s.add(est)
        await self.s.flush()
        return est
