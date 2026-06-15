# MCP Server — `kpi-summary`

Exposes the KPI data API to AI agents (Claude Desktop, Cursor, etc.). Every tool
delegates to the same `kpi_perf_summary_core` services that power the REST API.

## Tools

| Tool | Purpose |
|---|---|
| `list_sectors()` | Discover sectors and company counts |
| `list_kpis()` | KPI catalog (names + units) |
| `search_companies(query, sector?)` | Resolve a name to a ticker |
| `get_company(ticker)` | Profile + available KPIs + last_updated |
| `get_company_summary(ticker)` | Latest value, QoQ %, YoY %, latest QTD per KPI |
| `get_kpi_series(ticker, kpi, date_from?, date_to?, est_type?)` | Full historical + QTD series |
| `get_qtd(ticker, kpi)` | Latest QTD snapshot + intra-quarter trajectory |
| `compare_companies(tickers[], kpi)` | Cross-company latest-value comparison |

## Connect from an AI client

### Option A — Local (stdio), recommended for Claude Desktop / Cursor

Requires a reachable Postgres (`KPS_DATABASE_URL`) and [**uv**](https://docs.astral.sh/uv/)
(`brew install uv`). uv installs the pinned Python from `.python-version` automatically — no
system Python needed.

The repo is a uv workspace: a single `uv sync` at the **repo root** provisions one shared
`.venv` for the core and both adapters (api + mcp). If you already ran it for the API, it's
done.

```bash
# Provision Python + the shared venv (core + api + mcp, editable)
uv sync
```

The server reads from Postgres, so create the schema + data first with `make dev` (or
`init_db` + `seed`; see [apps/api/README.md](../api/README.md)). To smoke-test the server by
hand, run it from the repo root:

```bash
KPS_DATABASE_URL=postgresql+asyncpg://kps:kps@localhost:5432/kps \
  uv run python apps/mcp/server.py --transport stdio
```

Normally the AI client launches it for you — point the client at the server's absolute path,
using that venv's Python so the dependencies resolve. Add to the client's MCP config (Claude
Desktop:
`claude_desktop_config.json`; Cursor: `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "kpi-summary": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/apps/mcp/server.py", "--transport", "stdio"],
      "env": {
        "KPS_DATABASE_URL": "postgresql+asyncpg://kps:kps@localhost:5432/kps"
      }
    }
  }
}
```

### Option B — HTTP

Run the server over HTTP and point an HTTP-capable MCP client at `http://localhost:8765/mcp`.

Locally (no Docker), from the repo root after `uv sync`:

```bash
KPS_DATABASE_URL=postgresql+asyncpg://kps:kps@localhost:5432/kps \
  uv run python apps/mcp/server.py --transport http --host 0.0.0.0 --port 8765
```

Or via docker-compose — `make up` starts the same server at that URL.

**Connecting a client to the HTTP server:**

- **Cursor** (and other clients that accept a remote URL in their config) — use the `url` form
  directly:

  ```json
  {
    "mcpServers": {
      "kpi-summary": { "url": "http://localhost:8765/mcp" }
    }
  }
  ```

- **Claude Desktop** — `claude_desktop_config.json` launches **stdio servers only**; a bare
  `{ "url": ... }` entry will **not** load. Either:
  1. **Add it in the UI** — Settings → Connectors → *Add custom connector* → URL
     `http://localhost:8765/mcp` (remote MCP connectors require a Pro/Max/Team/Enterprise plan), or
  2. **Bridge stdio → HTTP** in the config file with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote)
     (needs Node):

     ```json
     {
       "mcpServers": {
         "kpi-summary": {
           "command": "npx",
           "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"]
         }
       }
     }
     ```

  For Claude Desktop, **Option A (stdio) is simpler** — it launches the server directly with no
  HTTP server or bridge to keep running.

## Try it

> "What sectors are covered?"
> "Summarize the latest KPIs for IGC."
> "Show me IGC's Total Revenue ($MM) trend for 2024–2025 and the current QTD pace."
> "Compare Total Revenue ($MM) across IGC, STRM, and GAME."

## Tests

`tests/test_tools.py` exercises each tool against real Postgres (output shaping, `est_type`
filtering, the QTD projection, cross-company comparison, and the guiding error messages). The
`mcp_server` fixture points the tools' session factory at a test DB and seeds a deterministic
dataset; tests are **skipped** if no DB is reachable. Run via `make test` (repo root, runs
api + mcp in Docker), or locally with uv: `make test-local` (or `uv run pytest apps/mcp -q`).
