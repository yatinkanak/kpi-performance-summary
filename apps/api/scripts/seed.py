"""Load the sample KPI CSV into Postgres.

Idempotent: if the estimates table already has rows, seeding is skipped so a
container restart does not append duplicate facts.
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime
from pathlib import Path

from kpi_perf_summary_core.db.models import Company, Estimate, EstimateType, Kpi, Sector
from kpi_perf_summary_core.db.session import SessionFactory
from sqlalchemy import func, select

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "kpi_sample_2000.csv"


def _date(value: str):
    value = (value or "").strip()
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


async def main() -> None:
    async with SessionFactory() as session:
        existing = await session.scalar(select(func.count()).select_from(Estimate))
        if existing:
            print(f"seed: estimates already populated ({existing} rows); skipping")
            return

        sectors: dict[str, Sector] = {}
        companies: dict[str, Company] = {}
        kpis: dict[str, Kpi] = {}
        estimates: list[Estimate] = []

        with CSV_PATH.open(newline="") as f:
            for row in csv.DictReader(f):
                sector_name = row["sector"].strip()
                if sector_name not in sectors:
                    sector = Sector(name=sector_name)
                    session.add(sector)
                    await session.flush()  # assign sector.id for the FK below
                    sectors[sector_name] = sector

                ticker = row["ticker"].strip()
                if ticker not in companies:
                    companies[ticker] = Company(
                        ticker=ticker,
                        name=row["company_name"].strip(),
                        sector_id=sectors[sector_name].id,
                    )
                    session.add(companies[ticker])

                kpi_name = row["kpi"].strip()
                if kpi_name not in kpis:
                    kpis[kpi_name] = Kpi(name=kpi_name, unit=row["unit"].strip())
                    session.add(kpis[kpi_name])

                estimates.append(
                    Estimate(
                        company=companies[ticker],
                        kpi=kpis[kpi_name],
                        period_start=_date(row["period_start"]),
                        period_end=_date(row["period_end"]),
                        fiscal_period=row["period"].strip(),
                        est_type=EstimateType(row["estimate_type"].strip()),
                        value=float(row["value"]),
                        as_of=_date(row["as_of"]),
                        source="seed",
                    )
                )

        # Estimates link to their company/kpi via ORM relationships (unit-of-work
        # resolves the FKs on flush); bulk add them after the parents exist.
        session.add_all(estimates)
        await session.commit()
        print(
            f"seed: {len(sectors)} sectors, {len(companies)} companies, "
            f"{len(kpis)} KPIs, {len(estimates)} estimates loaded"
        )


if __name__ == "__main__":
    asyncio.run(main())
