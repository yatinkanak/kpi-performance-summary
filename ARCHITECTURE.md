# Architecture — KPI Performance Summary

> A full-stack application that lets time-constrained public investors view top-line
> performance metrics (Revenue, Subscribers, ASP, Units Sold, …) for public
> companies. The same data layer is served to **humans** (React web app) and to
> **AI agents** (MCP server) through a single shared core.

---

## 1. Data model (derived from the sample dataset)

The design is grounded in the actual shape of `kpi_sample_2000.csv` (2,000 rows):

| Fact | Value |
|---|---|
| Companies | 20, each with a unique `ticker` and one `sector` |
| Sectors | 20 (≈1:1 to companies in the sample) |
| KPIs | 5 — `ASP ($)`, `Total Revenue ($MM)`, `Global Net Added Subscribers`, `U.S. Net Added Subscribers`, `Units Sold` |
| Unit | Functionally determined by KPI (`$`, `$MM`, `subs`, `units`) — not free per row |
| Logical series | 100 `(company, kpi)` pairs |
| Historical rows | 16 per series — one per fiscal quarter `2022Q1 → 2025Q4`, `as_of` empty (1,600 rows) |
| QTD rows | 4 per series — intra-quarter snapshots of the **current** quarter `2026Q1` at `as_of` ∈ {Jan 31, Feb 15, Feb 28, Mar 15} (400 rows) |

Two observations drive the schema:

1. **`as_of` makes QTD a *trajectory*, not a single number.** QTD values accumulate within
   the quarter (e.g. IGC revenue 263 → 395 → 503 → 627 across the four snapshots). All four
   points are meaningful and are charted together.
2. **"Publish new estimates" requires an append-only, versioned fact table** so revisions are
   auditable rather than destructive.

---

## 2. System architecture

The keystone decision: **the REST API and the MCP server are two thin adapters over one
shared `core` package.** Business logic (series assembly, summary math, QTD selection,
publish) is written once and imported by both. Neither adapter re-implements logic, so the
data humans see and the data agents see can never drift.

```
   Human users (browser)          AI agents (Claude · Cursor)
             │ HTTPS / JSON (OpenAPI)          │ stdio / HTTP (MCP)
             ▼                                 │
  ┌────────────────────┐                       │
  │   React + TS SPA   │                       │
  │   TanStack Query   │                       │
  │      Recharts      │                       │
  └──────────┬─────────┘                       │
             │                                 │
             ▼                                 ▼
  ┌────────────────────┐            ┌────────────────────┐
  │ FastAPI  (adapter) │            │ FastMCP  (adapter) │
  │      routers       │            │       tools        │
  └──────────┬─────────┘            └──────────┬─────────┘
             └────────────────┬────────────────┘
                              │ import / call
                              ▼
       ┌────────────────────────────────────────────┐
       │   Shared core  ·  kpi_perf_summary_core    │
       │          services → repositories           │
       └──────────────────────┬─────────────────────┘
                              │ SQLAlchemy (async)
                              ▼
             ┌────────────────────────────────┐    ┌──────────────────┐
             │           PostgreSQL           │◀──▶│ Redis (optional) │
             │estimates (fact) + current view │    │      cache       │
             └────────────────┬───────────────┘    └──────────────────┘
                              ▲ one-time seed
             ┌────────────────────────────────┐
             │  init_db + CSV loader (seed)   │
             └────────────────────────────────┘
```

### Technology choices (tied to constraints)

| Layer | Choice | Justification |
|---|---|---|
| Frontend | React + TS + **Vite** + **TanStack Query** + **Recharts** | Query gives caching / dedup / stale-while-revalidate out of the box for a read-heavy dashboard. URL-driven filter state makes views shareable. |
| Backend | **FastAPI (async)** + Pydantic + SQLAlchemy 2.0 | Async fits I/O-bound DB reads; Pydantic gives validation + auto OpenAPI, which generates the typed frontend client. |
| Shared core | plain Python package (`kpi_perf_summary_core`) | Logic written once; consumed by both API and MCP. |
| MCP | **FastMCP** | Imports the same `core.services`; no logic drift between humans and agents. |
| Database | **PostgreSQL** | `DISTINCT ON` selects the latest publish per logical key (the "current snapshot") in-database; append-only fact table is a free audit log. |
| Cache | Redis (optional at this scale) | Summary/series cached with `as_of`-derived keys, invalidated on publish. Designed-in, not required for 2k rows. |

---

## 3. Repository structure

```
kpi-performance-summary/
├── ARCHITECTURE.md                # this file
├── README.md                      # run instructions, decisions, MCP connect guide
├── docker-compose.yml             # postgres + api + mcp + frontend
├── Makefile                       # make up / seed / test (Docker) · install / test-local / dev (uv)
├── pyproject.toml                 # uv workspace root (ties core + api + mcp together)
├── uv.lock                        # locked dependency graph for the whole workspace
├── .python-version                # Python pinned for uv (3.12)
├── .env.example
├── packages/
│   └── core/                      # ← SHARED domain layer (the keystone)
│       └── kpi_perf_summary_core/
│           ├── config.py
│           ├── db/{session,models}.py   # async engine + SQLAlchemy ORM
│           ├── schemas.py               # Pydantic DTOs (shared by API + MCP)
│           ├── repositories.py          # SQL data access (no business logic)
│           └── services.py              # series assembly, summary math, publish
├── apps/
│   ├── api/                       # FastAPI adapter (depends on core)
│   │   ├── app/
│   │   │   ├── main.py            # app factory + middleware (CORS, rate limit, /metrics)
│   │   │   ├── api/v1/            # companies, kpis, estimates, search, health
│   │   │   ├── deps.py            # DI: DB session → service; publish-token guard
│   │   │   └── observability.py   # structlog, request-id, Prometheus
│   │   ├── scripts/{init_db,seed}.py
│   │   └── data/kpi_sample_2000.csv
│   └── mcp/                       # FastMCP adapter (depends on core)
│       └── server.py              # tool definitions → core.services
└── frontend/
    └── src/
        ├── api/                   # generated client + Query hooks
        ├── pages/                 # Dashboard, CompanyDetail, KpiDetail
        ├── components/            # SearchBar, KpiChart, SummaryCard, DateRangeFilter, ExportButton
        └── lib/                   # csv export, formatters
```

---

## 4. Database schema

Three small dimensions plus one append-only fact table.

```sql
CREATE TABLE sectors (
  id    SMALLSERIAL PRIMARY KEY,
  name  TEXT NOT NULL UNIQUE
);

CREATE TABLE companies (
  id          SERIAL PRIMARY KEY,
  ticker      TEXT NOT NULL UNIQUE,         -- stable natural key (API + MCP)
  name        TEXT NOT NULL,
  sector_id   INTEGER NOT NULL REFERENCES sectors(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE kpis (                          -- controlled vocabulary (5 rows)
  id          SMALLSERIAL PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,          -- 'Total Revenue ($MM)'
  unit        TEXT NOT NULL,                 -- '$MM'  (unit is FD by KPI)
  description TEXT
);

CREATE TYPE estimate_type AS ENUM ('historical', 'qtd');

-- Fact table: APPEND-ONLY ledger
CREATE TABLE estimates (
  id             BIGSERIAL PRIMARY KEY,
  company_id     INTEGER NOT NULL REFERENCES companies(id),
  kpi_id         INTEGER NOT NULL REFERENCES kpis(id),
  period_start   DATE NOT NULL,
  period_end     DATE NOT NULL,
  fiscal_period  TEXT NOT NULL,              -- '2026Q1' (display label)
  est_type       estimate_type NOT NULL,
  value          NUMERIC(20,4) NOT NULL,
  as_of          DATE,                       -- QTD snapshot date; NULL for historical
  published_at   TIMESTAMPTZ NOT NULL DEFAULT now(),  -- ingest/publish time → "last updated"
  source         TEXT NOT NULL              -- default 'seed' applied app-side on insert
);
```

### Append-only + "current view" — the core idea

Publishing never `UPDATE`s; it `INSERT`s. The current value of any series point is the
latest publish for that logical key. For QTD, each `as_of` is its own point (the whole
trajectory is meaningful); for historical, `as_of` is `NULL`, so revisions of the same
quarter collapse to the latest publish:

```sql
CREATE VIEW current_estimates AS
SELECT DISTINCT ON (company_id, kpi_id, period_start, est_type, as_of) *
FROM estimates
ORDER BY company_id, kpi_id, period_start, est_type, as_of, published_at DESC;
```

This yields a **full audit history for free** (every revision retained) while reads stay
simple. At scale, swap the view for a `MATERIALIZED VIEW` refreshed `CONCURRENTLY` on
publish, or maintain an `is_current` flag.

### Indexes

```sql
CREATE INDEX ix_est_series          ON estimates (company_id, kpi_id, period_start);
CREATE INDEX ix_est_qtd             ON estimates (company_id, kpi_id, as_of)
                                     WHERE est_type = 'qtd';   -- latest QTD fast path
CREATE INDEX ix_companies_ticker    ON companies (ticker);
CREATE INDEX ix_companies_sector_id ON companies (sector_id);
```

**Trade-offs:** `unit` lives on `kpis` (canonical; functionally determined) rather than per
row, removing the CSV's redundancy. `fiscal_period` is denormalized onto the fact for cheap
labelling though it is derivable from `period_start`. Company search is a case-insensitive
substring match (`lower(name/ticker) LIKE '%q%'`) — fine at this scale; a `pg_trgm` GIN index
is the upgrade path for fuzzy matching.

---

## 5. Backend API (FastAPI)

Versioned under `/api/v1`. Reads are public + rate-limited; the single write endpoint is
gated by a service token.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/sectors` | List sectors with company counts (nav tree) |
| `GET` | `/companies?search=&sector=&limit=&offset=` | Search / browse companies (paginated) |
| `GET` | `/companies/{ticker}` | Company profile + available KPIs + last_updated |
| `GET` | `/companies/{ticker}/summary` | **Top-line dashboard**: per-KPI latest value, QoQ %, YoY %, latest QTD + as_of |
| `GET` | `/companies/{ticker}/kpis/{kpi_id}/series?from=&to=&est_type=` | **Core chart endpoint**: historical series + QTD trajectory, unit, as_of, last_updated |
| `GET` | `/companies/{ticker}/kpis/{kpi_id}/series/export?format=csv` | Export current view (CSV / JSON) |
| `GET` | `/kpis` | KPI catalog |
| `GET` | `/search?q=` | Unified search across sectors / companies / KPIs |
| `POST` | `/companies/{ticker}/kpis/{kpi_id}/estimates` | **Publish** new estimate (append-only insert); token-gated; 201 |
| `GET` | `/healthz` `/readyz` `/metrics` | Liveness, readiness, Prometheus |

Summary math (QoQ vs prior quarter, YoY vs same quarter prior year) is computed in
`core.services` over the assembled series — positional lookups against the prior quarter and
the same quarter a year back — written once, reused by MCP.

---

## 6. Frontend data-fetching plan

- **Typed client generated from OpenAPI** (`openapi-typescript`) → no hand-written types,
  drift-proof against the backend.
- **TanStack Query** wraps each endpoint in a hook (`useCompanySummary`, `useKpiSeries`) with
  caching, dedup, and stale-while-revalidate. Query keys include filter params so each
  date-range / KPI view is cached independently.
- **URL is the source of truth for filter state** (`?from=&to=&kpi=`) → bookmarkable /
  shareable views; the export button serializes the *current* query result.
- **Pages:** Dashboard (sector → company drill-down) → Company detail (summary cards, all
  KPIs) → KPI detail (Recharts line chart: historical solid + QTD dashed, date-range filter,
  "last updated" / "QTD as-of" badges, CSV export).
- **Search:** debounced input → `/search`, results grouped by type.
- **Client security:** no secrets in the SPA; reads hit public rate-limited endpoints; the
  admin publish form attaches the service token server-side, never exposing it to the browser.

---

## 7. MCP server (FastMCP)

Tools mirror how an LLM reasons about the data — discovery → drill-down — with rich
descriptions, enum'd params, and responses pairing compact structured JSON with a one-line
natural-language summary.

| Tool | Signature | LLM intent |
|---|---|---|
| `list_sectors()` | → sectors | "What's available?" |
| `search_companies(query, sector?)` | → [{ticker, name, sector}] | Resolve a name to a ticker |
| `get_company(ticker)` | → profile + KPIs + last_updated | Orient on one company |
| `list_kpis(ticker?)` | → KPI catalog | "What can I ask about?" |
| `get_kpi_series(ticker, kpi, from?, to?, est_type?)` | → timeseries + unit + as_of | The data pull |
| `get_qtd(ticker, kpi)` | → latest QTD value + trajectory + as_of | "Where are we now, intra-quarter" |
| `get_company_summary(ticker)` | → per-KPI latest + QoQ/YoY + QTD | One-call insight |
| `compare_companies(tickers[], kpi, period)` | → aligned cross-company values | Comparative analysis |

Principles: stable string keys (`ticker`, KPI name) so the model never invents IDs; errors
return guiding messages ("ticker ABC not found; try search_companies"); the server
`import`s `core.services`, so MCP and REST cannot diverge. See README for the Claude Desktop /
Cursor connection config.

---

## 8. Security, observability, scalability

This section describes what is **implemented** today; the production hardening it points
toward is collected in §9.

**Security:** Pydantic validation on all inputs; SQLAlchemy parameterized queries (no SQLi);
a CORS allowlist; IP-based rate limiting (120/min default, via slowapi); pagination caps
(`limit ≤ 200`); and the single write path gated by a service token (`X-Publish-Token`,
constant-time comparison, with the dev default rejected under `KPS_ENVIRONMENT=production`).
Domain exceptions map to clean HTTP (404 / 400 / 429).

**Observability:** `structlog` JSON logs with a request-ID middleware (`x-request-id` echoed
on every response); Prometheus RED metrics at `/metrics` (latency and counts labelled by
*route template*, not raw path, to keep cardinality low); and the **append-only `estimates`
table doubles as an audit trail** — every published value is retained with its `published_at`
timestamp and `source`.

**Scalability:** FastAPI is stateless → scales horizontally behind a load balancer; an async
connection pool is configured and **env-tunable** (`KPS_DB_POOL_SIZE`, `KPS_DB_MAX_OVERFLOW`,
`KPS_DB_POOL_TIMEOUT`, `KPS_DB_POOL_RECYCLE`, `KPS_DB_POOL_PRE_PING`) so each deployment can
size the pool to its DB connection limits. Trivial at 2k rows — the structure holds at
millions; the path to get there (caching, replicas, partitioning) is in §9.

---

## 9. Future improvements

Grouped by area, roughly in priority order. These are deferred deliberately to keep the
take-home focused; revisit as needed.

### Data & schema
- **Retain QTD snapshot history across quarters** so "current QTD pace vs prior-quarter pace
  at the same point" becomes derivable. The sample only carries QTD for the live quarter
  (2026Q1), so the strongest investor signal — is this quarter tracking ahead of or behind
  the last few at the same point in the quarter? — is not yet computable. Near-term step:
  extend the seed/loader to synthesize prior-quarter QTD trajectories for demo, then add a
  `pace_vs_prior` field to the summary service.
- Confidence intervals / revision deltas on estimates; alerting when a new QTD snapshot
  deviates materially from prior estimates.

### Infrastructure & operations
- **Replace `create_all` + `CREATE OR REPLACE VIEW` with Alembic migrations.** The current
  one-command startup (`init_db`) is intentional for the take-home; production needs
  versioned, reversible migrations with a review trail, and a `MATERIALIZED VIEW` (refreshed
  `CONCURRENTLY` on publish) or an `is_current` flag in place of the live `current_estimates`
  view once the table grows.
- Redis caching on summary/series keyed by `as_of` (invalidated on publish); PgBouncer to cap
  total server-side connections once many API processes each run their own (now env-tunable)
  pool — `N workers × pool_size` can otherwise exceed Postgres `max_connections`; Postgres read
  replicas behind the read endpoints; partition `estimates` by `period_start`; a CDN for the
  static SPA.
- `Idempotency-Key` support for the publish endpoint (not yet implemented) so retried
  publishes are de-duplicated; per-client rate-limit tiers.

### Product & frontend
- WebSocket/SSE (Server Sent Events) push when daily QTD snapshots land; saved watchlists;
  sector-level rollups.
- Generate the frontend client from the OpenAPI schema in CI (`openapi-typescript`) so types
  can never drift from the backend (hand-written today).

### AI / MCP
- MCP **resources** (not just tools) exposing the KPI catalog for cheaper grounding; an
  LLM-eval harness scoring tool discoverability and answer quality.

### Observability
- **OpenTelemetry** traces spanning API/MCP → DB for end-to-end latency attribution.
- **Sentry** (or similar) for exception aggregation and alerting.
- Capture the publishing **actor** ("who") alongside the existing `published_at` ("when") once
  real auth lands, completing the audit trail.

### Security & auth
The publish endpoint is gated by a single shared service token (`X-Publish-Token`), compared
in constant time, with a dev-friendly default that's rejected under `KPS_ENVIRONMENT=production`
so a real deploy fails closed rather than shipping a known token — deliberately minimal for the
take-home. A production deployment should revisit this, e.g. proper caller identity (OAuth2/
OIDC with asymmetrically-signed, short-lived tokens), per-client API keys with rotation, and
managed secrets over TLS. Further hardening deferred here: **separate DB roles** (read-only
for GET paths, a write role only for publish), **security headers**, and **request
payload-size limits**.

---

## 10. Key trade-off for discussion

**MCP-imports-core (in-process)** vs **MCP-as-HTTP-client-of-the-API**. This build uses
shared-core for lowest latency and zero logic duplication; the HTTP-client variant buys
independent deployment/scaling at the cost of a network hop and a second serialization
boundary. Both are defensible; the shared service layer keeps either option open.
