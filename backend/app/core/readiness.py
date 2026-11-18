"""Readiness for /health/ready (E-001/F-008/T-002).

Checks only cheap local state: settings, schema applied by this process and a DB ping.
Never calls AI, mail or Google. Failure reasons are logged by category, never values.
"""

import asyncio
import logging

from sqlalchemy import text

from app.core.config import get_settings
from app.db import session as db_session

logger = logging.getLogger(__name__)

DB_TIMEOUT_SECONDS = 1.0
TOTAL_TIMEOUT_SECONDS = 2.0

_schema_ready = False
_last_failure: str | None = None


def mark_schema_ready() -> None:
    global _schema_ready
    _schema_ready = True


async def _ping_db() -> None:
    # Read the engine at call time: tests rebind app.db.session.engine.
    async with db_session.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _failure() -> str | None:
    errors = get_settings().deployment_errors()
    if errors:
        return "config: " + ", ".join(errors)
    if not _schema_ready:
        return "schema not applied"
    try:
        await asyncio.wait_for(_ping_db(), DB_TIMEOUT_SECONDS)
    except TimeoutError:
        return "database timeout"
    except Exception as exc:  # noqa: BLE001 - any driver error means not ready
        return f"database unavailable ({type(exc).__name__})"
    return None


async def check_ready() -> bool:
    global _last_failure
    try:
        failure = await asyncio.wait_for(_failure(), TOTAL_TIMEOUT_SECONDS)
    except TimeoutError:
        failure = "readiness timeout"
    # Log transitions only, so an external monitor polling every minute does not spam logs.
    if failure != _last_failure:
        if failure:
            logger.warning("not ready: %s", failure)
        elif _last_failure:
            logger.info("ready again")
        _last_failure = failure
    return failure is None
