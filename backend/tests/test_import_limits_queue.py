"""Task 11: limity pozycji, daily, bez verify w analizie (atrapy)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.import_jobs import (
    DAILY_IMPORT_LIMIT,
    MAX_IMPORT_ITEMS,
    ImportDailyLimitError,
    ImportTooManyError,
    _position_count,
)


def test_position_count_plain_notes():
    assert _position_count(kind="plain", notes=[["a"], ["b"]], raw_text=None) == 2


def test_position_count_raw_text_blank_lines():
    raw = "casa\n\nperro\n  \ngato\n"
    assert _position_count(kind="raw_text", notes=[], raw_text=raw) == 3


def test_limits_constants():
    assert MAX_IMPORT_ITEMS == 25
    assert DAILY_IMPORT_LIMIT == 25


@pytest.mark.asyncio
async def test_analyze_import_classify_params(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.ai.prompts.v1 import LOOKUP_DRAFT_MODEL
    from app.ai.schemas.import_classify import import_classify_schema
    from app.services.llm import LLMService

    svc = LLMService()
    svc.mock = False
    svc.lookup_model = "gpt-5.6-terra"
    svc.client = MagicMock()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        content = '{"items":[]}'
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=None)

    svc.client.chat.completions.create = AsyncMock(side_effect=fake_create)
    await svc.analyze_import_classify(native="pl", learning="es", notes=[["cerrada"], ["casa"]])
    assert len(captured) == 1
    assert captured[0]["model"] == LOOKUP_DRAFT_MODEL
    assert captured[0]["reasoning_effort"] == "none"
    assert captured[0]["max_completion_tokens"] == 2500
    assert "temperature" not in captured[0]
    assert captured[0]["response_format"]["json_schema"]["schema"] == import_classify_schema()["schema"]
    prompt = captured[0]["messages"][1]["content"]
    assert "adjective masculine singular" in prompt
    assert "Do not copy inflection" in prompt
    assert "Keep full phrases and constructions" in prompt
    assert '[["cerrada"], ["casa"]]' in prompt


def test_import_errors_carry_codes():
    assert str(ImportTooManyError(26)) == "import_too_many"
    assert str(ImportDailyLimitError(25)) == "import_daily_limit"
    assert str(ImportDailyLimitError(20, remaining=5)) == "import_quota_exceeded"
    assert ImportDailyLimitError(20, remaining=5).remaining == 5
    assert ImportTooManyError(26).count == 26


@pytest.mark.pg
async def test_import_nul_and_unselected_items_are_not_errors(pg, monkeypatch):
    from sqlalchemy import select

    from app.models import ImportJobItem
    from app.services import import_jobs
    from tests.pg_factories import create_list, create_profile, create_user

    monkeypatch.setattr(import_jobs, "spawn_job", lambda _id: None)
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        word_list = await create_list(session, profile, "Import")
        job = await import_jobs.create_job_from_text(
            session, user=user, profile=profile, word_list=word_list,
            text="casa\x00\nperro", mode="vocabulario",
        )
        assert "\x00" not in job.input_meta["raw_text"]
        items = (await session.execute(
            select(ImportJobItem).where(ImportJobItem.job_id == job.id).order_by(ImportJobItem.ordinal)
        )).scalars().all()
        for item in items:
            item.verdict = "ready"
        items.append(ImportJobItem(job_id=job.id, ordinal=2, verdict="failed", input_label="???"))
        session.add(items[-1])
        job.status = "review"
        await session.flush()
        await import_jobs.request_commit(session, job, [items[0].id])
        await import_jobs._refresh_counts(job, items)
        assert [item.verdict for item in items] == ["ready", "skipped", "failed"]
        assert job.failed_count == 1
        assert import_jobs.format_error_lemmas(items) == "???"
        items[1].verdict = "failed"
        await import_jobs._refresh_counts(job, items)
        assert job.failed_count == 1


@pytest.mark.asyncio
async def test_import_queue_checks_order_before_cache_hydration(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services import card_jobs

    card_id, profile_id = uuid4(), uuid4()
    gate = AsyncMock(return_value=(False, profile_id, True))
    hydrate = AsyncMock(return_value=True)
    monkeypatch.setattr(card_jobs, "_import_queue_allows", gate)
    monkeypatch.setattr(card_jobs, "_hydrate_before_queue", hydrate)

    await card_jobs._run_claimed_enrich(card_id)

    gate.assert_awaited_once_with(card_id)
    hydrate.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_import_head_advances_queue(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from app.services import card_jobs, import_jobs

    card_id, profile_id = uuid4(), uuid4()
    monkeypatch.setattr(
        card_jobs, "_import_queue_allows", AsyncMock(return_value=(True, profile_id, True))
    )
    hydrate = AsyncMock(return_value=True)
    advance = Mock()
    monkeypatch.setattr(card_jobs, "_hydrate_before_queue", hydrate)
    monkeypatch.setattr(import_jobs, "spawn_next_import_card", advance)

    await card_jobs._run_claimed_enrich(card_id)

    hydrate.assert_awaited_once_with(card_id, None)
    advance.assert_called_once_with(profile_id)


@pytest.mark.pg
async def test_import_queue_gates_cache_before_hydration_on_postgres(pg, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from app.models import ImportJob, ImportJobItem, LearningCard
    from app.services import card_jobs, import_jobs
    from tests.pg_factories import create_card, create_list, create_profile, create_user

    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        word_list = await create_list(session, profile, "Import")
        job = ImportJob(user_id=user.id, profile_id=profile.id, list_id=word_list.id, status="done")
        session.add(job)
        await session.flush()
        first = await create_card(session, profile, "primero", "noun")
        second = await create_card(session, profile, "segundo", "noun")
        first.import_job_id = second.import_job_id = job.id
        session.add_all([
            ImportJobItem(job_id=job.id, ordinal=0, created_card_id=first.id),
            ImportJobItem(job_id=job.id, ordinal=1, created_card_id=second.id),
        ])
        await session.commit()
        first_id, second_id, profile_id = first.id, second.id, profile.id

    hydrate = AsyncMock(return_value=True)
    advance = Mock()
    monkeypatch.setattr(card_jobs, "_hydrate_before_queue", hydrate)
    monkeypatch.setattr(import_jobs, "spawn_next_import_card", advance)

    await card_jobs._run_claimed_enrich(second_id)
    hydrate.assert_not_awaited()
    await card_jobs._run_claimed_enrich(first_id)
    hydrate.assert_awaited_once_with(first_id, None)
    advance.assert_called_once_with(profile_id)

    async with pg() as session:
        first = await session.get(LearningCard, first_id)
        first.enrichment_status = "learnable"
        await session.commit()
    assert await card_jobs._import_queue_allows(first_id) == (True, profile_id, True)
