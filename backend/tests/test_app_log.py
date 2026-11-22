from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AppLog, LlmUsage
from app.services.app_log import (
    category_for_path,
    is_noisy_get,
    log_event,
    route_template,
    sanitize_payload,
    should_log_http,
)
from app.services.auth_cleanup import purge_diagnostics
from app.services.llm_usage import record_llm_usage


def test_category_for_path():
    assert category_for_path("/api/v1/lookup") == "lookup"
    assert category_for_path("/api/v1/imports/jobs") == "import"
    assert category_for_path("/api/v1/lists") == "lists"
    assert category_for_path("/api/v1/cards/abc/move") == "cards"
    assert category_for_path("/api/v1/me/settings") == "settings"
    assert category_for_path("/api/v1/srs/review") == "srs"
    assert category_for_path("/api/v1/auth/login") == "auth"


def test_noisy_get_skips_polls_but_not_mutations():
    assert is_noisy_get("GET", "/api/v1/lists")
    assert is_noisy_get("GET", "/api/v1/lists/abc/words")
    assert is_noisy_get("GET", "/api/v1/imports/jobs/abc/progress")
    assert not is_noisy_get("POST", "/api/v1/lists")
    assert not is_noisy_get("DELETE", "/api/v1/lists/abc")
    assert not is_noisy_get("POST", "/api/v1/lookup")


def test_should_log_http_errors_and_slow_polls():
    assert should_log_http("GET", "/api/v1/lists", 500, 10)
    assert should_log_http("GET", "/api/v1/lists", 200, 2500)
    assert not should_log_http("GET", "/api/v1/lists", 200, 20)
    assert should_log_http("POST", "/api/v1/lookup", 200, 20)
    assert should_log_http("DELETE", "/api/v1/cards/x", 204, 20)


def test_sanitize_payload_keeps_only_flat_technical_fields():
    out = sanitize_payload(
        {
            "password": "secret",
            "lemma": "el resultado",
            "note": "private",
            "reason": "write_failed",
            "n": 3,
            "nested": {"phase": "x"},
        }
    )
    assert out == {"reason": "write_failed", "n": 3}
    assert sanitize_payload({"lemma": "x"}) is None


def test_route_template_hides_object_ids_only():
    path = f"/api/v1/cards/{uuid4()}/retry-enrichment"
    assert route_template(path) == "/api/v1/cards/{id}/retry-enrichment"
    assert route_template("/api/v1/lookup") == "/api/v1/lookup"


@pytest.mark.pg
async def test_log_event_stores_no_exception_text_or_content(pg):
    typed = "secret-lemma-typed-by-user"
    try:
        raise ValueError(f"bad {typed}")
    except ValueError as exc:
        await log_event(
            level="error",
            category="enrichment",
            event="enrichment_failed",
            message="enrichment failed",
            payload={"lemma": "private", "reason": "x"},
            exc=exc,
        )
    async with pg() as db:
        row = (await db.execute(select(AppLog))).scalar_one()
    assert row.error_type == "ValueError"
    assert row.error_message is None
    assert typed not in (row.traceback or "")
    assert row.payload == {"reason": "x"}


@pytest.mark.pg
async def test_purge_diagnostics_by_age_without_traffic(pg):
    now = now_utc()
    async with pg() as db:
        db.add_all(
            [
                AppLog(level="info", category="http", event="old", created_at=now - timedelta(days=8)),
                AppLog(level="info", category="http", event="fresh", created_at=now - timedelta(days=6)),
                LlmUsage(model="m", purpose="p", created_at=now - timedelta(days=31)),
                LlmUsage(model="m", purpose="p", created_at=now - timedelta(days=29)),
            ]
        )
        await db.commit()
    counts = await purge_diagnostics(now=now)
    assert (counts["app_logs"], counts["llm_usage"]) == (1, 1)
    async with pg() as db:
        assert [r.event for r in (await db.execute(select(AppLog))).scalars()] == ["fresh"]
        assert len((await db.execute(select(LlmUsage))).scalars().all()) == 1


@pytest.mark.pg
async def test_llm_usage_keeps_content_out_by_default(pg, monkeypatch):
    from app.core.config import get_settings
    from app.services.llm_usage import bind_llm_usage_context

    monkeypatch.setattr(get_settings(), "llm_store_payloads", False)
    bind_llm_usage_context(query="private query", lemma="private", pos="noun")
    await record_llm_usage(provider="openai", model="m", purpose="p", request_json={"p": "x"})
    async with pg() as db:
        row = (await db.execute(select(LlmUsage))).scalar_one()
    assert (row.query, row.lemma, row.pos) == (None, None, None)
