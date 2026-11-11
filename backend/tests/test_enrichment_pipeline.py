"""Pipeline enrichment: parallel side-jobs, learnable vs complete, POS retry."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ
from app.lsp.enrichment import (
    assemble_core_card,
    finish_side_jobs,
    has_required_inflection,
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


def test_assemble_normalizes_stem_change_note():
    core = _core_payload("pensar", "verb")
    core["headword_note"] = "e:ie"
    card = assemble_core_card(_profile(), "pensar", "verb", core)
    assert card["headword_note"] == "(e>ie)"


def test_assemble_drops_regular_headword_note():
    core = _core_payload()
    core["headword_note"] = "regular"
    card = assemble_core_card(_profile(), "hablar", "verb", core)
    assert card["headword_note"] is None


def test_content_complete_phrase_needs_inflection_and_similar():
    content = {
        "schema_version": "vocabulario.card.v1",
        "entry_kind": "lemma",
        "lemma": "pagar a plazos",
        "language": "es",
        "pos": "phrase",
        "meanings": [{"gloss_l1": "płacić na raty", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": [],
        "conjugation": {"presente": {"yo": "pago a plazos"}},
    }
    assert not content_is_complete(content)
    content["similar_words"] = _similar(MIN_SIMILAR_FOR_QUIZ)
    for item in content["similar_words"]:
        item["pos"] = "phrase"
    assert content_is_complete(content)


def test_content_complete_noun_phrase_with_article_without_inflection():
    """la/el + rzeczownik: LSP nie odmienia — karta jest gotowa bez koniugacji."""
    content = {
        "schema_version": "vocabulario.card.v1",
        "entry_kind": "lemma",
        "lemma": "la red social",
        "language": "es",
        "pos": "phrase",
        "meanings": [
            {
                "gloss_l1": "sieć społecznościowa",
                "examples": [{"l2": "Uso una red social.", "l1": "Używam sieci.", "cefr": "A2"}],
            }
        ],
        "similar_words": [
            {"lemma": f"la red {i}", "pos": "phrase", "gloss_l1": f"g{i}"}
            for i in range(MIN_SIMILAR_FOR_QUIZ)
        ],
        "conjugation": None,
        "inflection": None,
    }
    assert content_is_learnable(content)
    assert content_is_complete(content)
    assert _entry_has_paid_content(SimpleNamespace(content=content))


def test_content_complete_verbal_phrase_without_article_needs_inflection():
    content = {
        "schema_version": "vocabulario.card.v1",
        "entry_kind": "lemma",
        "lemma": "pagar a plazos",
        "language": "es",
        "pos": "phrase",
        "meanings": [{"gloss_l1": "płacić na raty", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": [],
        "conjugation": None,
        "inflection": None,
    }
    assert content_is_learnable(content)
    assert not content_is_complete(content)


def test_content_complete_verb_needs_inflection_and_similar():
    content = {
        "schema_version": "vocabulario.card.v1",
        "pos": "verb",
        "meanings": [{"gloss_l1": "mówić", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(MIN_SIMILAR_FOR_QUIZ),
        "conjugation": {"present": ["hablo"]},
    }
    assert content_is_complete(content)


def test_content_complete_noun_needs_noun_forms_not_verb_tenses():
    content = {
        "schema_version": "vocabulario.card.v1",
        "lemma": "la botella",
        "language": "es",
        "pos": "noun",
        "meanings": [{"gloss_l1": "butelka", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(MIN_SIMILAR_FOR_QUIZ),
        "inflection": {
            "verbs": None,
            "nouns": {"singular": "el correo electrónico", "plural": "los correos electrónicos"},
            "adjectives": None,
        },
    }
    assert content_is_complete(content, learning_lang="es")
    content["inflection"] = {"verbs": None, "nouns": None, "adjectives": None}
    assert not content_is_complete(content, learning_lang="es")


def test_content_complete_adj_needs_adjective_forms():
    content = {
        "schema_version": "vocabulario.card.v1",
        "lemma": "cariñoso",
        "language": "es",
        "pos": "adj",
        "meanings": [{"gloss_l1": "czuły", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(MIN_SIMILAR_FOR_QUIZ),
        "inflection": {
            "verbs": None,
            "nouns": None,
            "adjectives": {"forms": {"m_sg": "cariñoso"}},
        },
    }
    assert content_is_complete(content, learning_lang="es")


def test_assemble_keeps_spanish_noun_article_when_llm_returns_stem():
    core = _core_payload(lemma="cerrajero", pos="noun")
    card = assemble_core_card(_profile(), "el cerrajero", "noun", core)
    assert card["lemma"] == "el cerrajero"


def test_assemble_promotes_article_from_llm_when_lookup_is_bare():
    core = _core_payload(lemma="el cerrajero", pos="noun")
    card = assemble_core_card(_profile(), "cerrajero", "noun", core)
    assert card["lemma"] == "el cerrajero"


def test_guard_keeps_article_when_llm_returns_stem():
    from types import SimpleNamespace

    from app.services.card_jobs import _guard_enrichment_lemma

    card = SimpleNamespace(lemma_l2="el cerrajero", pos="noun")
    pinned = _guard_enrichment_lemma(
        card,
        {
            "schema_version": "vocabulario.card.v1",
            "lemma": "cerrajero",
            "pos": "noun",
            "language": "es",
        },
    )
    assert pinned["lemma"] == "el cerrajero"


def test_select_live_card_treats_article_variant_as_same_word():
    from types import SimpleNamespace

    from app.services.word_lists import select_live_card_for_lemma

    existing = SimpleNamespace(lemma_l2="el cerrajero", pos="noun")
    assert select_live_card_for_lemma([existing], "cerrajero", "noun") is existing
    assert select_live_card_for_lemma([existing], "el cerrajero", "noun") is existing
    assert select_live_card_for_lemma([existing], "cerrajero", "verb") is None


def test_assemble_core_keeps_lookup_lemma_not_translation():
    core = _core_payload(lemma="do something gradually", pos="verb")
    card = assemble_core_card(_profile(), "ir haciendo algo", "construction", core)
    assert card["lemma"] == "ir haciendo algo"
    assert card["pos"] == "construction"
    assert card["entry_kind"] == "lemma"


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


async def _fake_related(llm, profile, lemma, pos, *, gloss_hint=None):
    return {
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "associations_l2": [],
    }


def test_run_lemma_enrichment_fetches_similar_for_construction(monkeypatch):
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
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", _fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    asyncio.run(
        run_lemma_enrichment(
            _profile(), "ir a hacer algo", "construction", require_similar=True
        )
    )
    assert similar_calls == ["construction"]


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
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", _fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    async def on_study(card: dict):
        order.append("on_study")
        assert content_is_learnable(card)
        assert card["similar_words"] == []

    async def run():
        return await run_lemma_enrichment(
            _profile(),
            "hablar",
            "verb",
            on_study=on_study,
            require_similar=False,
        )

    result = asyncio.run(run())
    assert "on_study" in order
    assert order.index("on_study") < order.index("similar_done")
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
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", _fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    asyncio.run(
        run_lemma_enrichment(_profile(), "play", "noun", require_similar=False)
    )
    assert "noun" in similar_calls
    assert "verb" in similar_calls


def test_has_required_inflection_treats_null_forms_as_missing():
    empty = {"verbs": {"tenses": None, "non_finite": None}}
    assert has_required_inflection(
        {"inflection": empty}, pos="phrase", lemma="de repente", learning_lang="es"
    ) is False
    assert has_required_inflection(
        {"inflection": empty, "inflection_status": "not_applicable"},
        pos="phrase",
        lemma="de repente",
        learning_lang="es",
    ) is True
    assert has_required_inflection(
        {}, pos="phrase", lemma="la red social", learning_lang="es"
    ) is True
    assert has_required_inflection(
        {"inflection": empty}, pos="verb", lemma="enviar", learning_lang="es"
    ) is False


def _phrase_shell(lemma: str, pos: str = "phrase") -> dict:
    return {
        "lemma": lemma,
        "pos": pos,
        "language": "es",
        "meanings": [{"gloss_l1": "nagle", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(),
        "inflection": {"verbs": {"tenses": None, "non_finite": None}},
    }


def test_finish_side_jobs_calls_model_for_null_inflection(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    calls: list[str] = []

    async def fake_infl(llm, profile, lemma, pos):
        calls.append(lemma)
        return {"verbs": {"tenses": None, "non_finite": None}}

    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)
    result = asyncio.run(finish_side_jobs(_profile(), _phrase_shell("de repente"), llm=object()))
    assert calls == ["de repente"]
    assert result["inflection_status"] == "not_applicable"
    assert result["inflection"] is None
    assert result["conjugation"] is None


def test_finish_side_jobs_keeps_phrase_open_when_inflection_fails(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    async def fake_infl(llm, profile, lemma, pos):
        raise RuntimeError("model down")

    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)
    result = asyncio.run(finish_side_jobs(_profile(), _phrase_shell("de repente"), llm=object()))
    assert "inflection_status" not in result


def test_empty_verb_inflection_is_not_marked_inapplicable(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    async def fake_infl(llm, profile, lemma, pos):
        return {"verbs": {"tenses": None, "non_finite": None}}

    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)
    result = asyncio.run(
        finish_side_jobs(_profile(), _phrase_shell("enviar", pos="verb"), llm=object())
    )
    assert result.get("inflection_status") != "not_applicable"


def test_run_lemma_marks_empty_phrase_not_applicable(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        return _core_payload(lemma=lemma, pos="phrase")

    async def fake_similar(llm, profile, lemma, pos):
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {}

    async def fake_fill(llm, core, lang):
        return None

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", _fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)
    monkeypatch.setattr(
        "app.services.related_articles.fill_related_articles_on_core", fake_fill
    )
    result = asyncio.run(
        run_lemma_enrichment(
            _profile(), "de repente", "phrase", require_similar=False
        )
    )
    assert result["inflection_status"] == "not_applicable"
    assert result["inflection"] is None


def test_related_pending_blocks_complete():
    content = {
        "schema_version": "vocabulario.card.v1",
        "pos": "verb",
        "lemma": "hablar",
        "language": "es",
        "meanings": [{"gloss_l1": "mówić", "examples": [{"l2": "a", "l1": "b"}]}],
        "similar_words": _similar(),
        "inflection": {"verbs": {"tenses": {"present": {}}}},
        "related_pending": True,
    }
    assert content_is_learnable(content)
    assert not content_is_complete(content, learning_lang="es")
    content.pop("related_pending")
    assert content_is_complete(content, learning_lang="es")


def test_related_before_study_merges_without_pending(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    events: list[str] = []

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        await asyncio.sleep(0.05)
        return _core_payload()

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

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    async def on_study(card: dict):
        events.append("on_study")
        assert card.get("related_pending") is not True
        assert card.get("synonyms_l2")

    result = asyncio.run(
        run_lemma_enrichment(
            _profile(), "hablar", "verb", on_study=on_study, require_similar=False
        )
    )
    assert events.index("related_done") < events.index("on_study")
    assert "related_pending" not in result or result.get("related_pending") is not True
    assert result["synonyms_l2"]


def test_related_failure_keeps_pending(monkeypatch):
    from app.lsp import enrichment as enrich_mod

    async def fake_core(llm, profile, lemma, pos, *, gloss_hint=None):
        return _core_payload()

    async def fake_related(llm, profile, lemma, pos, *, gloss_hint=None):
        raise RuntimeError("related down")

    async def fake_similar(llm, profile, lemma, pos):
        return _similar()

    async def fake_infl(llm, profile, lemma, pos):
        return {"verbs": {"tenses": {"present": {}}}}

    monkeypatch.setattr(enrich_mod, "_fetch_core_with_examples", fake_core)
    monkeypatch.setattr(enrich_mod, "_fetch_related_part", fake_related)
    monkeypatch.setattr(enrich_mod, "fetch_similar_words", fake_similar)
    monkeypatch.setattr(enrich_mod, "fetch_lsp_inflection", fake_infl)

    result = asyncio.run(
        run_lemma_enrichment(_profile(), "hablar", "verb", require_similar=False)
    )
    assert result.get("related_pending") is True
    assert content_is_learnable(result)
    assert not content_is_complete(result, learning_lang="es")
