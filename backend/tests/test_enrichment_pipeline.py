"""Pipeline enrichment: parallel side-jobs, learnable vs complete, POS retry."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ
from app.lsp.enrichment import (
    assemble_core_card,
    side_jobs_need_retry,
    run_lemma_enrichment,
)
from app.services.card_jobs import (
    STATUS_LEARNABLE,
    STATUS_PREPARING,
    _apply_enrich_retry,
    content_is_complete,
    content_is_learnable,
    _entry_has_paid_content,
)


def _core_payload(lemma="hablar", pos="verb"):
    return {
        "lemma": lemma,
        "pos": pos,
        "ipa": "aˈβlaɾ",
        "meanings": [
            {
                "gloss_l1": "mówić",
                "synonyms_l1": [],
                "usages": [],
                "examples": [
                    {"l2": "Hablo español.", "l1": "Mówię po hiszpańsku.", "cefr": "A2"},
                    {"l2": "Hablamos del tema.", "l1": "Rozmawiamy o temacie.", "cefr": "B2"},
                    {"l2": "No cabe duda.", "l1": "Nie ulega wątpliwości.", "cefr": "C2"},
                ],
            }
        ],
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
    }


def _similar(n: int = 12) -> list[dict]:
    return [{"lemma": f"w{i}", "pos": "verb", "gloss_l1": f"g{i}"} for i in range(n)]


def _profile():
    return SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")


def test_side_jobs_stable_when_pos_matches():
    assert side_jobs_need_retry("hablar", "verb", "hablar", "verb") == (False, False)
    assert side_jobs_need_retry("el gato", "noun", "gato", "noun") == (False, False)


def test_side_jobs_retry_on_pos_change():
    assert side_jobs_need_retry("play", "noun", "play", "verb") == (True, True)


def test_side_jobs_retry_when_lookup_pos_unknown():
    retry_similar, retry_inflection = side_jobs_need_retry("hablar", None, "hablar", "verb")
    assert retry_similar is True
    assert retry_inflection is True


def test_content_is_learnable_without_similar_or_inflection():
    content = {
        "schema_version": "vocabulario.card.v1",
        "pos": "verb",
        "meanings": [{"gloss_l1": "mówić", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": [],
    }
    assert content_is_learnable(content)
    assert not content_is_complete(content)
    assert not _entry_has_paid_content(SimpleNamespace(content=content))


def test_content_complete_verb_needs_inflection_and_similar():
    content = {
        "schema_version": "vocabulario.card.v1",
        "pos": "verb",
        "meanings": [{"gloss_l1": "mówić", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(MIN_SIMILAR_FOR_QUIZ),
        "conjugation": {"present": ["hablo"]},
    }
    assert content_is_complete(content)


def test_assemble_core_keeps_lookup_lemma_not_translation():
    core = _core_payload(lemma="do something gradually", pos="verb")
    card = assemble_core_card(_profile(), "ir haciendo algo", "construction", core)
    assert card["lemma"] == "ir haciendo algo"


def test_guard_pins_lemma_on_lemma_path_and_raises_on_adaptive():
    from app.services.card_jobs import _guard_enrichment_lemma

    lemma_card = SimpleNamespace(lemma_l2="ir haciendo algo", pos="verb")
    pinned = _guard_enrichment_lemma(
        lemma_card,
        {"schema_version": "vocabulario.card.v1", "lemma": "do something gradually", "pos": "verb"},
    )
    assert pinned["lemma"] == "ir haciendo algo"

    adaptive_card = SimpleNamespace(lemma_l2="ir a hacer algo", pos="construction")
    try:
        _guard_enrichment_lemma(
            adaptive_card,
            {
                "schema_version": "vocabulario.adaptive.v1",
                "entry_kind": "construction",
                "lemma": "going to do something",
            },
        )
    except ValueError as exc:
        assert "adaptive_lemma_mismatch" in str(exc)
    else:
        raise AssertionError("expected adaptive_lemma_mismatch")


def test_run_lemma_enrichment_skips_similar_for_construction(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    similar_calls: list[str] = []

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        return _core_payload(lemma=lemma, pos="verb")

    async def fake_similar(llm, profile, lemma, pos):
        similar_calls.append(str(pos))
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {}

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    asyncio.run(
        run_lemma_enrichment(
            _profile(), "ir a hacer algo", "construction", require_similar=True
        )
    )
    assert similar_calls == []


def test_assemble_core_omits_similar_and_inflection():
    card = assemble_core_card(_profile(), "hablar", "verb", _core_payload())
    assert card["lemma"] == "hablar"
    assert card["pos"] == "verb"
    assert card["meanings"]
    assert card["similar_words"] == []
    assert card["inflection"] is None
    assert content_is_learnable(card)
    assert not content_is_complete(card)


def test_learnable_retry_stays_on_queue():
    card = SimpleNamespace(
        id=uuid4(),
        lemma_l2="hablar",
        enrichment_retry_count=0,
        enrichment_status=STATUS_LEARNABLE,
        enrichment_error=None,
        enrichment_retry_at=None,
        enrichment_auto_retry_used=False,
        enrichment_manual_triggered=False,
    )
    _apply_enrich_retry(card, RuntimeError("side_jobs_timeout"))
    assert card.enrichment_status == STATUS_LEARNABLE
    assert card.enrichment_status != STATUS_PREPARING
    assert card.enrichment_retry_at is not None


def test_core_callback_runs_before_slow_similar(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    order: list[str] = []

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        order.append("core_start")
        await asyncio.sleep(0.02)
        order.append("core_done")
        return _core_payload()

    async def fake_similar(llm, profile, lemma, pos):
        order.append("similar_start")
        await asyncio.sleep(0.08)
        order.append("similar_done")
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        order.append("infl_start")
        await asyncio.sleep(0.01)
        order.append("infl_done")
        return {"verbs": {"tenses": {"present": {}}}}

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    async def on_core(card: dict):
        order.append("on_core")
        assert content_is_learnable(card)
        assert card["similar_words"] == []

    async def run():
        return await run_lemma_enrichment(
            _profile(),
            "hablar",
            "verb",
            on_core=on_core,
            require_similar=False,
        )

    result = asyncio.run(run())
    assert "on_core" in order
    assert order.index("on_core") < order.index("similar_done")
    assert "similar_start" in order
    assert "infl_start" in order
    assert len(result.get("similar_words") or []) >= MIN_SIMILAR_FOR_QUIZ


def test_pos_mismatch_refetches_similar(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    similar_calls: list[str] = []

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        return _core_payload(lemma="play", pos="verb")

    async def fake_similar(llm, profile, lemma, pos):
        similar_calls.append(str(pos))
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {"verbs": {"tenses": {"present": {}}}}

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    asyncio.run(
        run_lemma_enrichment(_profile(), "play", "noun", require_similar=False)
    )
    assert "noun" in similar_calls
    assert "verb" in similar_calls
