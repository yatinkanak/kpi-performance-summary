# KPI Performance Summary

A full-stack app that lets time-constrained public investors view top-line KPI
performance (Revenue, Subscribers, ASP, Units Sold) for public companies —
served to **humans** (React web app) and **AI agents** (MCP server) over a
single shared data core.

> Full design rationale, schema, and trade-offs: **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

```
React SPA ─┐                ┌── FastAPI  (REST)  ─┐
           ├─ HTTP / JSON ──┤                     ├─ kpi_perf_summary_core ─ Postgres
AI agents ─┘                └── FastMCP (tools) ──┘     (shared logic)
```

## Quick start (Docker — one command)

```bash
cp .env.example .env
make up           # builds db + api + mcp + frontend; API seeds the CSV on first boot
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| API metrics (Prometheus) | http://localhost:8000/metrics |
| MCP server (HTTP) | http://localhost:8765/mcp |

`make down` stops it; `make clean` also wipes the database volume; `make seed`
re-runs the loader; `make test` runs backend tests.

## What you can do

- **Browse** companies by sector; **search** sectors / companies / KPIs (top bar).
- **Company summary**: per-KPI latest value, QoQ %, YoY %, and latest QTD with as-of date.
- **KPI detail**: historical vs QTD chart, date-range filter (URL-driven, shareable),
  "last updated" / "QTD as-of" badges, and **CSV export** of the current view.
- **Publish** a new estimate (write path), gated by a service token:

```bash
curl -X POST http://localhost:8000/api/v1/companies/IGC/kpis/Total%20Revenue%20%28%24MM%29/estimates \
  -H "Content-Type: application/json" -H "X-Publish-Token: dev-publish-token" \
  -d '{"period_start":"2026-01-01","period_end":"2026-03-31","fiscal_period":"2026Q1","est_type":"qtd","value":640.0,"as_of":"2026-03-31"}'
```

## MCP server (AI agents)

The same core powers an MCP server with tools for company lookup, KPI series, and QTD
queries. Connection instructions for Claude Desktop / Cursor (stdio and HTTP) are in
**[apps/mcp/README.md](./apps/mcp/README.md)**.

## Repository layout

```
packages/core/   # shared domain: models, schemas, repositories, services (the keystone)
apps/api/        # FastAPI adapter + CSV seed + Dockerfile   → apps/api/README.md
apps/mcp/        # FastMCP adapter (imports core services)   → apps/mcp/README.md
frontend/        # React + TS + Vite + TanStack Query + Recharts  → frontend/README.md
```

Component-level docs: **[backend](./apps/api/README.md)** · **[MCP server](./apps/mcp/README.md)** · **[frontend](./frontend/README.md)**.

## Key design decisions (summary)

- **One shared core, two adapters** — REST and MCP import the same services, so human
  and agent views can never drift.
- **Append-only `estimates` ledger + `current_estimates` view** — publishing inserts
  (never updates), giving a free audit trail; reads see the latest publish per logical key.
- **`as_of` models the QTD trajectory** — intra-quarter snapshots are first-class, not
  overwritten.
- **Postgres window functions** compute QoQ/YoY in the service layer.

See [ARCHITECTURE.md §8](./ARCHITECTURE.md) for security, observability, scalability, and
[§9](./ARCHITECTURE.md) for future improvements.

## Local development (without Docker)

The backend uses [**uv**](https://docs.astral.sh/uv/) — install it with `brew install uv`
(or `curl -LsSf https://astral.sh/uv/install.sh | sh`). uv reads the pinned Python from
`.python-version` and installs it for you, so **no system Python is required**. You also
need Node 20+ and a local Postgres.

The repo is a **uv workspace**: a single `uv sync` at the root provisions one shared `.venv`
with `core` + `api` + `mcp` (all editable) plus the test tooling.

```bash
# Backend — provision Python + the shared venv, then seed and run the API
uv sync                                                  # = make install
export KPS_DATABASE_URL=postgresql+asyncpg://kps:kps@localhost:5432/kps
cd apps/api && uv run python -m scripts.init_db && uv run python -m scripts.seed
uv run uvicorn app.main:app --reload                     # http://localhost:8000/docs

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# frontend unit tests (Vitest, no backend needed): npm test
```

Run the backend tests with `make test-local` (or `uv run pytest -q` from the repo root).
`make dev` does the seed + run steps above in one shot. Per-component setup (including the
MCP server) lives in each component's README — see the links above.
