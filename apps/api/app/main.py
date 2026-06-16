"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from kpi_perf_summary_core.config import get_settings
from kpi_perf_summary_core.repositories import NotFoundError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import companies, estimates, favorites, health, kpis, search
from app.observability import ObservabilityMiddleware, configure_logging

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="KPI Performance Summary API",
        version="0.1.0",
        description="Top-line KPI estimates (historical + QTD) for public companies.",
    )

    app.state.limiter = limiter
    # SlowAPIMiddleware is what actually enforces the limiter's default_limits globally;
    # without it the limiter and its 429 handler are inert.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # ----- exception handlers (domain errors -> clean HTTP) --------------
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _bad_request(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    # ----- routes --------------------------------------------------------
    api = "/api/v1"
    app.include_router(health.router)
    app.include_router(search.router, prefix=api, tags=["search"])
    app.include_router(kpis.router, prefix=api, tags=["kpis"])
    app.include_router(companies.router, prefix=api, tags=["companies"])
    app.include_router(favorites.router, prefix=api, tags=["favorites"])
    app.include_router(estimates.router, prefix=api, tags=["estimates"])

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
