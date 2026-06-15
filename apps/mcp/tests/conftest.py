"""Fixtures for MCP tool tests.

The MCP tools open their own sessions via ``server.SessionFactory``. The ``mcp_server``
fixture points that factory at a Postgres test engine, seeds a deterministic dataset
(committed, since the tools read on separate connections), and yields the ``server`` module
so tests can call the tool coroutines directly. Data is truncated around each test.

Skips if Postgres is unreachable, so a bare ``pytest`` run stays green. Postgres (not SQLite)
on purpose — the schema relies on Postgres-only features (see the api test suite).
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest
import pytest_asyncio
from kpi_perf_summary_core.config import get_settings
from kpi_perf_summary_core.db.models import Base, Company, Estimate, EstimateType, Kpi, Sector
from kpi_perf_summary_core.db.views import CURRENT_ESTIMATES_VIEW
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_TRUNCATE = "TRUNCATE estimates, companies, kpis, sectors RESTART IDENTITY CASCADE"


async def _seed(session: AsyncSession) -> None:
    """ACME with five historical quarters (QoQ 25.0 / YoY 100.0) + two QTD snapshots,
    plus BETA with one historical value, for compare_companies."""
    tech = Sector(name="Tech")
    session.add(tech)
    await session.flush()
    acme = Company(ticker="ACME", name="Acme Corp", sector_id=tech.id)
    beta = Company(ticker="BETA", name="Beta Inc", sector_id=tech.id)
    kpi = Kpi(name="Total Revenue ($MM)", unit="$MM")
    session.add_all([acme, beta, kpi])
    await session.flush()

    for fp, ps, pe, val in [
        ("2024Q1", date(2024, 1, 1), date(2024, 3, 31), 100.0),
        ("2024Q2", date(2024, 4, 1), date(2024, 6, 30), 120.0),
        ("2024Q3", date(2024, 7, 1), date(2024, 9, 30), 140.0),
        ("2024Q4", date(2024, 10, 1), date(2024, 12, 31), 160.0),
        ("2025Q1", date(2025, 1, 1), date(2025, 3, 31), 200.0),
    ]:
        session.add(
            Estimate(
                company_id=acme.id,
                kpi_id=kpi.id,
                period_start=ps,
                period_end=pe,
                fiscal_period=fp,
                est_type=EstimateType.historical,
                value=val,
                as_of=None,
                source="seed",
            )
        )
    for as_of, val in [(date(2025, 4, 30), 50.0), (date(2025, 5, 15), 90.0)]:
        session.add(
            Estimate(
                company_id=acme.id,
                kpi_id=kpi.id,
                period_start=date(2025, 4, 1),
                period_end=date(2025, 6, 30),
                fiscal_period="2025Q2",
                est_type=EstimateType.qtd,
                value=val,
                as_of=as_of,
                source="seed",
            )
        )
    session.add(
        Estimate(
            company_id=beta.id,
            kpi_id=kpi.id,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            fiscal_period="2025Q1",
            est_type=EstimateType.historical,
            value=300.0,
            as_of=None,
            source="seed",
        )
    )
    await session.flush()


@pytest_asyncio.fixture
async def mcp_server():
    server = importlib.import_module("server")
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        await engine.dispose()
        pytest.skip(f"Postgres not reachable for MCP tests: {exc}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(CURRENT_ESTIMATES_VIEW))
        await conn.execute(text(_TRUNCATE))

    TestSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with TestSession() as s:
        await _seed(s)
        await s.commit()

    original = server.SessionFactory
    server.SessionFactory = TestSession  # tools resolve this at call time
    try:
        yield server
    finally:
        server.SessionFactory = original
        async with engine.begin() as conn:
            await conn.execute(text(_TRUNCATE))
        await engine.dispose()
