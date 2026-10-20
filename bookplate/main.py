"""The FastAPI app: routers, static files, migrations on start, request IDs and
one JSON log line per request (lib/log.ts)."""

import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .auth import LoginRequired
from .db import migrate
from .routes import api, pages

log = logging.getLogger("bookplate")
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()  # database changes are applied automatically when a new version starts
    yield


app = FastAPI(title="Bookplate", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(api.router)
app.include_router(pages.router)


@app.middleware("http")
async def request_id(request: Request, call_next):
    """Every request gets an ID (kept from a reverse proxy that sets one), logged with its outcome."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    if not request.url.path.startswith("/static"):
        log.info(
            json.dumps(
                {
                    "event": "http.request",
                    "req": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000),
                }
            )
        )
    return response


@app.exception_handler(LoginRequired)
async def to_login(_: Request, __: LoginRequired):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or exc.status_code != 404:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return pages.render(request, "not_found.html", status_code=404)
