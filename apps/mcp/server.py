"""FastMCP server exposing the KPI data API to AI agents.

Every tool delegates to ``kpi_perf_summary_core.services.KpiService`` — the SAME logic
that powers the FastAPI app — so humans and agents always see identical data.

Run:
    python server.py --transport stdio          # for Claude Desktop / Cursor (local)
    python server.py --transport http --port 8765   # for HTTP-capable clients
"""

from __future__ import annotations

import argparse

from fastmcp import FastMCP
from kpi_perf_summary_core.db.session import SessionFactory
from kpi_perf_summary_core.repositories import NotFoundError
from kpi_perf_summary_core.services import KpiService

mcp = FastMCP(
    name="kpi-summary",
    instructions=(
        "Provides quarterly KPI estimates for public companies. "
        "Each company has a ticker and belongs to a sector. KPIs (e.g. Total "
        "Revenue ($MM), Global Net Added Subscribers) have HISTORICAL quarterly "
        "values and QTD (quarter-to-date) intra-quarter snapshots keyed by an "
        "'as_of' date. Typical flow: search_companies -> get_company_summary -> "
        "get_kpi_series. Always pass tickers and KPI names exactly as returned."
    ),
)


async def _with_service(fn):
    async with SessionFactory() as session:
        return await fn(KpiService(session))


def _dump(model) -> dict:
    return model.model_dump(mode="json")


@mcp.tool
async def list_sectors() -> list[dict]:
    """List all sectors with the number of companies in each. Start here to
    discover what is available."""
    return [_dump(s) for s in await _with_service(lambda svc: svc.list_sectors())]


@mcp.tool
async def list_kpis() -> list[dict]:
    """List the KPI catalog (name, unit, description). Use the returned KPI
    'name' verbatim when calling get_kpi_series or get_qtd."""
    return [_dump(k) for k in await _with_service(lambda svc: svc.list_kpis())]


@mcp.tool
async def search_companies(query: str, sector: str | None = None) -> list[dict]:
    """Find companies by name or ticker (optionally filtered by sector).
    Returns ticker, name, and sector. Use this to resolve a company name to its
    ticker before pulling data."""
    rows = await _with_service(
        lambda svc: svc.search_companies(search=query, sector=sector, limit=20)
    )
    return [_dump(c) for c in rows]


@mcp.tool
async def get_company(ticker: str) -> dict:
    """Get a company profile: name, sector, the KPIs available for it, and when
    its data was last updated."""
    try:
        return _dump(await _with_service(lambda svc: svc.get_company_detail(ticker)))
    except NotFoundError as e:
        return {"error": str(e), "hint": "Try search_companies to find the ticker."}


@mcp.tool
async def get_company_summary(ticker: str) -> dict:
    """At-a-glance summary for a company: for each KPI, the latest quarterly
    value, quarter-over-quarter % change, year-over-year % change, and the latest
    QTD value with its as_of date. Best single call for a quick read."""
    try:
        return _dump(await _with_service(lambda svc: svc.get_company_summary(ticker)))
    except NotFoundError as e:
        return {"error": str(e), "hint": "Try search_companies to find the ticker."}


@mcp.tool
async def get_kpi_series(
    ticker: str,
    kpi: str,
    date_from: str | None = None,
    date_to: str | None = None,
    est_type: str | None = None,
) -> dict:
    """Get the full time series for one (company, KPI): historical quarterly
    values plus the QTD trajectory. 'kpi' is the KPI name from list_kpis.
    Optional date_from/date_to (YYYY-MM-DD) filter the range; est_type
    ('historical' or 'qtd') filters which series are returned."""
    try:
        series = await _with_service(
            lambda svc: svc.get_series(ticker, kpi, _d(date_from), _d(date_to))
        )
    except NotFoundError as e:
        return {"error": str(e), "hint": "Check ticker via search_companies and KPI via list_kpis."}
    out = _dump(series)
    if est_type == "historical":
        out["qtd"] = []
    elif est_type == "qtd":
        out["historical"] = []
    return out


@mcp.tool
async def get_qtd(ticker: str, kpi: str) -> dict:
    """Get just the latest quarter-to-date snapshot and the intra-quarter
    trajectory for one (company, KPI), including the 'as_of' date of the most
    recent snapshot."""
    try:
        series = await _with_service(lambda svc: svc.get_series(ticker, kpi))
    except NotFoundError as e:
        return {"error": str(e)}
    return {
        "ticker": series.ticker,
        "kpi": series.kpi,
        "unit": series.unit,
        "qtd_as_of": series.qtd_as_of.isoformat() if series.qtd_as_of else None,
        "latest_qtd_value": series.qtd[-1].value if series.qtd else None,
        "trajectory": [_dump(p) for p in series.qtd],
    }


@mcp.tool
async def compare_companies(tickers: list[str], kpi: str) -> dict:
    """Compare the latest historical value of one KPI across several companies.
    'tickers' is a list of ticker symbols; 'kpi' is the KPI name."""

    async def _run(svc: KpiService):
        results = []
        for t in tickers:
            try:
                s = await svc.get_series(t, kpi)
            except NotFoundError:
                results.append({"ticker": t, "error": "not found"})
                continue
            latest = s.historical[-1] if s.historical else None
            results.append(
                {
                    "ticker": s.ticker,
                    "company_name": s.company_name,
                    "latest_period": latest.fiscal_period if latest else None,
                    "latest_value": latest.value if latest else None,
                    "unit": s.unit,
                }
            )
        return results

    return {"kpi": kpi, "results": await _with_service(_run)}


def _d(value: str | None):
    from datetime import date

    return date.fromisoformat(value) if value else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()
