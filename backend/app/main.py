from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import me_router, profiles_router, router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.learning import router as learning_router
from app.api.v1.meta import router as meta_router
from app.api.v1.sync import router as sync_router
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
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vocabulario API", version="0.1.0", lifespan=lifespan)
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
    app.include_router(meta_router, prefix=prefix)
    app.include_router(sync_router, prefix=prefix)
    app.include_router(devices_router, prefix=prefix)

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
