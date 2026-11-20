"""Fixture testów na lokalnym Postgresie.

Adres musi być ustawiony, zanim jakikolwiek test zaimportuje `app`:
`app.db.session.engine` powstaje przy imporcie z `get_settings()`.

Bez bazy testy `pg` są pomijane. `REQUIRE_PG_TESTS=1` (CI) zamienia każdy
brak bazy, brak wybranych testów `pg` i pominięty test `pg` w błąd.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# asyncio.run() w starszych testach zamyka pętlę Proactora. Następne połączenie
# asyncpg dostaje wtedy „Event loop is closed”. Selector tego nie robi.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_REQUIRE_ENV = "REQUIRE_PG_TESTS"
_schema_ready = False
_pg_skip_reason: str | None = None
_pg_required = False
_pg_not_run: list[str] = []


def _require_flag() -> bool:
    value = os.environ.get(_REQUIRE_ENV, "").strip().lower()
    if value in {"", "0", "false", "no"}:
        return False
    if value in {"1", "true", "yes"}:
        return True
    pytest.exit(f"{_REQUIRE_ENV} must be 1 or 0, got {value!r}.", returncode=4)


def _url_from_dotenv() -> str | None:
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "TEST_DATABASE_URL":
            return value.strip().strip('"').strip("'") or None
    return None


def _configured_test_url() -> str | None:
    if "TEST_DATABASE_URL" in os.environ:
        return os.environ["TEST_DATABASE_URL"].strip() or None
    return _url_from_dotenv()


def _guard_test_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    database = parsed.path.lstrip("/").split("/", 1)[0]
    if host in _LOCAL_HOSTS and database.endswith("_test"):
        return
    pytest.exit(
        "TEST_DATABASE_URL must use a local host (localhost, 127.0.0.1, ::1) "
        f"and a database name ending in _test (host={host!r}, database={database!r}).",
        returncode=3,
    )


_test_url = _configured_test_url()


async def _ping(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


def pytest_configure(config: pytest.Config) -> None:
    global _pg_skip_reason, _pg_required
    _pg_required = _require_flag()
    if not _test_url:
        _pg_skip_reason = "TEST_DATABASE_URL is not set"
    else:
        _guard_test_url(_test_url)
        os.environ["DATABASE_URL"] = _test_url
        try:
            asyncio.run(_ping(_test_url))
        except Exception as exc:
            _pg_skip_reason = f"TEST_DATABASE_URL connection failed: {type(exc).__name__}"
    if _pg_required and _pg_skip_reason is not None:
        pytest.exit(
            f"{_REQUIRE_ENV}=1 but PostgreSQL tests cannot run: {_pg_skip_reason}.",
            returncode=3,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _pg_skip_reason is None:
        return
    skip = pytest.mark.skip(reason=_pg_skip_reason)
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)


def pytest_collection_finish(session: pytest.Session) -> None:
    if _pg_required and not any("pg" in item.keywords for item in session.items):
        pytest.exit(f"{_REQUIRE_ENV}=1 but no tests marked pg were selected.", returncode=3)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.skipped and "pg" in report.keywords and report.nodeid not in _pg_not_run:
        _pg_not_run.append(report.nodeid)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _pg_required and _pg_not_run and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter) -> None:
    if not _pg_not_run:
        return
    if _pg_required:
        terminalreporter.section("required PostgreSQL tests did not pass", red=True)
        for nodeid in _pg_not_run:
            terminalreporter.line(f"SKIPPED/XFAIL {nodeid}")
        return
    terminalreporter.write_line(
        f"{len(_pg_not_run)} PostgreSQL tests (marker pg) skipped: "
        f"{_pg_skip_reason or 'skipped by the test'}. They did not verify the database.",
        yellow=True,
    )


async def _prepare_engine():
    global _schema_ready

    from app import models  # noqa: F401
    from app.core.config import get_settings
    from app.db import session as db_session
    from app.db.base import Base
    from app.db.migrations import apply_schema

    engine = create_async_engine(get_settings().database_url, echo=False)
    # Rebind istniejącej fabryki — moduły typu card_jobs trzymają import
    # `from app.db.session import async_session_factory` z czasu załadowania.
    db_session.engine = engine
    db_session.async_session_factory.configure(bind=engine)
    factory = db_session.async_session_factory
    if not _schema_ready:
        await apply_schema(engine, Base.metadata)
        _schema_ready = True
    return engine, factory


@pytest.fixture
async def pg():
    from app.db.base import Base

    engine, factory = await _prepare_engine()
    names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield factory
    try:
        try:
            from app.services import background
        except ImportError:
            background = None
        if background is not None and hasattr(background, "drain_background"):
            await background.drain_background(1)
        from app.services import card_jobs, lookup_category_jobs, lookup_jobs

        card_jobs._claimed.clear()
        lookup_jobs._inflight.clear()
        lookup_category_jobs._inflight.clear()
    finally:
        await engine.dispose()


@pytest.fixture
async def pg_client(pg):
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
