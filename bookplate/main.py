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

from . import auth
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
    # A session slid forward gets a fresh cookie too, unless this response already sets or clears it.
    token = getattr(request.state, "renew_session", None)
    if token and not any(c.startswith(f"{auth.COOKIE}=") for c in response.headers.getlist("set-cookie")):
        auth.set_cookie(response, token)
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
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    if exc.status_code == 404:
        return pages.render(request, "not_found.html", status_code=404)
    # Pages are read by people: a refused form (a limit, a too-large file) gets a page, not JSON.
    return pages.render(
        request,
        "not_found.html",
        status_code=exc.status_code,
        heading="That didn't work",
        message=exc.detail,
    )
