"""GeMVerify API."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import (
    admin,
    auth,
    bids,
    dashboard,
    documents,
    explanations,
    notifications,
    tenders,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="GeMVerify API",
    version="1.0.0",
    description=(
        "Bid document verification for government e-procurement. "
        "Deterministic verification with an AI explanation layer."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # required: the session travels in an httpOnly cookie
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    """Normalise every error into {detail, code}."""
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        body = exc.detail
    else:
        body = {"detail": str(exc.detail), "code": "ERROR"}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "; ".join(
                f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
            )
            or "Invalid request",
            "code": "VALIDATION_ERROR",
        },
    )


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logging.getLogger("gemverify").info("database ready at %s", settings.DATABASE_URL)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.APP_NAME}


for router in (
    auth.router,
    tenders.router,
    bids.router,
    documents.router,
    notifications.router,
    dashboard.router,
    explanations.router,
    admin.router,
):
    app.include_router(router, prefix=settings.API_PREFIX)
