"""Unit tests for card history / restore helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.card_corrections import _can_restore_event, _diff_summary


def _event(event_type: str, offset_seconds: int = 0):
    return SimpleNamespace(
        id=uuid4(),
        event_type=event_type,
        created_at=datetime(2026, 1, 1, 12, 0, offset_seconds, tzinfo=UTC),
    )


def test_can_restore_pure_self_edit():
    edit = _event("self_edit_applied", 10)
    assert _can_restore_event(edit, [edit]) is True


def test_cannot_restore_after_ai_accepted():
    submitted = _event("correction_submitted", 0)
    accepted = _event("correction_accepted", 5)
    edit = _event("self_edit_applied", 10)
    events = [submitted, accepted, edit]
    assert _can_restore_event(edit, events) is False


def test_can_restore_after_reject_then_self_edit():
    submitted = _event("correction_submitted", 0)
    rejected = _event("correction_rejected", 5)
    edit = _event("self_edit_applied", 10)
    events = [submitted, rejected, edit]
    assert _can_restore_event(edit, events) is True


def test_diff_summary_lemma_gloss():
    before = {"lemma_l2": "hablar", "pos": "verb", "gloss_primary": "mówić"}
    after = {"lemma_l2": "hablár", "pos": "verb", "gloss_primary": "gadać"}
    text = _diff_summary(before, after)
    assert "hablar" in text
    assert "hablár" in text
    assert "mówić" in text
