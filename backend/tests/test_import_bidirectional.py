"""Bidirectional flag for preserve import cards."""

from __future__ import annotations

from app.api.v1.learning import _card_queue_direction
from app.services.card_jobs import build_import_display_content


class _Settings:
    practice_direction = "random"


def test_build_content_bidirectional_when_semantics_tagged():
    display = {
        "prompt": {
            "blocks": [
                {"type": "headword", "text": "hablar", "semantic": "headword"},
            ]
        },
        "answer": {
            "blocks": [
                {"type": "gloss", "text": "mówić", "semantic": "translation"},
            ]
        },
        "bidirectional": True,
        "prompt_style": "word",
    }
    content = build_import_display_content(
        lemma="hablar",
        gloss="mówić",
        learning_lang="es",
        display=display,
    )
    assert content["display"]["bidirectional"] is True
    assert content["lemma_l2"] == "hablar"
    assert content["gloss_primary"] == "mówić"
    assert content["meanings"][0]["gloss_l1"] == "mówić"


def test_build_content_forces_false_without_semantics():
    display = {
        "prompt": {"blocks": [{"type": "text", "text": "foo"}]},
        "answer": {"blocks": [{"type": "text", "text": "bar"}]},
        "bidirectional": True,
        "prompt_style": "word",
    }
    content = build_import_display_content(
        lemma="foo",
        gloss="bar",
        learning_lang="es",
        display=display,
    )
    assert content["display"]["bidirectional"] is False


def test_queue_direction_forces_l2_to_l1_when_not_bidirectional():
    content = {
        "schema_version": "import_display.v1",
        "display": {"bidirectional": False},
    }
    assert _card_queue_direction(_Settings(), content) == "l2_to_l1"


def test_queue_direction_allows_settings_when_bidirectional():
    content = {
        "schema_version": "import_display.v1",
        "display": {"bidirectional": True},
    }
    # random settings → either direction ok
    d = _card_queue_direction(_Settings(), content)
    assert d in {"l2_to_l1", "l1_to_l2"}
