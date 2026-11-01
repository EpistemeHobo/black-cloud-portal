import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app import config, history  # noqa: F401  -- history registers the change log listener
from app.auth import seed_admin
from app.db import SessionLocal
from app.routers import auth, dashboard, meta, people, systems

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("portal")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Portal starting | environment=%s", config.ENVIRONMENT)
    with SessionLocal() as db:
        seed_admin(db)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Cloud Internal Developer Portal",
    # The API is for the portal's own frontend; no public API docs in production.
    docs_url=None if config.IS_PRODUCTION else "/api/docs",
    redoc_url=None,
    openapi_url=None if config.IS_PRODUCTION else "/api/openapi.json",
)

if config.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)
if config.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )


@app.middleware("http")
async def track_activity(request: Request, call_next):
    # The health check doesn't count as someone using the portal; everything else
    # does. The sleep job (infra/portal_mode) reads this through /api/health.
    if request.url.path != "/api/health":
        meta.last_activity = time.monotonic()
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


for router in (auth.router, dashboard.router, meta.router, people.router, systems.router):
    app.include_router(router)


class FrontendFiles(StaticFiles):
    """Static files, plus one fix for Next.js 16's static export.

    The browser prefetches `__next.system.__PAGE__.txt`, but the export writes it
    as `__next.system/__PAGE__.txt`. Without this, every link prefetch is a 404.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        suffix = ".__PAGE__.txt"
        if response.status_code == 404 and path.endswith(suffix):
            return await super().get_response(path[: -len(suffix)] + "/__PAGE__.txt", scope)
        return response


# The static Next.js site. Mounted last so /api routes win.
if config.FRONTEND_DIR.is_dir():
    app.mount("/", FrontendFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning("No frontend at %s; serving the API only.", config.FRONTEND_DIR)
