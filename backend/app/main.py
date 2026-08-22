"""ReasonFlow API — modular monolith entrypoint (architecture B/C)."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .errors import register_error_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("reasonflow")


def run_migrations():
    import os
    from alembic.config import Config
    from alembic import command

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_cfg_path = os.getenv("ALEMBIC_CONFIG", os.path.join(base_dir, "alembic.ini"))
    if os.path.exists(alembic_cfg_path):
        alembic_cfg = Config(alembic_cfg_path)
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
        command.upgrade(alembic_cfg, "head")
    else:
        Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    if settings.seed_on_boot:
        from .seed.seed import run_seed

        run_seed()
    if settings.is_sqlite:
        log.warning("UNEXPECTED STORE: SQLite is TEST-ONLY — runtime/demo must run on PostgreSQL 16+pgvector (docker compose up)")
    if not settings.redis_url:
        log.warning("DEGRADED STATE: REDIS_URL not set — in-process cache/event fallbacks active")
    if not (settings.openai_api_key or settings.embedding_api_key):
        log.info("DETERMINISTIC MODE: no AI provider credentials — LLM stages will run deterministic templates")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.3.0-s1", lifespan=lifespan)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    from .routers import audit, auth, contracts, decisions, health, investigations, kpis, reconcile, scenarios

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(contracts.router, prefix=settings.api_prefix)
    app.include_router(scenarios.router, prefix=settings.api_prefix)
    app.include_router(kpis.router, prefix=settings.api_prefix)
    app.include_router(reconcile.router, prefix=settings.api_prefix)
    app.include_router(investigations.router, prefix=settings.api_prefix)
    app.include_router(audit.router, prefix=settings.api_prefix)
    app.include_router(decisions.router, prefix=settings.api_prefix)
    from .routers import learning as learning_router
    app.include_router(learning_router.router, prefix=settings.api_prefix)
    app.include_router(learning_router.mem_router, prefix=settings.api_prefix)
    from .routers import aigov as aigov_router
    app.include_router(aigov_router.router, prefix=settings.api_prefix)

    @app.get("/")
    def root():
        return {"app": settings.app_name, "api": settings.api_prefix, "docs": "/docs"}

    return app


app = create_app()
