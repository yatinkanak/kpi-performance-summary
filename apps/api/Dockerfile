FROM python:3.14-slim

# Bring in the uv binary for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

WORKDIR /app

# Install into the image's system interpreter (no nested venv needed in a container).
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

# Install the shared core package first (local path dependency).
COPY packages/core /core
RUN uv pip install /core

# Install the API adapter.
COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/app /app/app
COPY apps/api/scripts /app/scripts
COPY apps/api/data /app/data
COPY apps/api/tests /app/tests
# Install with [dev] extras so `make test` can run the suite inside this image.
RUN uv pip install ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
