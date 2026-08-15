"""Regression: identical gloss_l1 must not steal the same examples."""

from __future__ import annotations

from app.services.enrichment import (
    _merge_examples_into_meanings,
    examples_unique_across_meanings,
)


def test_merge_examples_prefers_index_when_gloss_collides():
    core = {
        "meanings": [
            {"gloss_l1": "lot", "examples": []},
            {"gloss_l1": "lot", "examples": []},
        ]
    }
    payload = {
        "meanings": [
            {
                "gloss_l1": "lot",
                "examples": [
                    {"l2": "Mi vuelo sale a las ocho.", "l1": "a", "cefr": "A2"},
                    {"l2": "El vuelo se retrasó.", "l1": "b", "cefr": "B2"},
                    {"l2": "Cancelaron el vuelo.", "l1": "c", "cefr": "C2"},
                ],
            },
            {
                "gloss_l1": "lot",
                "examples": [
                    {"l2": "El vuelo del águila es majestuoso.", "l1": "d", "cefr": "A2"},
                    {"l2": "Observamos el vuelo de las mariposas.", "l1": "e", "cefr": "B2"},
                    {"l2": "El vuelo libre de las aves fascina.", "l1": "f", "cefr": "C2"},
                ],
            },
        ]
    }
    _merge_examples_into_meanings(core, payload)
    assert core["meanings"][0]["examples"][0]["l2"] == "Mi vuelo sale a las ocho."
    assert core["meanings"][1]["examples"][0]["l2"] == "El vuelo del águila es majestuoso."


def test_examples_unique_across_meanings_rejects_copies():
    payload = {
        "meanings": [
            {
                "examples": [
                    {"l2": "Same sentence.", "l1": "a", "cefr": "A2"},
                    {"l2": "B one.", "l1": "b", "cefr": "B2"},
                    {"l2": "C one.", "l1": "c", "cefr": "C2"},
                ]
            },
            {
                "examples": [
                    {"l2": "Same sentence.", "l1": "a", "cefr": "A2"},
                    {"l2": "B two.", "l1": "b", "cefr": "B2"},
                    {"l2": "C two.", "l1": "c", "cefr": "C2"},
                ]
            },
        ]
    }
    assert not examples_unique_across_meanings(payload, expected=2)


def test_examples_unique_across_meanings_accepts_distinct():
    payload = {
        "meanings": [
            {
                "examples": [
                    {"l2": "A one.", "l1": "a", "cefr": "A2"},
                    {"l2": "B one.", "l1": "b", "cefr": "B2"},
                    {"l2": "C one.", "l1": "c", "cefr": "C2"},
                ]
            },
            {
                "examples": [
                    {"l2": "A two.", "l1": "a", "cefr": "A2"},
                    {"l2": "B two.", "l1": "b", "cefr": "B2"},
                    {"l2": "C two.", "l1": "c", "cefr": "C2"},
                ]
            },
        ]
    }
    assert examples_unique_across_meanings(payload, expected=2)
