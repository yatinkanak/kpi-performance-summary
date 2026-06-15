"""Pytest fixtures for Postgres-backed integration tests.

DB-backed tests request ``db_session`` (an ``AsyncSession``) or ``api_client`` (an httpx
client wired to that session). Each test runs against the Postgres configured by
``KPS_DATABASE_URL`` — the same DB the app uses; in CI / ``make test`` this is the compose
``db`` service. Work happens inside a transaction that is rolled back after the test (the
session joins it via a SAVEPOINT, so even the publish path's ``commit()`` stays contained),
so tests never pollute each other or the database.

If Postgres is unreachable the DB tests are **skipped** (not failed), so the no-DB smoke
tests still pass on a bare ``pytest`` run. We test against Postgres rather than SQLite on
purpose: the schema relies on Postgres-only behavior (``DISTINCT ON``, partial indexes,
native ENUM, ``SMALLINT``/``BIGINT`` identity PKs), so SQLite would test a different DB.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import pytest_asyncio
from kpi_perf_summary_core.config import get_settings
from kpi_perf_summary_core.db.models import Base, Company, Estimate, EstimateType, Kpi, Sector
from kpi_perf_summary_core.db.session import get_session
from kpi_perf_summary_core.db.views import CURRENT_ESTIMATES_VIEW
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture
async def pg_engine():
    """Function-scoped async engine; creates the schema, or skips if no DB is reachable."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError) as exc:
            pytest.skip(f"Postgres not reachable for DB tests: {exc}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text(CURRENT_ESTIMATES_VIEW))
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(pg_engine) -> AsyncSession:
    """An ``AsyncSession`` wrapped in a transaction rolled back after each test.

    ``join_transaction_mode="create_savepoint"`` lets code under test call ``commit()``
    (e.g. the publish path) without ending the outer transaction, so isolation holds.
    """
    conn = await pg_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def api_client(db_session) -> httpx.AsyncClient:
    """httpx client bound to the app, with the DB dependency pointed at ``db_session`` so
    requests see data the test staged (and everything rolls back afterward)."""
    from app.main import app

    async def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


async def seed_dataset(session: AsyncSession) -> None:
    """Insert a deterministic dataset: company TSTCO / KPI 'Test Revenue ($MM)' with five
    historical quarters (100→120→140→160→200) and two QTD snapshots (50, 90) so QoQ
    (=25.0), YoY (=100.0), and the QTD trajectory have known expected values.

    Adds and flushes; the caller decides whether to commit.

    Uses deliberately synthetic identifiers (``TSTCO`` / ``Test Sector`` / ``Test Revenue``)
    that cannot collide with the real seeded dataset, so DB tests pass whether they run
    against an empty schema (``make test``) or a database already seeded from the CSV.
    """
    sector = Sector(name="Test Sector")
    session.add(sector)
    await session.flush()

    company = Company(ticker="TSTCO", name="Testco Industries", sector_id=sector.id)
    kpi = Kpi(name="Test Revenue ($MM)", unit="$MM")
    session.add_all([company, kpi])
    await session.flush()

    hist = [
        ("2024Q1", date(2024, 1, 1), date(2024, 3, 31), 100.0),
        ("2024Q2", date(2024, 4, 1), date(2024, 6, 30), 120.0),
        ("2024Q3", date(2024, 7, 1), date(2024, 9, 30), 140.0),
        ("2024Q4", date(2024, 10, 1), date(2024, 12, 31), 160.0),
        ("2025Q1", date(2025, 1, 1), date(2025, 3, 31), 200.0),
    ]
    for fp, ps, pe, val in hist:
        session.add(
            Estimate(
                company_id=company.id,
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
    qtd = [(date(2025, 4, 30), 50.0), (date(2025, 5, 15), 90.0)]
    for as_of, val in qtd:
        session.add(
            Estimate(
                company_id=company.id,
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
    await session.flush()


@pytest_asyncio.fixture
async def seeded(db_session) -> AsyncSession:
    """db_session pre-populated with :func:`seed_dataset`."""
    await seed_dataset(db_session)
    return db_session
