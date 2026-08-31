"""FastAPI app assembly for Learning 360° (l360).

Routes live in l360/routers/* (split 31/08/2026, P3 of the engineering
review); this module owns app creation, middleware, monitoring, and SPA
serving only.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from l360.config import IS_POSTGRES, SENTRY_DSN, assert_secure_config
from l360.db import init_db
from l360.routers import (
    auth_routes,
    billing_routes,
    bookings,
    clients,
    directory,
    educators,
    finance,
    payments_routes,
    public,
    settings,
)

assert_secure_config()

# Error monitoring — inert without the SENTRY_DSN Fly secret (P0-3).
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0, send_default_pii=False)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Creates the SQLite schema for local/dev so `uvicorn l360.api:app` works
    # on a clean checkout. No-op on Postgres — that schema is owned by gated
    # Alembic, never mutated on boot.
    init_db()
    yield


app = FastAPI(title="Learning 360°", lifespan=lifespan)

if not IS_POSTGRES:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


for _r in (auth_routes, directory, clients, educators, settings, billing_routes, bookings, payments_routes, finance, public):
    app.include_router(_r.router)


# --- SPA serving ------------------------------------------------------
_DIST = os.path.join(os.path.dirname(__file__), "web", "dist")

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.middleware("http")
    async def _asset_cache_headers(request, call_next):
        response = await call_next(request)
        # Vite content-hashes everything under /assets, so those may be
        # cached forever; index.html must NOT be — a home-screen PWA that
        # caches it keeps referencing old CSS/JS across deploys (the iOS
        # date-box fix appeared "not deployed" for exactly this reason).
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/")
    def _index():
        return FileResponse(os.path.join(_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        candidate = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
else:
    @app.get("/")
    def _no_build():
        return JSONResponse(
            {"status": "backend up — React build not present; run the Vite dev server"},
        )
