"""Task 12: enrich_meanings + enrich_study_finish, gloss lock, callback order."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lsp.enrichment import (
    assemble_meanings_card,
    run_lemma_enrichment,
    _force_locked_glosses,
    _glosses_match_locked,
    _locked_glosses,
)
from app.services.card_jobs import content_is_learnable
from app.services.llm import LLMService


def _profile():
    return SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")


def _similar(n: int = 12) -> list[dict]:
    return [{"lemma": f"w{i}", "pos": "verb", "gloss_l1": f"g{i}"} for i in range(n)]


@pytest.mark.asyncio
async def test_enrich_meanings_and_finish_params(monkeypatch):
    svc = LLMService()
    svc.mock = False
    svc.lookup_model = "gpt-5.6-terra"
    svc.client = MagicMock()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        system = kwargs["messages"][0]["content"]
        if "meanings (glosses) are FIXED" in system:
            content = (
                '{"lemma":"hablar","pos":"verb","ipa":"","headword_note":null,'
                '"meanings":[{"gloss_l1":"mówić","examples":['
                '{"l2":"a","l1":"b","cefr":"A2"},'
                '{"l2":"c","l1":"d","cefr":"B2"},'
                '{"l2":"e","l1":"f","cefr":"C2"}],'
                '"usages":[{"l2":"u","l1":"v"}]}]}'
            )
        else:
            content = '{"lemma":"hablar","pos":"verb","meanings":[{"gloss_l1":"mówić"}]}'
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=None)

    svc.client.chat.completions.create = AsyncMock(side_effect=fake_create)
    profile = _profile()

    await svc.enrich_meanings(profile, "hablar", "verb", "mówić")
    await svc.enrich_study_finish(profile, "hablar", "verb", [{"gloss_l1": "mówić"}])

    assert len(captured) == 2
    m_kwargs, f_kwargs = captured
    assert m_kwargs["model"] == "gpt-5.6-terra"
    assert m_kwargs["reasoning_effort"] == "none"
    assert m_kwargs["max_completion_tokens"] == 800
    assert f_kwargs["model"] == "gpt-5.6-terra"
    assert f_kwargs["reasoning_effort"] == "none"
    assert f_kwargs["max_completion_tokens"] == 2200


def test_gloss_lock_rejects_and_forces():
    locked = ["mówić", "rozmawiać"]
    bad = {
        "meanings": [
            {"gloss_l1": "gadać", "examples": []},
            {"gloss_l1": "rozmawiać", "examples": []},
        ]
    }
    assert not _glosses_match_locked(locked, bad)
    forced = _force_locked_glosses(locked, bad)
    assert _locked_glosses(forced.get("meanings") or []) == locked


def test_assemble_meanings_sets_pending_flags():
    card = assemble_meanings_card(
        _profile(),
        "hablar",
        "verb",
        {"lemma": "hablar", "pos": "verb", "meanings": [{"gloss_l1": "mówić"}]},
    )
    assert card["examples_pending"] is True
    assert card["related_pending"] is True
    assert card["meanings"][0]["examples"] == []
    assert not content_is_learnable(card)


def test_meanings_before_finish_callbacks(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    events: list[str] = []

    async def fake_meanings(llm, profile, lemma, pos, *, gloss_hint=None):
        events.append("meanings_start")
        await asyncio.sleep(0.01)
        events.append("meanings_done")
        return {"lemma": lemma, "pos": pos, "meanings": [{"gloss_l1": "mówić"}]}

    async def fake_finish(llm, profile, lemma, pos, locked_meanings):
        events.append("finish_start")
        assert _locked_glosses(locked_meanings) == ["mówić"]
        await asyncio.sleep(0.02)
        events.append("finish_done")
        return {
            "lemma": lemma,
            "pos": pos,
            "ipa": "x",
            "meanings": [
                {
                    "gloss_l1": "mówić",
                    "examples": [
                        {"l2": "a", "l1": "b", "cefr": "A2"},
                        {"l2": "c", "l1": "d", "cefr": "B2"},
                        {"l2": "e", "l1": "f", "cefr": "C2"},
                    ],
                    "usages": [],
                }
            ],
        }

    async def fake_related(llm, profile, lemma, pos, *, gloss_hint=None):
        await asyncio.sleep(0.005)
        return {
            "synonyms_l2": [],
            "antonyms_l2": [],
            "word_family_l2": [],
            "associations_l2": [],
        }

    async def fake_similar(llm, profile, lemma, pos):
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {"verbs": {"tenses": {"present": {}}}}

    monkeypatch.setattr(enrich_mod, "_fetch_meanings", fake_meanings)
    monkeypatch.setattr(enrich_mod, "_fetch_study_finish", fake_finish)
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    async def on_meanings(card: dict):
        events.append("on_meanings")
        assert card.get("examples_pending") is True
        assert not content_is_learnable(card)

    async def on_study(card: dict):
        events.append("on_study")
        assert "examples_pending" not in card or card.get("examples_pending") is not True
        assert content_is_learnable(card)

    result = asyncio.run(
        run_lemma_enrichment(
            _profile(),
            "hablar",
            "verb",
            on_meanings=on_meanings,
            on_study=on_study,
            require_similar=False,
        )
    )
    assert events.index("on_meanings") < events.index("finish_start")
    assert events.index("on_meanings") < events.index("on_study")
    assert content_is_learnable(result)
    assert "examples_pending" not in result


def test_related_before_meanings_merges_into_on_meanings(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    events: list[str] = []

    async def fake_meanings(llm, profile, lemma, pos, *, gloss_hint=None):
        await asyncio.sleep(0.04)
        return {"lemma": lemma, "pos": "verb", "meanings": [{"gloss_l1": "mówić"}]}

    async def fake_finish(llm, profile, lemma, pos, locked_meanings):
        return {
            "lemma": lemma,
            "pos": pos,
            "meanings": [
                {
                    "gloss_l1": "mówić",
                    "examples": [
                        {"l2": "a", "l1": "b", "cefr": "A2"},
                        {"l2": "c", "l1": "d", "cefr": "B2"},
                        {"l2": "e", "l1": "f", "cefr": "C2"},
                    ],
                    "usages": [],
                }
            ],
        }

    async def fake_related(llm, profile, lemma, pos, *, gloss_hint=None):
        events.append("related_done")
        return {
            "synonyms_l2": [
                {"lemma": "decir", "pos": "verb", "article": None, "gloss_l1": "mówić"}
            ],
            "antonyms_l2": [],
            "word_family_l2": [],
            "associations_l2": [],
        }

    async def fake_similar(llm, profile, lemma, pos):
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {"verbs": {"tenses": {"present": {}}}}

    monkeypatch.setattr(enrich_mod, "_fetch_meanings", fake_meanings)
    monkeypatch.setattr(enrich_mod, "_fetch_study_finish", fake_finish)
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    async def on_meanings(card: dict):
        events.append("on_meanings")
        assert card.get("related_pending") is not True
        assert card.get("synonyms_l2")

    asyncio.run(
        run_lemma_enrichment(
            _profile(),
            "hablar",
            "verb",
            on_meanings=on_meanings,
            require_similar=False,
        )
    )
    assert events.index("related_done") < events.index("on_meanings")
