"""Tests for self-edit validation."""

from app.services.card_corrections import compute_self_edit_user_changes


def test_compute_self_edit_user_changes_pos():
    before = {"pos": "noun", "notes": "", "meanings": [{"gloss_l1": "house"}]}
    after = {"pos": "verb", "notes": "", "meanings": [{"gloss_l1": "house"}]}
    changes = compute_self_edit_user_changes(before, after)
    assert changes == {"pos": {"from": "noun", "to": "verb"}}


def test_compute_self_edit_user_changes_gloss():
    before = {"meanings": [{"gloss_l1": "house", "examples": [], "usages": []}]}
    after = {"meanings": [{"gloss_l1": "home", "examples": [], "usages": []}]}
    changes = compute_self_edit_user_changes(before, after)
    assert "meanings" in changes
    assert changes["meanings"][0]["gloss_l1"]["to"] == "home"


def test_compute_self_edit_user_changes_empty_when_same():
    content = {"pos": "noun", "notes": "x", "meanings": [{"gloss_l1": "a"}]}
    assert compute_self_edit_user_changes(content, dict(content)) == {}
