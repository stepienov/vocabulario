"""Unit tests for enrichment retry backoff."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.card_jobs import (
    STATUS_FAILED,
    STATUS_LEARNABLE,
    STATUS_PREPARATION_PROBLEM,
    STATUS_PREPARING,
    _apply_enrich_retry,
    _clear_enrich_retry,
)


def _card(**kwargs):
    defaults = {
        "id": uuid4(),
        "lemma_l2": "hablar",
        "enrichment_retry_count": 0,
        "enrichment_status": "pending",
        "enrichment_error": None,
        "enrichment_retry_at": None,
        "enrichment_auto_retry_used": False,
        "enrichment_manual_triggered": False,
        "enrichment_side_retries": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_first_fail_schedules_single_auto_retry():
    card = _card()
    before = datetime.now(UTC)
    _apply_enrich_retry(card, RuntimeError("boom"))
    assert card.enrichment_status == STATUS_PREPARING
    assert card.enrichment_auto_retry_used is True
    assert card.enrichment_retry_count == 0
    assert card.enrichment_retry_at >= before + timedelta(minutes=14)


def test_auto_retry_fail_goes_to_prep_problem_without_manual_count():
    card = _card(enrichment_auto_retry_used=True)
    _apply_enrich_retry(card, RuntimeError("boom"))
    assert card.enrichment_status == STATUS_PREPARATION_PROBLEM
    assert card.enrichment_retry_count == 0


def test_manual_fail_increments_and_returns_to_prep_problem():
    card = _card(enrichment_auto_retry_used=True, enrichment_manual_triggered=True)
    _apply_enrich_retry(card, RuntimeError("boom"))
    assert card.enrichment_status == STATUS_PREPARATION_PROBLEM
    assert card.enrichment_retry_count == 1
    assert card.enrichment_manual_triggered is False


def test_third_manual_fail_is_terminal():
    card = _card(
        enrichment_auto_retry_used=True,
        enrichment_manual_triggered=True,
        enrichment_retry_count=2,
    )
    _apply_enrich_retry(card, RuntimeError("boom"))
    assert card.enrichment_status == STATUS_FAILED
    assert card.enrichment_retry_count == 3


def test_learnable_fail_does_not_leave_queue():
    card = _card(enrichment_status=STATUS_LEARNABLE)
    _apply_enrich_retry(card, RuntimeError("inflection_timeout"))
    assert card.enrichment_status == STATUS_LEARNABLE
    assert card.enrichment_retry_at is not None


def test_clear_enrich_retry():
    card = _card(
        enrichment_retry_count=2,
        enrichment_error="x",
        enrichment_retry_at=datetime.now(UTC),
        enrichment_auto_retry_used=True,
        enrichment_manual_triggered=True,
        enrichment_side_retries=2,
    )
    _clear_enrich_retry(card)
    assert card.enrichment_retry_count == 0
    assert card.enrichment_side_retries == 0
    assert card.enrichment_auto_retry_used is False
    assert card.enrichment_manual_triggered is False


def test_learnable_side_retries_stop_after_three():
    card = _card(enrichment_status=STATUS_LEARNABLE, enrichment_side_retries=2)
    _apply_enrich_retry(card, RuntimeError("side_jobs"))
    assert card.enrichment_status == STATUS_LEARNABLE
    assert card.enrichment_side_retries == 3
    assert card.enrichment_retry_at is None
    assert card.enrichment_error


@pytest.mark.pg
async def test_exhausted_learnable_is_not_resumed(pg, monkeypatch):
    from app.services.card_jobs import _apply_enrich_retry, _resume_pending_enrichment
    from tests.pg_factories import create_card, create_profile, create_user

    spawned: list = []
    monkeypatch.setattr(
        "app.services.card_jobs.spawn_enrich", lambda card_id: spawned.append(card_id)
    )
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(
            session, profile, "de repente", "phrase", status=STATUS_LEARNABLE, content={}
        )
        card.enrichment_side_retries = 2
        await session.commit()
        _apply_enrich_retry(card, RuntimeError("side_jobs"))
        await session.commit()
        assert card.enrichment_side_retries == 3
        assert card.enrichment_retry_at is None
        card_id = card.id
    await _resume_pending_enrichment()
    assert card_id not in spawned


@pytest.mark.pg
async def test_unchanged_learnable_retry_keeps_updated_at(pg, monkeypatch):
    from app.models import LearningCard
    from app.services.background import drain_background
    from app.services.card_jobs import _persist_enrichment_result
    from tests.pg_factories import create_card, create_profile, create_user

    events: list[str] = []
    notified: list = []

    async def capture(**kwargs):
        events.append(kwargs.get("event"))

    async def notify(*args, **kwargs):
        notified.append(args)

    async def same_family(db, profile, content, entry):
        return content

    monkeypatch.setattr("app.services.card_jobs.log_event", capture)
    monkeypatch.setattr("app.services.push.notify_cards_ready", notify)
    monkeypatch.setattr("app.services.card_jobs.sync_word_family", same_family)
    content = {
        "lemma": "hablar",
        "pos": "verb",
        "language": "es",
        "meanings": [{"gloss_l1": "mówić", "examples": [{"l2": "Hablo.", "l1": "Mówię."}]}],
        "similar_words": [],
    }
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(
            session,
            profile,
            "hablar",
            "verb",
            status=STATUS_LEARNABLE,
            content=content,
        )
        await session.commit()
        before = card.updated_at
        card_id = card.id
        await _persist_enrichment_result(
            session, card, profile, dict(content), entry=None, notified=False
        )
        await drain_background(2)
    async with pg() as session:
        stored = await session.get(LearningCard, card_id)
    assert stored is not None
    assert stored.updated_at == before
    assert stored.enrichment_side_retries == 1
    assert stored.enrichment_status == STATUS_LEARNABLE
    assert notified == []
    assert "enrich_side_retry" in events
    assert "enrich_ready" not in events


@pytest.mark.pg
async def test_get_card_enrichment_active_follows_claim(pg, pg_client):
    from app.services.card_jobs import STATUS_FAILED, _claimed
    from tests.pg_factories import auth_headers, create_card, create_profile, create_user

    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(
            session,
            profile,
            "mesa",
            "noun",
            status=STATUS_FAILED,
            content={"lemma": "mesa"},
        )
        await session.commit()
        headers = auth_headers(user)
        card_id = card.id
        profile_id = profile.id
    url = f"/api/v1/cards/{card_id}?profile_id={profile_id}"
    _claimed.add(card_id)
    active = await pg_client.get(url, headers=headers)
    assert active.status_code == 200
    assert active.json()["enrichment_active"] is True
    _claimed.discard(card_id)
    idle = await pg_client.get(url, headers=headers)
    assert idle.status_code == 200
    assert idle.json()["enrichment_active"] is False
