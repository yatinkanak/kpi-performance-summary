"""Unit/integration tests for the shared core service layer (KpiService).

This is the keystone logic imported by both the API and MCP adapters, so covering it here
exercises the business rules both depend on: QoQ/YoY math, series assembly, KPI resolution,
publish validation, and the append-only / current-view contract.
"""

from datetime import UTC, date, datetime

import pytest
from kpi_perf_summary_core import schemas
from kpi_perf_summary_core.db.models import Company, Estimate, EstimateType, Kpi, Sector
from kpi_perf_summary_core.repositories import NotFoundError
from kpi_perf_summary_core.services import KpiService, _pct_change
from sqlalchemy import func, select


# ----- pure math (no DB) -------------------------------------------------
def test_pct_change():
    assert _pct_change(200.0, 160.0) == 25.0
    assert _pct_change(200.0, 100.0) == 100.0
    assert _pct_change(None, 100.0) is None
    assert _pct_change(100.0, None) is None
    assert _pct_change(100.0, 0.0) is None  # guards divide-by-zero


# ----- summary math (QoQ / YoY / QTD) ------------------------------------
async def test_company_summary(seeded):
    summary = await KpiService(seeded).get_company_summary("TSTCO")
    assert summary.ticker == "TSTCO"
    rev = next(k for k in summary.kpis if k.kpi == "Test Revenue ($MM)")
    assert rev.latest_period == "2025Q1"
    assert rev.latest_value == 200.0
    assert rev.qoq_pct == 25.0  # 200 vs 160
    assert rev.yoy_pct == 100.0  # 200 vs 100 (four quarters back)
    assert rev.qtd_value == 90.0
    assert rev.qtd_as_of == date(2025, 5, 15)
    assert rev.unit == "$MM"


async def test_list_sectors_counts(seeded):
    sectors = await KpiService(seeded).list_sectors()
    assert next(s for s in sectors if s.name == "Test Sector").company_count == 1


# ----- series assembly ---------------------------------------------------
async def test_get_series(seeded):
    s = await KpiService(seeded).get_series("TSTCO", "Test Revenue ($MM)")
    assert [p.fiscal_period for p in s.historical] == [
        "2024Q1",
        "2024Q2",
        "2024Q3",
        "2024Q4",
        "2025Q1",
    ]
    assert s.historical[-1].value == 200.0
    assert len(s.qtd) == 2
    assert s.qtd_as_of == date(2025, 5, 15)
    assert s.unit == "$MM"


async def test_resolve_kpi_by_id_and_name(seeded):
    svc = KpiService(seeded)
    kpi = await svc.repo.get_kpi_by_name("Test Revenue ($MM)")
    by_id = await svc.get_series("TSTCO", kpi.id)  # numeric id
    by_digit = await svc.get_series("TSTCO", str(kpi.id))  # digit string
    by_name = await svc.get_series("tstco", "Test Revenue ($MM)")  # name + lc ticker
    assert by_id.kpi == by_digit.kpi == by_name.kpi == "Test Revenue ($MM)"


async def test_date_range_filter(seeded):
    s = await KpiService(seeded).get_series(
        "TSTCO", "Test Revenue ($MM)", date_from=date(2025, 1, 1), date_to=date(2025, 3, 31)
    )
    assert [p.fiscal_period for p in s.historical] == ["2025Q1"]


# ----- not-found paths ---------------------------------------------------
async def test_unknown_ticker_raises(seeded):
    svc = KpiService(seeded)
    with pytest.raises(NotFoundError):
        await svc.get_company_detail("NOPE")
    with pytest.raises(NotFoundError):
        await svc.get_series("NOPE", "Test Revenue ($MM)")


async def test_unknown_kpi_raises(seeded):
    with pytest.raises(NotFoundError):
        await KpiService(seeded).get_series("TSTCO", "No Such KPI")


# ----- search ------------------------------------------------------------
async def test_search(seeded):
    svc = KpiService(seeded)
    assert any(c.ticker == "TSTCO" for c in (await svc.search("testco")).companies)
    assert any(s.name == "Test Sector" for s in (await svc.search("test sector")).sectors)
    assert any("Revenue" in k.name for k in (await svc.search("revenue")).kpis)


# ----- publish: validation ----------------------------------------------
async def test_publish_qtd_requires_as_of(seeded):
    payload = schemas.PublishEstimateIn(
        period_start=date(2025, 4, 1),
        period_end=date(2025, 6, 30),
        fiscal_period="2025Q2",
        est_type="qtd",
        value=120.0,
        as_of=None,
    )
    with pytest.raises(ValueError, match="as_of"):
        await KpiService(seeded).publish_estimate("TSTCO", "Test Revenue ($MM)", payload)


async def test_publish_historical_rejects_as_of(seeded):
    payload = schemas.PublishEstimateIn(
        period_start=date(2025, 1, 1),
        period_end=date(2025, 3, 31),
        fiscal_period="2025Q1",
        est_type="historical",
        value=210.0,
        as_of=date(2025, 3, 31),
    )
    with pytest.raises(ValueError, match="Historical"):
        await KpiService(seeded).publish_estimate("TSTCO", "Test Revenue ($MM)", payload)


# ----- publish: append-only + current-view "latest wins" -----------------
async def test_publish_appends_and_latest_wins(db_session):
    # Self-contained data so we can pin the existing row's publish time and make
    # "latest publish wins" deterministic (a fresh publish stamps now() > 2025).
    sector = Sector(name="ApndSector")
    db_session.add(sector)
    await db_session.flush()
    company = Company(ticker="APND", name="Append Co", sector_id=sector.id)
    kpi = Kpi(name="Revenue X", unit="$MM")
    db_session.add_all([company, kpi])
    await db_session.flush()
    db_session.add(
        Estimate(
            company_id=company.id,
            kpi_id=kpi.id,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            fiscal_period="2025Q1",
            est_type=EstimateType.historical,
            value=100.0,
            as_of=None,
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
            source="seed",
        )
    )
    await db_session.flush()

    svc = KpiService(db_session)
    out = await svc.publish_estimate(
        "APND",
        "Revenue X",
        schemas.PublishEstimateIn(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            fiscal_period="2025Q1",
            est_type="historical",
            value=999.0,
            as_of=None,
        ),
    )
    assert out.value == 999.0

    # current_estimates collapses to the latest publish ...
    s = await svc.get_series("APND", "Revenue X")
    q1 = [p for p in s.historical if p.fiscal_period == "2025Q1"]
    assert len(q1) == 1 and q1[0].value == 999.0

    # ... while the ledger retains both rows as an audit trail.
    count = await db_session.scalar(
        select(func.count())
        .select_from(Estimate)
        .where(
            Estimate.company_id == company.id,
            Estimate.kpi_id == kpi.id,
            Estimate.period_start == date(2025, 1, 1),
        )
    )
    assert count == 2
