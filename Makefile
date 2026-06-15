.PHONY: up down clean seed logs test rebuild install test-local dev

# Local Postgres URL used by the uv (non-Docker) targets; override on the CLI, e.g.
#   make test-local KPS_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
KPS_DATABASE_URL ?= postgresql+asyncpg://kps:kps@localhost:5432/kps

# Bring up the full stack (db + api + mcp + frontend). API seeds on first boot.
up:
	docker compose up --build

# Stop and remove containers (keeps the pgdata volume).
down:
	docker compose down

# Wipe everything including the database volume.
clean:
	docker compose down -v

# Re-run the CSV seed against a running stack.
seed:
	docker compose exec api python -m scripts.seed

logs:
	docker compose logs -f api

# Run backend tests (api + mcp) in their images against a throwaway Postgres.
# --no-deps so the app containers run pytest instead of their boot commands; each test
# suite creates its own schema, so only a reachable db is needed.
test:
	docker compose up -d db
	docker compose run --build --rm --no-deps api pytest -q
	docker compose run --build --rm --no-deps mcp pytest -q

rebuild:
	docker compose build --no-cache

# --- Local development with uv (no Docker) -----------------------------------
# uv installs the pinned Python (.python-version) and provisions one shared .venv
# for core + api + mcp (all editable). Run these from the repo root.

# Provision Python + the shared workspace venv.
install:
	uv sync

# Run both backend suites locally against KPS_DATABASE_URL (DB tests skip if no DB).
test-local:
	KPS_DATABASE_URL=$(KPS_DATABASE_URL) uv run pytest -q

# Seed and run the API locally with autoreload (http://localhost:8000/docs).
dev:
	cd apps/api && KPS_DATABASE_URL=$(KPS_DATABASE_URL) uv run python -m scripts.init_db
	cd apps/api && KPS_DATABASE_URL=$(KPS_DATABASE_URL) uv run python -m scripts.seed
	cd apps/api && KPS_DATABASE_URL=$(KPS_DATABASE_URL) uv run uvicorn app.main:app --reload
