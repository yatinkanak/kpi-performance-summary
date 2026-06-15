FROM python:3.14-slim

# Bring in the uv binary for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

WORKDIR /app

# Install into the image's system interpreter (no nested venv needed in a container).
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY packages/core /core
RUN uv pip install /core

COPY apps/mcp/pyproject.toml /app/pyproject.toml
COPY apps/mcp/server.py /app/server.py
COPY apps/mcp/tests /app/tests
# Install with [dev] extras so `make test` can run the suite inside this image.
RUN uv pip install ".[dev]"

EXPOSE 8765
CMD ["python", "server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
