"""Unit tests for import-job helpers (no live DB)."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.import_classify import _vocabulario_lemma
from app.services.import_jobs import (
    _apply_lemma_verify,
    _apply_vocab_item,
    _finalize_analyze_verdicts,
    _import_invalid_reason_code,
    _plain_import_headword,
    format_error_lemmas,
)
from app.services.import_package import load_text_import


def _item(**kwargs):
    base = dict(
        ordinal=0,
        raw_note=["casa", "dom"],
        input_label="casa | dom",
        verdict="pending",
        verdict_phase=None,
        reason_code=None,
        reason_detail=None,
        lemma=None,
        pos=None,
        gloss=None,
        entry_kind=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_format_error_lemmas_semicolon_space():
    items = [
        _item(ordinal=2, verdict="failed", lemma="gamma", input_label="g"),
        _item(ordinal=0, verdict="failed", lemma=None, input_label="alpha"),
        _item(ordinal=1, verdict="ready", lemma="beta", input_label="b"),
        _item(ordinal=3, verdict="failed", lemma="delta", input_label="d"),
    ]
    assert format_error_lemmas(items) == "alpha; gamma; delta"


def test_format_error_lemmas_empty():
    assert format_error_lemmas([_item(verdict="ready", lemma="x")]) == ""


def test_apply_vocab_item_ready_pending():
    item = _item()
    _apply_vocab_item(
        item,
        {
            "valid": True,
            "headword_l2": "la casa",
            "gloss_l1": "dom",
            "entry_kind": "lemma",
            "pos": "noun",
            "input": "casa | dom",
        },
        "es",
    )
    assert item.verdict == "pending"
    assert item.lemma == "la casa"
    assert item.gloss == "dom"


def test_apply_vocab_item_phrase_keeps_headword():
    item = _item()
    _apply_vocab_item(
        item,
        {
            "valid": True,
            "headword_l2": "tener prisa",
            "entry_kind": "phrase",
            "base_lemma": None,
        },
        "es",
    )
    assert item.verdict == "pending"
    assert item.lemma == "tener prisa"
    assert item.entry_kind == "phrase"
    assert item.pos == "phrase"


def test_apply_vocab_item_construction_keeps_headword():
    item = _item()
    _apply_vocab_item(
        item,
        {
            "valid": True,
            "headword_l2": "volver a hacer algo",
            "entry_kind": "construction",
            "base_lemma": None,
        },
        "es",
    )
    assert item.verdict == "pending"
    assert item.lemma == "volver a hacer algo"
    assert item.entry_kind == "construction"
    assert item.pos == "construction"


def test_apply_vocab_item_llm_invalid():
    item = _item(input_label="???", raw_note=["???"])
    _apply_vocab_item(
        item,
        {"valid": False, "headword_l2": "???", "invalid_reason": "garbage"},
        "es",
    )
    assert item.verdict == "failed"
    assert item.reason_code == "llm_invalid"
    assert item.reason_detail == "garbage"


def test_plain_import_headword_rejects_numbers_and_junk():
    assert _plain_import_headword("el 123456") is None
    assert _plain_import_headword("123456") is None
    assert _plain_import_headword("XXXX$%&%·") is None
    assert _plain_import_headword("???") is None
    assert _plain_import_headword("ppppppppp") is None
    assert _plain_import_headword("la ppppppppp") is None
    assert _plain_import_headword("el perro") == "el perro"
    assert _plain_import_headword("evaluar") == "evaluar"
    assert _plain_import_headword("el medio ambiente") == "el medio ambiente"
    assert _plain_import_headword("(com)portarse") == "(com)portarse"
    assert _plain_import_headword("tener prisa") == "tener prisa"
    assert _plain_import_headword("volver a hacer algo") == "volver a hacer algo"


def test_apply_vocab_item_rejects_number_even_if_llm_valid():
    item = _item(input_label="123456", raw_note=["123456"])
    _apply_vocab_item(
        item,
        {"valid": True, "headword_l2": "el 123456", "entry_kind": "lemma", "pos": "noun"},
        "es",
    )
    assert item.verdict == "failed"
    assert item.reason_code == "llm_invalid"


def test_apply_vocab_item_rejects_repeated_letters_even_if_llm_adds_article():
    item = _item(input_label="ppppppppp", raw_note=["ppppppppp"])
    _apply_vocab_item(
        item,
        {"valid": True, "headword_l2": "la ppppppppp", "entry_kind": "lemma", "pos": "noun"},
        "es",
    )
    assert item.verdict == "failed"
    assert item.reason_code == "llm_invalid"


def test_apply_vocab_item_rejects_symbol_junk():
    item = _item(input_label="XXXX$%&%·", raw_note=["XXXX$%&%·"])
    _apply_vocab_item(item, {"valid": False, "headword_l2": "XXXX$%&%·"}, "es")
    assert item.verdict == "failed"
    assert item.reason_code == "llm_invalid"


def test_apply_vocab_item_rejects_plain_word_on_l1_mismatch():
    item = _item(input_label="evaluar", raw_note=["evaluar"])
    _apply_vocab_item(
        item,
        {
            "valid": False,
            "headword_l2": "evaluar",
            "invalid_reason": "Treść jest po hiszpańsku (L1), a brakuje hasła po francusku (L2).",
        },
        "fr",
    )
    assert item.verdict == "failed"
    assert item.reason_code == "not_learning_lang"
    assert item.lemma == "evaluar"


def test_apply_vocab_item_construction_wrong_language_stays_failed():
    item = _item(input_label="volver a hacer algo", raw_note=["volver a hacer algo"])
    _apply_vocab_item(
        item,
        {
            "valid": False,
            "headword_l2": "volver a hacer algo",
            "entry_kind": "construction",
            "invalid_reason": "not a headword in the language you’re learning",
        },
        "en",
    )
    assert item.verdict == "failed"
    assert item.reason_code == "not_learning_lang"
    assert item.entry_kind != "lemma"


def test_import_prompts_gate_non_l2():
    from app.ai.prompts.v1 import (
        IMPORT_ADAPTIVE_PROMPT_V1,
        IMPORT_CLASSIFY_PROMPT_V1,
        IMPORT_VERIFY_LEMMAS_PROMPT_V1,
    )

    assert "innym języku" in IMPORT_CLASSIFY_PROMPT_V1
    assert "valid=true tylko gdy to L2" in IMPORT_CLASSIFY_PROMPT_V1
    assert "NOT in the learning language" in IMPORT_VERIFY_LEMMAS_PROMPT_V1
    assert "NIE tłumacz hasła" in IMPORT_ADAPTIVE_PROMPT_V1
    assert "example.l2 TYLKO w L2" in IMPORT_ADAPTIVE_PROMPT_V1


def test_admin_user_rejects_plain_user():
    import asyncio

    import pytest
    from fastapi import HTTPException

    from app.core.deps import get_admin_user

    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_admin_user(SimpleNamespace(role="user")))
    assert exc.value.status_code == 403


def test_import_invalid_reason_code_splits_language_from_junk():
    assert _import_invalid_reason_code("nie jest w języku nauki") == "not_learning_lang"
    assert _import_invalid_reason_code("NOT in the learning language") == "not_learning_lang"
    assert _import_invalid_reason_code("garbage / keyboard smash") == "llm_invalid"
    assert _import_invalid_reason_code(None) == "llm_invalid"


def test_apply_lemma_verify_rejects_wrong_language():
    items = [
        _item(verdict="ready", lemma="pająk"),
        _item(verdict="ready", lemma="casa"),
    ]
    _apply_lemma_verify(
        items,
        {"invalid": [{"index": 0, "reason": "real word but not in the learning language"}]},
    )
    assert items[0].verdict == "failed"
    assert items[0].reason_code == "not_learning_lang"
    assert items[1].verdict == "ready"


def test_apply_lemma_verify_rejects_listed_indexes():
    items = [
        _item(verdict="ready", lemma="casa"),
        _item(verdict="ready", lemma="la ppppppppp"),
        _item(verdict="ready", lemma="perro"),
    ]
    _apply_lemma_verify(items, {"invalid": [{"index": 1, "reason": "not a word"}]})
    assert items[0].verdict == "ready"
    assert items[1].verdict == "failed"
    assert items[1].reason_code == "llm_invalid"
    assert items[2].verdict == "ready"


def test_finalize_pending_with_lemma_becomes_ready():
    items = [
        _item(verdict="ready", lemma="casa"),
        _item(verdict="pending", lemma="perro", input_label="perro"),
        _item(verdict="pending", lemma=None, input_label="???"),
        _item(verdict="duplicate", lemma="gato"),
    ]
    _finalize_analyze_verdicts(items)
    assert items[0].verdict == "ready"
    assert items[1].verdict == "ready"
    assert items[2].verdict == "failed"
    assert items[2].reason_code == "no_lemma"
    assert items[3].verdict == "duplicate"


def test_comma_word_list_is_plain_notes():
    text = (
        "evaluar, fomentar, gestionar, influir, lograr, mantener, mejorar, "
        "prevenir, proponer, reconocer, resolver, superar, el artículo, "
        "el comienzo, el negocio, la alfombra, la oportunidad, la elección, "
        "el sueño, el empleado, la energía, el medio ambiente, la fábrica, "
        "el vuelo, la máquina, el pasajero, el proyecto, la razón, "
        "el resultado, la carretera, el servicio, la habilidad, la asignatura"
    )
    deck = load_text_import(text)
    assert deck.kind == "plain"
    assert deck.needs_format_analysis is False
    assert len(deck.notes) == 33
    assert deck.notes[0] == ["evaluar"]
    assert deck.notes[-1] == ["la asignatura"]
    assert deck.notes[21] == ["el medio ambiente"]


def test_quizlet_one_line_not_treated_as_word_list():
    deck = load_text_import("casa, house; perro, dog; gato, cat")
    assert deck.kind != "plain" or len(deck.notes) != 6


def test_vocabulario_lemma_rejects_sentence():
    assert (
        _vocabulario_lemma(
            {"headword_l2": "Tengo prisa porque llego tarde.", "entry_kind": "sentence"},
            learning_lang="es",
        )
        is None
    )


def test_vocabulario_lemma_keeps_phrase_not_base():
    assert (
        _vocabulario_lemma(
            {"headword_l2": "tener prisa", "entry_kind": "phrase", "base_lemma": "tener"},
            learning_lang="es",
        )
        == "tener prisa"
    )
    assert (
        _vocabulario_lemma(
            {"headword_l2": "ir a casa", "entry_kind": "construction", "base_lemma": "ir"},
            learning_lang="es",
        )
        == "ir a casa"
    )


def test_import_commit_content_is_vocabulario_card():
    from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ
    from app.services.card_jobs import build_pending_content

    content = build_pending_content(
        lemma="casa",
        pos="noun",
        gloss="dom",
        learning_lang="es",
        entry_kind="lemma",
    )
    assert content["schema_version"] == "vocabulario.card.v1"
    assert content["pos"] == "noun"
    assert content["pos"] != "imported"
    assert "similar_words" in content
    assert content["similar_words"] == []
    assert MIN_SIMILAR_FOR_QUIZ >= 7


def test_import_commit_construction_uses_adaptive_schema():
    from app.services.card_jobs import build_pending_content, resolve_enrichment_entry_kind

    content = build_pending_content(
        lemma="ir a hacer algo",
        pos="construction",
        gloss="zamierzać coś zrobić",
        learning_lang="es",
        entry_kind="construction",
    )
    assert content["schema_version"] == "vocabulario.adaptive.v1"
    assert content["entry_kind"] == "construction"
    assert content["pos"] == "construction"
    assert resolve_enrichment_entry_kind(content) == "construction"


def test_enrichment_routes_construction_pos_without_entry_kind():
    from app.services.card_jobs import resolve_enrichment_entry_kind

    stale_import = {
        "schema_version": "vocabulario.card.v1",
        "lemma": "ir a hacer algo",
        "pos": "construction",
        "meanings": [{"gloss_l1": "zamierzać coś zrobić", "examples": []}],
    }
    assert resolve_enrichment_entry_kind(stale_import) == "construction"
    assert resolve_enrichment_entry_kind({"lemma": "casa"}, pos="noun") == "lemma"
    assert (
        resolve_enrichment_entry_kind(
            {"entry_kind": "lemma", "pos": "phrase", "lemma": "pagar a plazos"},
        )
        == "lemma"
    )


def test_skips_similar_words_never_by_pos():
    from app.services.similar_words import skips_similar_words

    assert not skips_similar_words({"entry_kind": "construction"}, "construction")
    assert not skips_similar_words({"schema_version": "vocabulario.adaptive.v1"}, "verb")
    assert not skips_similar_words({"pos": "phrase"}, None)
    assert not skips_similar_words({"pos": "noun"}, "noun")


def test_ensure_similar_words_fetches_for_construction(monkeypatch):
    import asyncio

    from app.services import similar_words as sw

    async def fake_fetch(*args, **kwargs):
        return [{"lemma": f"ir a x{i}", "pos": "construction", "gloss_l1": f"g{i}"} for i in range(12)]

    monkeypatch.setattr(sw, "fetch_similar_words", fake_fetch)
    profile = SimpleNamespace(app_lang="pl", learning_lang="en")
    content = asyncio.run(
        sw.ensure_similar_words(
            {"schema_version": "vocabulario.adaptive.v1", "lemma": "ir a hacer algo"},
            profile,
            "ir a hacer algo",
            "construction",
        )
    )
    assert len(content["similar_words"]) == 12
