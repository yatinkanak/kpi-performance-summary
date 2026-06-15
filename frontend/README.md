# Frontend — React + TypeScript SPA (`frontend`)

The web client for time-constrained investors: browse companies by sector, see an
at-a-glance KPI summary, and drill into a historical-vs-QTD chart with date filtering
and CSV export. Talks to the FastAPI backend over JSON.

> System-wide design and rationale: **[../ARCHITECTURE.md](../ARCHITECTURE.md)**.

## Stack

- **Vite** + **React 18** + **TypeScript** (strict)
- **TanStack Query** — server-state caching, dedup, stale-while-revalidate
- **React Router** — routing + URL-driven filter state
- **Recharts** — the historical/QTD line chart

## Structure

```
frontend/src/
├── main.tsx              # bootstraps QueryClient + Router
├── App.tsx               # top bar (brand + search) and routes
├── api/client.ts         # typed API client + TanStack Query hooks + exportUrl()
├── lib/format.ts         # value/percent formatting, +/- color helpers
├── components/
│   ├── SearchBar.tsx     # debounced global search (sectors / companies / KPIs)
│   └── KpiChart.tsx      # Recharts: historical (solid) + QTD trajectory (dashed)
└── pages/
    ├── Dashboard.tsx     # sector filter + company grid
    ├── CompanyDetail.tsx # summary cards: latest value, QoQ %, YoY %, QTD as-of
    └── KpiDetail.tsx     # chart + date-range filter (URL-driven) + CSV export
```

## Routes

| Path | Page | Notes |
|---|---|---|
| `/` | Dashboard | Filter by sector, click a company to drill in |
| `/company/:ticker` | Company detail | One summary card per KPI; click a card → KPI chart |
| `/company/:ticker/kpi/:kpiId` | KPI detail | Chart + `?from=&to=` date filter + Export CSV |

## Data fetching

`src/api/client.ts` exposes one hook per endpoint — `useSectors`, `useCompanies`,
`useCompany`, `useCompanySummary`, `useKpiSeries`, `useSearch` — plus `exportUrl()` for
the CSV download link. Query keys include all filter params, so each date-range / KPI
view is cached independently and refetched only when inputs change.

Design choices:
- **URL is the source of truth for filters** (`KpiDetail` reads/writes `?from=&to=` via
  `useSearchParams`), so views are bookmarkable and shareable and the back button works.
- **Export reuses the current query params** — the CSV always matches what's on screen.
- The API types in `client.ts` are **hand-written today**; the intended production path is
  to generate them from the backend OpenAPI schema (`openapi-typescript`) so they can't drift.

## Running

### Via Docker (from repo root)

```bash
make up      # frontend at http://localhost:5173 (proxies to api at :8000)
```

### Local (without Docker)

Requires Node 20+ and the backend running (or reachable via `VITE_API_BASE_URL`).

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b + vite build (production bundle in dist/)
npm run preview    # serve the production build locally
```

## Tests

[Vitest](https://vitest.dev) + Testing Library (jsdom), no backend or DB needed:

```bash
npm test           # vitest run (one-shot)
npm run test:watch # watch mode
```

- **`lib/format.test.ts`** — value/percent formatting and +/- color helpers (pure units).
- **`api/client.test.ts`** — `exportUrl()` query-string assembly.
- **`components/SearchBar.test.tsx`** — render + interaction with the data hook mocked
  (groups appear past 2 chars; company link points at `/company/:ticker`; empty groups hide).
- **`components/KpiChart.test.tsx`** — recharts is stubbed (SVG doesn't lay out under jsdom)
  to assert KpiChart's historical+QTD point-merging logic.

Test files live next to the code as `*.test.ts(x)` and are excluded from `tsc -b`/`vite build`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend origin; the client appends `/api/v1` |

Set it in `.env` (repo root, consumed by docker-compose) or `frontend/.env.local` for
local dev. Only `VITE_`-prefixed vars are exposed to the browser bundle — never put
secrets here.

## Notes

- The dev server (`npm run dev`) is used in the container for the take-home; for production,
  `npm run build` and serve `dist/` from a CDN or nginx.
- `tsc -b` runs in `npm run build` and is the type-check gate.
