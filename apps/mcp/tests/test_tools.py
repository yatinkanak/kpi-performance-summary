"""Tests for the FastMCP tool functions.

The tools delegate to the shared core service (already covered in the api suite), so these
focus on the MCP layer itself: output shaping, the est_type filtering, the QTD projection,
cross-company comparison, and the guiding error messages returned to the agent.
"""

KPI = "Total Revenue ($MM)"


async def test_list_sectors(mcp_server):
    out = await mcp_server.list_sectors()
    tech = next(s for s in out if s["name"] == "Tech")
    assert tech["company_count"] == 2


async def test_list_kpis(mcp_server):
    assert any(k["name"] == KPI and k["unit"] == "$MM" for k in await mcp_server.list_kpis())


async def test_search_companies(mcp_server):
    out = await mcp_server.search_companies("acme")
    assert [c["ticker"] for c in out] == ["ACME"]


async def test_get_company_summary(mcp_server):
    out = await mcp_server.get_company_summary("ACME")
    rev = next(k for k in out["kpis"] if k["kpi"] == KPI)
    assert rev["qoq_pct"] == 25.0 and rev["yoy_pct"] == 100.0 and rev["qtd_value"] == 90.0


async def test_get_kpi_series_est_type_filter(mcp_server):
    full = await mcp_server.get_kpi_series("ACME", KPI)
    assert len(full["historical"]) == 5 and len(full["qtd"]) == 2

    hist = await mcp_server.get_kpi_series("ACME", KPI, est_type="historical")
    assert hist["qtd"] == [] and len(hist["historical"]) == 5

    qtd = await mcp_server.get_kpi_series("ACME", KPI, est_type="qtd")
    assert qtd["historical"] == [] and len(qtd["qtd"]) == 2


async def test_get_qtd(mcp_server):
    out = await mcp_server.get_qtd("ACME", KPI)
    assert out["latest_qtd_value"] == 90.0
    assert out["qtd_as_of"] == "2025-05-15"
    assert len(out["trajectory"]) == 2


async def test_compare_companies(mcp_server):
    out = await mcp_server.compare_companies(["ACME", "BETA", "NOPE"], KPI)
    by = {r["ticker"]: r for r in out["results"]}
    assert by["ACME"]["latest_value"] == 200.0
    assert by["BETA"]["latest_value"] == 300.0
    assert by["NOPE"]["error"] == "not found"


async def test_get_company_not_found_returns_hint(mcp_server):
    out = await mcp_server.get_company("NOPE")
    assert "error" in out and "search_companies" in out["hint"]
