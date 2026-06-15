# Contributing — quality gates & CI

How the repo keeps itself green. Backend tooling runs through **uv**; the frontend through
**npm**. See [README.md](./README.md) for setup and [ARCHITECTURE.md](./ARCHITECTURE.md) for design.

## Local commands

```bash
make install      # uv sync — pinned Python + shared venv (core + api + mcp + dev tools)
make lint         # ruff check + ruff format --check   (what CI enforces)
make fmt          # ruff check --fix + ruff format     (auto-fix + format)
make test-local   # pytest (core + api + mcp) against KPS_DATABASE_URL

# Frontend (in ./frontend)
npm ci && npm run build && npm test
```

## Pre-commit hooks (local commit gate)

Config: [`.pre-commit-config.yaml`](./.pre-commit-config.yaml) — ruff (lint + format) plus
hygiene hooks (trailing whitespace, EOF, YAML/TOML/JSON validity, large-file and
private-key guards).

> **First-time setup (per clone, required):** the config file alone does nothing — git hooks
> live in `.git/hooks/` and are **not** cloned, so each developer must install them once:
>
> ```bash
> uvx pre-commit install           # activates hooks on every `git commit` in this clone
> uvx pre-commit run --all-files   # optional: run once over the whole repo now
> ```

You don't have to install them — **CI runs the exact same hooks** (the `quality` job below) on
every push/PR, so the gate is enforced for everyone regardless. Installing locally just gives
you the feedback before you push (and can be bypassed with `git commit --no-verify`).

## CI (GitHub Actions)

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) runs on every push to `main` and on PRs:

- **quality** — `pre-commit run --all-files` (the same hooks as local: ruff lint + format +
  hygiene). This enforces the hooks for everyone, even contributors who didn't `pre-commit install`.
- **backend** — `uv sync --frozen` → `pytest`, with a real **Postgres 16 service** (the
  DB-backed suites need it; SQLite can't model `DISTINCT ON` / partial indexes / native ENUM).
- **frontend** — `npm ci` → `npm run build` (tsc typecheck + vite) → `npm test` (vitest).

## Dependency updates

[`.github/dependabot.yml`](./.github/dependabot.yml) opens weekly, grouped PRs for **uv**
(Python), **npm** (frontend), **github-actions**, and the **Docker** base images — keeping the
lockfiles and images current with minimal noise.

## Linting & formatting config

Configured in the root [`pyproject.toml`](./pyproject.toml) under `[tool.ruff]`: line length
100, target py311, rules `E/F/W/I/UP/B`. FastAPI's `Query/Depends/Header/...` are marked
immutable (so `B008` doesn't false-positive on the dependency-injection idiom), and `UP042` is
ignored to keep the SQLAlchemy-mapped `EstimateType` as `str + Enum`.

## Deliberately deferred (noted, not built for the take-home)

These are the next hardening steps a production repo would add; left out to keep scope focused:

- **Security scanning** — CodeQL (SAST), `pip-audit` / `npm audit` for known CVEs, Trivy for
  Docker-image vulnerabilities, and a secret scanner (gitleaks) in CI.
- **Coverage** — `pytest --cov` + `vitest --coverage` with a threshold gate and a report upload.
- **Frontend lint** — ESLint + Prettier (today the frontend gate is typecheck + tests only).
- **Repo policy** — branch protection requiring green CI + review, signed commits, and a
  CODEOWNERS file.
- **Release** — build/push the API/MCP/frontend images on tags; SBOM generation.
