"""Structured logging, request IDs, and Prometheus metrics."""

from __future__ import annotations

import time
import uuid

import structlog
from kpi_perf_summary_core.config import get_settings
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def configure_logging() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), get_settings().log_level, 20)
        ),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )


log = structlog.get_logger()

REQUEST_COUNT = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "path"])


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Attaches a request id, logs each request, and records RED metrics."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        # Use the route template (not the raw path) to keep metric cardinality low.
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(request.method, path, "500").inc()
            log.exception("request_failed", method=request.method, path=path)
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        elapsed = time.perf_counter() - start
        REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        response.headers["x-request-id"] = request_id
        log.info(
            "request",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 1),
        )
        return response
