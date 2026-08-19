"""Unit tests for enrichment retry backoff."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.services.card_jobs import (
    STATUS_FAILED,
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


def test_clear_enrich_retry():
    card = _card(
        enrichment_retry_count=2,
        enrichment_error="x",
        enrichment_retry_at=datetime.now(UTC),
        enrichment_auto_retry_used=True,
        enrichment_manual_triggered=True,
    )
    _clear_enrich_retry(card)
    assert card.enrichment_retry_count == 0
    assert card.enrichment_auto_retry_used is False
    assert card.enrichment_manual_triggered is False
