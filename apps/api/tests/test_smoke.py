"""Lightweight smoke tests that do not require a database.

DB-backed integration tests run against the Postgres service (see README);
these verify the app wires up and the OpenAPI contract is generated.
"""

import httpx
import pytest
from app.main import app


@pytest.mark.asyncio
async def test_healthz():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_exposes_core_routes():
    paths = app.openapi()["paths"]
    assert "/api/v1/companies/{ticker}/summary" in paths
    assert "/api/v1/companies/{ticker}/kpis/{kpi_id}/series" in paths
    assert "/api/v1/search" in paths
