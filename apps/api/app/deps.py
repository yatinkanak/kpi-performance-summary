"""Shared FastAPI dependencies."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kpi_perf_summary_core.config import get_settings
from kpi_perf_summary_core.db.session import get_session
from kpi_perf_summary_core.services import KpiService


async def get_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KpiService:
    return KpiService(session)


ServiceDep = Annotated[KpiService, Depends(get_service)]


def require_publish_token(
    x_publish_token: Annotated[str | None, Header()] = None,
) -> None:
    """Gate the single write endpoint with a service token (no user auth in scope).

    Uses a constant-time comparison so the check doesn't leak the token via timing.
    """
    if x_publish_token is None or not secrets.compare_digest(
        x_publish_token, get_settings().publish_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Publish-Token",
        )
