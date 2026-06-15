# Backend — FastAPI adapter (`apps/api`)

The HTTP/REST adapter for the KPI Performance Summary app. It is a thin layer over
the shared domain package **`packages/core` (`kpi_perf_summary_core`)** — all business logic
(series assembly, QoQ/YoY math, the publish path) lives in core and is reused by the
MCP server, so the two adapters can never drift.

> System-wide design and rationale: **[../../ARCHITECTURE.md](../../ARCHITECTURE.md)**.

## Structure

```
apps/api/
├── app/
│   ├── main.py            # app factory: middleware, CORS, exception handlers, routers, /metrics
│   ├── deps.py            # DI: DB session → KpiService; publish-token guard
│   ├── observability.py   # structlog JSON logging, request-id middleware, Prometheus RED metrics
│   └── api/v1/
│       ├── health.py      # /healthz, /readyz
│       ├── search.py      # /sectors, /search
│       ├── kpis.py        # /kpis
│       ├── companies.py   # /companies, /{ticker}, /summary, /series, /series/export
│       └── estimates.py   # POST publish (token-gated)
├── scripts/
│   ├── init_db.py         # create tables + current_estimates view (idempotent)
│   └── seed.py            # load data/kpi_sample_2000.csv (skips if already seeded)
├── data/kpi_sample_2000.csv
├── tests/test_smoke.py    # no-DB smoke tests (health + OpenAPI contract)
└── Dockerfile
```

## API routes

All under `/api/v1` (except probes and `/metrics`). Interactive docs at `/docs`.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/sectors` | Sectors with company counts |
| `GET` | `/companies?search=&sector=&limit=&offset=` | Browse / search companies (paginated, `limit ≤ 200`) |
| `GET` | `/companies/{ticker}` | Profile + available KPIs + `last_updated` |
| `GET` | `/companies/{ticker}/summary` | At-a-glance: per-KPI latest, QoQ %, YoY %, latest QTD + as_of |
| `GET` | `/companies/{ticker}/kpis/{kpi_id}/series?from=&to=` | Historical + QTD series. `kpi_id` accepts a numeric id **or** KPI name |
| `GET` | `/companies/{ticker}/kpis/{kpi_id}/series/export?from=&to=` | CSV export of the current view |
| `GET` | `/kpis` | KPI catalog |
| `GET` | `/search?q=` | Unified search across sectors / companies / KPIs |
| `POST` | `/companies/{ticker}/kpis/{kpi_id}/estimates` | **Publish** a new estimate (append-only). Requires `X-Publish-Token`; returns 201 |
| `GET` | `/healthz` `/readyz` `/metrics` | Liveness, readiness (DB ping), Prometheus |

### Publish example

```bash
curl -X POST 'http://localhost:8000/api/v1/companies/IGC/kpis/Total%20Revenue%20(%24MM)/estimates' \
  -H 'Content-Type: application/json' -H 'X-Publish-Token: dev-publish-token' \
  -d '{"period_start":"2026-01-01","period_end":"2026-03-31","fiscal_period":"2026Q1","est_type":"qtd","value":640.0,"as_of":"2026-03-31"}'
```

Publishing **inserts** a new immutable row; the `current_estimates` view always returns the
latest publish per logical key, so prior revisions are retained as an audit trail.
Validation: `qtd` requires `as_of`; `historical` must omit it.

## Running

### Via Docker (from repo root) — recommended

```bash
make up        # starts db + api (+ mcp + frontend); api runs init_db + seed on boot
make logs      # tail api logs
make seed      # re-run the seed against a running stack
make test      # pytest inside the api image
```

### Local (without Docker)

Uses [**uv**](https://docs.astral.sh/uv/) — install it with `brew install uv` (or
`curl -LsSf https://astral.sh/uv/install.sh | sh`). uv installs the pinned Python from
`.python-version` automatically, so **no system Python is needed**. Requires a reachable
Postgres.

The repo is a uv workspace: a single `uv sync` at the **repo root** provisions one shared
`.venv` for the core and both adapters (api + mcp), all editable. Run these from the repo
root.

```bash
# 1. Provision Python + the shared venv (core + api + mcp + dev tools)
uv sync

# 2. Point at Postgres, create schema, and seed
export KPS_DATABASE_URL=postgresql+asyncpg://kps:kps@localhost:5432/kps
cd apps/api && uv run python -m scripts.init_db && uv run python -m scripts.seed

# 3. Run the API (and tests) — `uv run` uses the shared workspace venv
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs
uv run pytest -q
```

`uv run` always executes inside the workspace `.venv`, so there's nothing to activate. If
you prefer an activated shell (e.g. with direnv), `uv sync` creates a standard `.venv` you
can `source .venv/bin/activate` (`echo 'source .venv/bin/activate' >> .envrc && direnv allow`)
and then drop the `uv run` prefix.

### Tests

`make test` (from the repo root) runs the **api and mcp** suites in their images against a
throwaway Postgres. Locally, run `make test-local` (or `uv run pytest -q`) from the repo
root with a reachable DB. Everything tests against **real Postgres** (no SQLite — the schema
relies on Postgres-only features, so we test what we ship).

- **Smoke** (`test_smoke.py`) — no DB; app wiring + OpenAPI contract.
- **Core services** (`test_services.py`) — the shared business logic both adapters use:
  QoQ/YoY math, series assembly, KPI resolution, publish validation, and the append-only /
  current-view "latest publish wins" contract.
- **HTTP API** (`test_api.py`) — routing, response shaping, error mapping (404/400), and the
  publish-token gate (403).

DB-backed tests use the `db_session` / `api_client` fixtures (each test runs in a transaction
that is rolled back for isolation). They are **skipped** automatically if no DB is reachable,
so a bare `pytest` still passes (smoke + pure-math tests run); `make test` provides the DB.

## Configuration

Read by `kpi_perf_summary_core.config.Settings` (prefix **`KPS_`**):

| Variable | Default | Purpose |
|---|---|---|
| `KPS_DATABASE_URL` | `postgresql+asyncpg://kps:kps@localhost:5432/kps` | Async SQLAlchemy URL (asyncpg) |
| `KPS_DB_POOL_SIZE` | `10` | Persistent connections kept open in the pool (≥ 1) |
| `KPS_DB_MAX_OVERFLOW` | `20` | Extra connections allowed beyond the pool under burst (≥ 0) |
| `KPS_DB_POOL_TIMEOUT` | `30` | Seconds to wait for a free connection before erroring (≥ 1) |
| `KPS_DB_POOL_RECYCLE` | `1800` | Recycle connections older than N seconds; `-1` disables |
| `KPS_DB_POOL_PRE_PING` | `true` | Liveness-check a pooled connection before use |
| `KPS_ENVIRONMENT` | `development` | Set to `production` to enable production guards (rejects the default publish token). |
| `KPS_PUBLISH_TOKEN` | `dev-publish-token` | Token required by the publish endpoint. The default lets it run out of the box; when `KPS_ENVIRONMENT=production` the app refuses to start unless this is overridden with a strong, random value. Serve over TLS in production (the token rides in a request header). |
| `KPS_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Browser CORS allowlist |
| `KPS_MAX_PAGE_SIZE` | `200` | Pagination cap |
| `KPS_LOG_LEVEL` | `INFO` | structlog level |

## Cross-cutting concerns

- **Security:** Pydantic validation on all inputs; parameterized SQL (no SQLi); CORS
  allowlist; rate limiting via slowapi (120/min default); pagination caps; the single write
  path gated by `X-Publish-Token` (constant-time comparison; the default dev token is
  rejected when `KPS_ENVIRONMENT=production`, so a real deploy fails closed rather than
  shipping a known token). No user auth (out of scope per the assignment) — see
  ARCHITECTURE.md §9 for the path to real auth.
- **Observability:** JSON logs with a per-request `x-request-id`; Prometheus RED metrics at
  `/metrics` (latency labelled by route template to keep cardinality low); `/healthz` and
  `/readyz` probes. The append-only `estimates` table doubles as the audit log.
- **Errors:** domain exceptions map to clean HTTP — `NotFoundError → 404`, `ValueError → 400`,
  rate limit → 429.
