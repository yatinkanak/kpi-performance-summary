"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from kpi_perf_summary_core.db.session import get_session
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(session: Annotated[AsyncSession, Depends(get_session)]):
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
