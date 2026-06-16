"""HTTP-level tests for the FastAPI adapter.

Drives the app through httpx against a real Postgres (via the ``api_client`` fixture, whose
DB session is shared with ``seeded``), covering routing, response shaping, error mapping
(404 / 400), and the publish-token gate (403).
"""

from kpi_perf_summary_core.config import get_settings
from kpi_perf_summary_core.db.models import Kpi
from sqlalchemy import select

TOKEN = get_settings().publish_token
SERIES = "/api/v1/companies/TSTCO/kpis/Test Revenue ($MM)/series"
PUBLISH = "/api/v1/companies/TSTCO/kpis/Test Revenue ($MM)/estimates"


async def test_sectors_endpoint(seeded, api_client):
    r = await api_client.get("/api/v1/sectors")
    assert r.status_code == 200
    assert any(s["name"] == "Test Sector" and s["company_count"] == 1 for s in r.json())


async def test_companies_browse_and_search(seeded, api_client):
    r = await api_client.get("/api/v1/companies")
    assert r.status_code == 200 and any(c["ticker"] == "TSTCO" for c in r.json())
    r2 = await api_client.get("/api/v1/companies", params={"search": "testco"})
    assert [c["ticker"] for c in r2.json()] == ["TSTCO"]


async def test_company_detail_and_404(seeded, api_client):
    r = await api_client.get("/api/v1/companies/TSTCO")
    assert r.status_code == 200 and r.json()["sector"] == "Test Sector"
    assert (await api_client.get("/api/v1/companies/NOPE")).status_code == 404


async def test_summary_endpoint(seeded, api_client):
    r = await api_client.get("/api/v1/companies/TSTCO/summary")
    assert r.status_code == 200
    rev = next(k for k in r.json()["kpis"] if k["kpi"] == "Test Revenue ($MM)")
    assert rev["qoq_pct"] == 25.0 and rev["yoy_pct"] == 100.0 and rev["qtd_value"] == 90.0


async def test_series_by_name_and_id(seeded, api_client, db_session):
    r = await api_client.get(SERIES)
    assert r.status_code == 200
    body = r.json()
    assert len(body["historical"]) == 5 and len(body["qtd"]) == 2

    kpi = await db_session.scalar(select(Kpi).where(Kpi.name == "Test Revenue ($MM)"))
    r2 = await api_client.get(f"/api/v1/companies/TSTCO/kpis/{kpi.id}/series")
    assert r2.status_code == 200 and r2.json()["kpi"] == "Test Revenue ($MM)"


async def test_series_unknown_ticker_404(seeded, api_client):
    r = await api_client.get("/api/v1/companies/NOPE/kpis/Test Revenue ($MM)/series")
    assert r.status_code == 404


async def test_search_endpoint(seeded, api_client):
    r = await api_client.get("/api/v1/search", params={"q": "testco"})
    assert r.status_code == 200
    assert any(c["ticker"] == "TSTCO" for c in r.json()["companies"])


# ----- favorites: add / list (with metrics) / remove ---------------------
FAVORITES = "/api/v1/favorites"
FAV_BODY = {"ticker": "TSTCO", "kpi": "Test Revenue ($MM)"}


async def test_add_list_remove_favorite(seeded, api_client):
    r = await api_client.post(FAVORITES, json=FAV_BODY)
    assert r.status_code == 201
    fav = r.json()
    assert fav["ticker"] == "TSTCO" and fav["kpi"] == "Test Revenue ($MM)"
    # the favorite carries its at-a-glance metrics
    assert fav["metrics"]["qoq_pct"] == 25.0 and fav["metrics"]["yoy_pct"] == 100.0

    listed = (await api_client.get(FAVORITES)).json()
    assert any(f["ticker"] == "TSTCO" and f["kpi"] == "Test Revenue ($MM)" for f in listed)

    d = await api_client.delete(FAVORITES, params=FAV_BODY)
    assert d.status_code == 204
    after = (await api_client.get(FAVORITES)).json()
    assert not any(f["ticker"] == "TSTCO" for f in after)


async def test_add_favorite_unknown_ticker_404(seeded, api_client):
    r = await api_client.post(FAVORITES, json={"ticker": "NOPE", "kpi": "Test Revenue ($MM)"})
    assert r.status_code == 404


# ----- publish: auth gate + validation + success -------------------------
def _qtd_body():
    return {
        "period_start": "2025-04-01",
        "period_end": "2025-06-30",
        "fiscal_period": "2025Q2",
        "est_type": "qtd",
        "value": 120.0,
        "as_of": "2025-05-31",
    }


async def test_publish_missing_token_403(seeded, api_client):
    r = await api_client.post(PUBLISH, json=_qtd_body())
    assert r.status_code == 403


async def test_publish_bad_token_403(seeded, api_client):
    r = await api_client.post(PUBLISH, json=_qtd_body(), headers={"X-Publish-Token": "wrong"})
    assert r.status_code == 403


async def test_publish_validation_400(seeded, api_client):
    body = _qtd_body()
    del body["as_of"]  # qtd without as_of -> ValueError -> 400
    r = await api_client.post(PUBLISH, json=body, headers={"X-Publish-Token": TOKEN})
    assert r.status_code == 400


async def test_publish_success_201(seeded, api_client):
    r = await api_client.post(PUBLISH, json=_qtd_body(), headers={"X-Publish-Token": TOKEN})
    assert r.status_code == 201
    assert r.json()["value"] == 120.0 and r.json()["est_type"] == "qtd"
