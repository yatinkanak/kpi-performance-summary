# Interview Prep — KPI Performance Summary

One consolidated reference: the elevator pitch, a facts cheat-sheet, the full decision log
(all ADRs), assumptions & tech justification, anticipated Q&A, and likely "extend-it" prompts.

Schema/runtime deep dive: [ARCHITECTURE.md](./ARCHITECTURE.md). Design considerations, securing
reads/MCP, and future improvements are covered in §3–§5 and §8–§9.

---

## 0. 60-second pitch

> A full-stack app that lets time-constrained public investors read top-line KPIs (Revenue,
> Subscribers, ASP, Units Sold) for public companies. The keystone decision: the **REST API and
> the MCP server are two thin adapters over one shared `core` package** — series assembly,
> QoQ/YoY math, and publish are written once, so humans (React SPA) and AI agents (MCP) can
> never see different data. Estimates are stored in an **append-only ledger**; a Postgres view
> returns the latest publish per key, giving a free audit trail. QTD (quarter-to-date) values
> are modeled as a **trajectory** via an `as_of` date, not a single number.

---

## 1. Facts cheat-sheet (know these cold)

| | |
|---|---|
| Companies / Sectors / KPIs | 20 / 20 / 5 |
| Logical series `(company, kpi)` | 100 |
| Rows | ~2,000 = 1,600 historical (16 quarters `2022Q1→2025Q4`) + 400 QTD (4 snapshots) |
| KPIs | ASP ($), Total Revenue ($MM), Global Net Added Subscribers, U.S. Net Added Subscribers, Units Sold |
| QTD snapshots | current quarter `2026Q1` at `as_of` ∈ {Jan 31, Feb 15, Feb 28, Mar 15} |
| Stack | FastAPI · SQLAlchemy 2 async / asyncpg · Postgres 16 · FastMCP · React+TS+Vite+TanStack Query+Recharts · uv · Docker Compose |
| Guardrails | rate limit 120/min · pagination `≤200` · constant-time token · CORS allowlist · structlog + Prometheus |

```
React SPA ─┐                ┌── FastAPI (REST) ─┐
           ├─ HTTP/JSON ────┤                    ├─ kpi_perf_summary_core ─ Postgres
AI agents ─┘                └── FastMCP (tools) ─┘     (shared logic)        (append-only + view)
```

---

## 2. Decision log (all ADRs)

Each: **Decision · Why · Trade-off**. ADR-8 and ADR-10 have standalone deep-dive docs.

**ADR-1 — One shared `core`, two thin adapters.**
REST and MCP both import the same `core.services`. *Why:* logic written once → human and agent
views can't drift. *Trade-off:* adapters are coupled to one library version.

**ADR-2 — MCP imports core in-process (vs MCP as an HTTP client of the API).**
*Why:* lowest latency, zero duplication. *Trade-off:* MCP can't scale/deploy independently; the
shared service layer keeps the HTTP-client option open. (ARCHITECTURE §10 "key trade-off".)

**ADR-3 — Append-only `estimates` ledger + `current_estimates` view (vs mutable rows).**
Publishing inserts, never updates; the view returns the latest publish per key via
`DISTINCT ON … ORDER BY published_at DESC`. *Why:* free, auditable revision history; simple
reads. *Trade-off:* live view recompute cost grows → MATERIALIZED VIEW / `is_current` at scale.

**ADR-4 — `as_of` models QTD as a trajectory.**
QTD accumulates within a quarter, so every snapshot matters. *Why:* historical (`as_of=NULL`)
collapses to latest; each QTD `as_of` stays its own charted point. *Trade-off:* slightly more
query logic to split the two series.

**ADR-5 — `unit` lives on `kpis`, not each estimate.**
Unit is functionally determined by the KPI. *Why:* removes per-row redundancy in the CSV.
*Trade-off:* none material; a join to resolve unit (cheap, 5 rows).

**ADR-6 — PostgreSQL, and tests run on real Postgres (not SQLite).**
*Why:* schema depends on `DISTINCT ON`, partial indexes, native ENUM; SQLite would test a
different DB. *Trade-off:* tests need a reachable Postgres (they skip if none).

**ADR-7 — Only the write path is token-gated (`X-Publish-Token`).**
Constant-time compare; the dev default is rejected in production (fails closed). *Why:* minimal
auth in assignment scope, can't ship a known token. *Trade-off:* no identity/attribution → see
ADR-8.

**ADR-8 — Securing reads (UI) and MCP → sessions + per-client keys.**
A single shared key isn't real security (a browser can't keep a secret; one MCP key isn't
attributable). *Decision:* user session/BFF for the SPA, per-client (ideally OAuth) keys for
MCP. Detail in §8. *Status:* proposed.

**ADR-9 — uv workspace toolchain (local + Docker).**
One `uv sync` provisions pinned Python and a single venv with core + both adapters editable,
locked for reproducibility; Docker images install via uv too. *Why:* fast, reproducible,
monorepo-friendly. *Trade-off:* newer tool; install logic stated in both workspace and
Dockerfiles.

**ADR-10 — Future-improvements roadmap.**
Deferred deliberately: Alembic migrations, materialized/`is_current` current-view, Redis cache,
read replicas + PgBouncer + partitioning, cross-quarter QTD "pace vs prior", OpenTelemetry,
real auth. Detail in §9.

**Other deliberate simplifications.** `fiscal_period` denormalized onto the fact for cheap
labels (derivable from `period_start`); `LIKE` substring search (→ `pg_trgm` for fuzzy);
hand-written frontend types (→ OpenAPI-generated in CI); Redis cache designed-in but optional
at 2k rows.

---

## 3. Assumptions & constraints

- Small, fixed-shape dataset (~2k rows); optimize for clarity, but structure must hold at scale.
- Read-heavy, write-rare (a dashboard with occasional publishes).
- Tickers and KPI names are **stable natural keys** shared by API + MCP.
- Single tenant; **no end-user auth in scope** — only the write path is gated.
- Local/dev is trusted (dev token default, rejected in production).
- "Publish estimates" implies versioned, auditable data → append-only.

---

## 4. Technology choices — justification given constraints

| Choice | Fits because | Trade-off |
|---|---|---|
| **FastAPI (async)** | I/O-bound reads; Pydantic = validation + auto-OpenAPI that types the frontend | overkill if load were trivial |
| **SQLAlchemy 2 async + asyncpg** | one async data layer for both adapters | ORM overhead (negligible) |
| **PostgreSQL** | `DISTINCT ON` latest-publish, partial indexes, ENUM, append-only audit | heavier than SQLite, but SQLite can't model it |
| **Shared `core` package** | write logic once → no drift (keystone) | couples adapters to one version |
| **FastMCP** | standard MCP surface; reuses `core.services` | in-process coupling (ADR-2) |
| **React+Vite+TanStack Query** | read-heavy dashboard: caching/dedup/SWR + shareable URL state | — |
| **Recharts** | simple historical-vs-QTD line charts | less flexible than D3 (not needed) |
| **uv** | installs pinned Python; one workspace venv; reproducible | newer tool |
| **Docker Compose** | one command: db+api+mcp+frontend, seeds on boot | not a prod orchestrator |
| **structlog + Prometheus + slowapi** | JSON logs, RED metrics, IP rate limiting cheaply | slowapi per-process → shared store at scale |

---

## 5. Anticipated Q&A

**Data model**
- *Append-only vs UPDATE?* Immutable rows → auditable revisions and the QTD trajectory is
  preserved; "current" = latest publish per key.
- *How is "current value" computed?* `current_estimates` view: `DISTINCT ON (key) … ORDER BY
  published_at DESC`.
- *Why is `as_of` first-class?* QTD is a trajectory, not one number.
- *Why unit on `kpis`?* Functionally determined by KPI; avoids per-row redundancy.

**Architecture**
- *Why one core, two adapters?* Humans and agents can't see different data.
- *Why in-process MCP, not an HTTP client?* Latency + no duplication; cost is independent
  scaling (ADR-2 / §10).
- *How are QoQ/YoY computed?* In `core.services`, positional lookups vs prior quarter and same
  quarter a year back; reused by MCP.

**Persistence & scale**
- *Why Postgres / not SQLite for tests?* `DISTINCT ON`, partial indexes, ENUM — test what you
  ship.
- *Scale to millions of rows?* Materialized view / `is_current`, partition by `period_start`,
  read replicas + PgBouncer, Redis cache keyed by `as_of`.
- *Search?* `LIKE` substring now → `pg_trgm` GIN for fuzzy later.

**Security**
- *Why only writes secured?* Assignment scope; dev token fails closed in prod.
- *How to secure reads + MCP?* Not a shared key — session/BFF for the SPA, per-client keys for
  MCP (ADR-8).
- *Why constant-time compare?* Avoid leaking the token via timing.

**Ops & tooling**
- *Test isolation?* Per-test transaction rollback (+ savepoints so publish `commit()` is
  contained); collision-proof synthetic fixtures coexist with seed data.
- *What does the uv workspace buy you?* Pinned Python + one locked, editable venv; Docker uses
  uv too.
- *Migrations?* `create_all` now → Alembic for production (ADR-10).
- *Idempotent publish?* Accept an `Idempotency-Key` and de-dup retries (noted, not built).

---

## 6. Likely "extend it" / whiteboard prompts

Interviewers often ask you to evolve the design. Crisp lines to lead with:

- **"Add a new KPI."** Insert a `kpis` row (name + unit); the fact table and series logic are
  KPI-agnostic — no schema change. Unit rides on the KPI.
- **"Secure the reads."** Pivot to ADR-8: user session/BFF for the SPA, per-client keys for MCP;
  don't ship a secret to the browser.
- **"Make the current view fast at 100M rows."** MATERIALIZED VIEW refreshed `CONCURRENTLY` on
  publish (or an `is_current` flag), plus partition `estimates` by `period_start`.
- **"Add cross-quarter QTD pace ('is this quarter ahead of last?')."** Retain QTD snapshots
  across quarters, then add a `pace_vs_prior` field in the summary service (ADR-10).
- **"Deduplicate retried publishes."** `Idempotency-Key` header → unique constraint / lookup.
- **"Who published what?"** Record the principal alongside `published_at` once auth lands —
  the append-only ledger already gives when/what.
- **"Deploy to production."** Alembic migrations, real auth, separate read/write DB roles,
  Redis, replicas, TLS, secrets manager — all in ADR-10.

---

## 7. Talking tips

- **Lead with the keystone** (one core, two adapters) — it explains most other choices.
- **Name the demo↔prod boundary proactively**: append-only ledger, constant-time token, and
  fail-closed prod guard are real; the live view, single shared token, and `create_all` are
  deliberate take-home simplifications with a known upgrade path.
- **Tie every "what's missing" to ADR-10** so gaps read as conscious deferrals, not oversights.
- **Know the numbers** (§1) and the `DISTINCT ON` view — they're the most-probed details.
- **For the security question, don't reach for a shared API key** — that's the trap ADR-8
  exists to avoid.

---

## 8. Securing reads & MCP — detail

**Problem.** Only the write path is gated (`X-Publish-Token`); reads (SPA) and MCP are open.
"One shared API key everywhere" isn't real security: the **browser is a public client** — any
key shipped to it is readable by every visitor (DevTools/bundle) — and a shared key identifies
only *"someone who has the key,"* giving **no attribution and no per-caller revocation**. An MCP
HTTP key is only safe if its holder is trusted (a server-side agent); handed to many end users
it leaks just like the SPA key.

**Possible solutions.**
- **UI — user session / BFF.** User logs in; the backend keeps any real secret server-side and
  gives the browser only a short-lived `httpOnly` cookie (never an API key). Stronger: delegate
  login to an OIDC provider.
- **MCP — per-client keys.** Each client gets its own key (better: a short-lived OAuth token),
  stored server-side, scoped, rotatable, revocable → every call attributable. Local **stdio**
  clients have no network surface, so their trust boundary is local process access.
- **Demo-grade fallback.** A single shared key keeps endpoints from being trivially open, but
  only as explicitly *soft* security — it doesn't protect the SPA and gives no attribution or
  per-caller revocation.

---

## 9. Future improvements — grouped

All deferred deliberately to keep the take-home focused; the app works today. *(QTD =
quarter-to-date; idempotency = a retry has the same effect as one call.)*

- **Data & schema** — retain QTD snapshots across quarters → answer "is this quarter ahead of
  recent ones at the same point?" via a `pace_vs_prior` summary field; confidence intervals /
  revision deltas + alerting when a new snapshot jumps far from the prior estimate.
- **Infra & ops** — Alembic migrations (vs startup `create_all`); materialized / `is_current`
  current-view at scale; Redis cache, PgBouncer (cap DB connections), read replicas, partition
  `estimates` by `period_start`, CDN for the SPA; `Idempotency-Key` on publish + per-client
  rate limits.
- **Product & frontend** — live push (WebSocket/SSE) on new snapshots, watchlists, sector
  rollups; generate the frontend client from OpenAPI in CI so types can't drift.
- **AI / MCP** — expose the KPI catalog as an MCP **resource** (reference data the model just
  reads) rather than only a **tool** (an action it must call) → cheaper, keeps it grounded; an
  **LLM-eval harness** scoring tool-discoverability + answer quality.
- **Observability** — OpenTelemetry traces (API/MCP → DB) to see where time goes; Sentry for
  error aggregation; capture the **who** on each publish (complements existing `published_at`).
- **Security & auth** — OAuth2/OIDC identity, per-client keys with rotation, secrets vault +
  TLS, separate read/write DB roles, security headers + request-size limits (see §8).
