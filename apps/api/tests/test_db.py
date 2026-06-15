"""Postgres-backed integration test.

Runs against the real DB via the ``db_session`` fixture; skipped automatically when
Postgres isn't reachable (e.g. a bare local ``pytest``), and executed in ``make test``.
"""
from sqlalchemy import select

from kpi_perf_summary_core.db.models import Sector


async def test_db_session_roundtrip(db_session):
    db_session.add(Sector(name="Test Sector"))
    await db_session.flush()  # SMALLINT identity PK autoincrements on Postgres

    names = (await db_session.execute(select(Sector.name))).scalars().all()
    assert "Test Sector" in names
