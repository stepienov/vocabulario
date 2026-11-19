import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin_ui.router import mount_admin
from app.api.v1.account_deletion import router as account_deletion_router
from app.api.v1.admin_logs import router as admin_logs_router
from app.api.v1.auth import me_router, profiles_router, router as auth_router
from app.api.v1.content_reports import router as content_reports_router
from app.api.v1.devices import router as devices_router
from app.api.v1.imports import router as imports_router
from app.api.v1.learning import router as learning_router
from app.api.v1.legal import router as legal_router
from app.api.v1.meta import router as meta_router
from app.api.v1.sync import router as sync_router
from app.core.app_log_middleware import AppLogMiddleware
from app.core.config import get_settings
from app.core.readiness import check_ready, mark_schema_ready
from app.db.base import Base
from app.db.lifecycle import LifecycleBlocked
from app.db.migrations import apply_schema
from app.db.session import engine
from app.public_web.router import mount_public_web
from app import models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    config_errors = settings.deployment_errors()
    if config_errors:
        # Field names only; /health/ready stays 503 until fixed.
        logger.error(
            "invalid settings for environment %r: %s",
            settings.environment,
            ", ".join(config_errors),
        )
    await apply_schema(engine, Base.metadata)
    mark_schema_ready()
    from app.services.account_purge import run_purge_worker
    from app.services.card_jobs import resume_pending_enrichment
    from app.services.import_jobs import resume_unfinished_jobs, start_heartbeat_watchdog
    from app.services.llm_usage import purge_expired_llm_payloads
    from app.services.mail_outbox import run_mail_worker

    await purge_expired_llm_payloads(force=True)

    await resume_unfinished_jobs()
    watchdog = asyncio.create_task(start_heartbeat_watchdog())
    enrich_resume = asyncio.create_task(resume_pending_enrichment())
    mail_worker = asyncio.create_task(run_mail_worker())
    purge_worker = asyncio.create_task(run_purge_worker())
    yield
    from app.services.background import drain_background

    await drain_background(5)
    purge_worker.cancel()
    mail_worker.cancel()
    enrich_resume.cancel()
    watchdog.cancel()
    await asyncio.gather(
        purge_worker, mail_worker, enrich_resume, watchdog, return_exceptions=True
    )
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

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # The default body echoes the submitted input, which on auth routes holds passwords and tokens.
        detail = [
            {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(LifecycleBlocked)
    async def lifecycle_blocked(request: Request, exc: LifecycleBlocked) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "code": "account_deletion_pending",
                    "message": "account_deletion_pending",
                }
            },
        )

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(account_deletion_router, prefix=prefix)
    app.include_router(legal_router, prefix=prefix)
    app.include_router(content_reports_router, prefix=prefix)
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

    mount_admin(app)
    mount_public_web(app)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "environment": settings.environment,
            "persist_words": settings.persist_words,
        }

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready():
        headers = {"Cache-Control": "no-store"}
        if await check_ready():
            return JSONResponse({"status": "ok"}, headers=headers)
        return JSONResponse({"status": "unavailable"}, status_code=503, headers=headers)

    return app


app = create_app()
