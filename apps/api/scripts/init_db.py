"""Create tables and the current_estimates view.

Idempotent. In production this would be Alembic migrations; for the take-home a
single create_all + CREATE OR REPLACE VIEW keeps the stack one command to run.
"""

from __future__ import annotations

import asyncio

from kpi_perf_summary_core.db.models import Base
from kpi_perf_summary_core.db.session import engine
from kpi_perf_summary_core.db.views import CURRENT_ESTIMATES_VIEW
from sqlalchemy import text


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(CURRENT_ESTIMATES_VIEW))
    print("init_db: tables and current_estimates view ready")


if __name__ == "__main__":
    asyncio.run(main())
