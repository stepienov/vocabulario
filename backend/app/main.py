import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin_logs import router as admin_logs_router
from app.api.v1.auth import me_router, profiles_router, router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.imports import router as imports_router
from app.api.v1.learning import router as learning_router
from app.api.v1.meta import router as meta_router
from app.api.v1.sync import router as sync_router
from app.core.app_log_middleware import AppLogMiddleware
from app.core.config import get_settings
from app.db.base import Base
from app.db.migrations import run_migrations
from app.db.session import engine
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_migrations(conn)
    from app.services.card_jobs import resume_pending_enrichment
    from app.services.import_jobs import resume_unfinished_jobs, start_heartbeat_watchdog

    await resume_unfinished_jobs()
    watchdog = asyncio.create_task(start_heartbeat_watchdog())
    enrich_resume = asyncio.create_task(resume_pending_enrichment())
    yield
    enrich_resume.cancel()
    watchdog.cancel()
    await asyncio.gather(enrich_resume, watchdog, return_exceptions=True)
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vocabulario API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(AppLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(me_router, prefix=prefix)
    app.include_router(profiles_router, prefix=prefix)
    app.include_router(learning_router, prefix=prefix)
    app.include_router(imports_router, prefix=prefix)
    app.include_router(meta_router, prefix=prefix)
    app.include_router(sync_router, prefix=prefix)
    app.include_router(devices_router, prefix=prefix)
    app.include_router(admin_logs_router, prefix=prefix)

    if settings.environment == "development":
        from app.api.v1.dev_tools import router as dev_router

        app.include_router(dev_router, prefix=prefix)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "environment": settings.environment,
            "persist_words": settings.persist_words,
        }

    return app


app = create_app()
