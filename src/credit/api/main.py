"""FastAPI application wiring."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from zarreh_agentkit.api.health import build_health_router
from zarreh_agentkit.api.middleware import MaxBodySizeMiddleware
from zarreh_agentkit.observability import configure_logging

from credit.api import analyst, applications
from credit.api.deps import READ_LIMIT, limiter, settings

configure_logging(settings.environment)

app = FastAPI(
    title="Credit Decisioning",
    description=(
        "Calibrated credit model, code-derived adverse-action reasons, a mutation-tested "
        "notice verifier and a read-only analyst agent. Portfolio demonstration on the 1994 "
        "UCI German Credit benchmark; not a lender and not legal advice."
    ),
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(MaxBodySizeMiddleware, max_body_bytes=settings.max_request_body_bytes)


@app.middleware("http")
async def correlation_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")
    response.headers["X-Correlation-ID"] = cid
    return response


cors: dict[str, Any] = {
    "allow_origins": settings.frontend_origins,
    "allow_methods": ["GET", "POST"],
    "allow_headers": ["Content-Type"],
}
if settings.environment == "development":
    cors["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
app.add_middleware(CORSMiddleware, **cors)

app.include_router(build_health_router(limiter, READ_LIMIT))
app.include_router(applications.router)
app.include_router(analyst.router)


def _artifact(path: str) -> dict[str, Any]:
    if not Path(path).exists():
        raise HTTPException(503, f"{path} is missing. Run `make train` and `make eval`.")
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return data


@app.get("/evidence", tags=["evidence"])
@limiter.limit(READ_LIMIT)
def evidence(request: Request) -> dict[str, Any]:
    return _artifact(settings.evidence_path)


@app.get("/evidence/verifier", tags=["evidence"])
@limiter.limit(READ_LIMIT)
def verifier_report(request: Request) -> dict[str, Any]:
    return _artifact("artifacts/verifier_report.json")
