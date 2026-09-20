"""Filtry i hinty rodziny wyrazów."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.ai.language_typology import WORD_FAMILY_HINTS, word_family_guidance
from app.core.lemma_keys import canonical_lemma
from app.ai.prompts.v1 import build_enrichment_core_prompt_parts
from app.lsp.constants import SUPPORTED_L2_LANGS
from app.lsp.enrichment import assemble_core_card
from app.services.word_family_backfill import (
    apply_extra_antonyms,
    build_family_plans,
    prepare_entry,
)
from app.services.word_families import _candidate_items, _head_item, _lift_item_article
from app.services.word_family_quality import (
    belongs_in_family,
    filter_word_family,
    is_lexical_prefix_pair,
    is_negative_prefix_pair,
    is_same_member,
    is_verb_inflection_of,
    member_key,
)


def test_word_family_hints_cover_all_l2():
    missing = SUPPORTED_L2_LANGS - set(WORD_FAMILY_HINTS)
    assert missing == set()
    for code in SUPPORTED_L2_LANGS:
        text = word_family_guidance(code)
        assert code in text
        assert len(text) > 40


def test_enrichment_prompt_has_l2_family_guidance_not_inaguantable():
    static, _dynamic = build_enrichment_core_prompt_parts(
        native="pl",
        learning="es",
        lemma="influir",
        pos="verb",
        cefr="B1",
    )
    assert "inaguantable" not in static
    assert "L2-specific word-family guidance (es)" in static
    assert "libro" in static
    assert "irrelevante" in static
    assert "headword_note" in static
    assert "(e>ie)" in static
    assert "associations_l2" in static
    assert "Skojarzenia" in static


def test_negative_prefix_relevante_irrelevante():
    assert is_negative_prefix_pair("irrelevante", "relevante", "es")
    assert is_negative_prefix_pair("unhappy", "happy", "en")
    assert not is_negative_prefix_pair("influyente", "influir", "es")


def test_lexical_prefix_przepisac():
    assert is_lexical_prefix_pair("przepisać", "pisać", "pl")
    assert not is_lexical_prefix_pair("pisarz", "pisać", "pl")


def test_verb_gerund_english_detected():
    assert is_verb_inflection_of("working", "work", "en")
    assert not is_verb_inflection_of("worker", "work", "en")


def test_filter_moves_irrelevante_to_antonyms():
    family, antonyms = filter_word_family(
        "relevante",
        "adj",
        [
            {"lemma": "irrelevante", "pos": "adj", "gloss_l1": "nieistotny", "article": None},
            {"lemma": "relevancia", "pos": "noun", "gloss_l1": "istotność", "article": "la"},
        ],
        [],
        "es",
    )
    assert [w["lemma"] for w in family] == ["relevancia"]
    assert antonyms[0]["lemma"] == "irrelevante"


def test_filter_drops_headword_and_keeps_other_pos():
    family, _ = filter_word_family(
        "run",
        "verb",
        [
            {"lemma": "run", "pos": "verb", "gloss_l1": "biec"},
            {"lemma": "run", "pos": "noun", "gloss_l1": "bieg"},
        ],
        [],
        "en",
    )
    assert [w["lemma"] for w in family] == ["run"]
    assert family[0]["pos"] == "noun"


def test_belongs_rejects_negative_against_existing_member():
    assert not belongs_in_family(
        "irrelevante",
        "adj",
        [("relevante", "adj")],
        "es",
    )
    assert belongs_in_family(
        "influencia",
        "noun",
        [("influir", "verb")],
        "es",
    )


def _core(lemma, pos, family):
    return {
        "lemma": lemma,
        "pos": pos,
        "ipa": "a",
        "meanings": [
            {
                "gloss_l1": "x",
                "synonyms_l1": [],
                "usages": [],
                "examples": [
                    {"l2": "a", "l1": "a", "cefr": "A2"},
                    {"l2": "b", "l1": "b", "cefr": "B2"},
                    {"l2": "c", "l1": "c", "cefr": "C2"},
                ],
            }
        ],
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": family,
    }


def test_assemble_filters_irrelevante_and_keeps_beyond_ten():
    profile = SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")
    family = [
        {"lemma": "irrelevante", "pos": "adj", "gloss_l1": "nieistotny", "article": None}
    ] + [
        {"lemma": f"rel{i}", "pos": "noun", "article": "la", "gloss_l1": f"g{i}"}
        for i in range(12)
    ]
    card = assemble_core_card(profile, "relevante", "adj", _core("relevante", "adj", family))
    lemmas = [w["lemma"] for w in card["word_family_l2"]]
    assert "irrelevante" not in lemmas
    assert card["antonyms_l2"][0]["lemma"] == "irrelevante"
    assert len(lemmas) == 12


def _prepared(lemma, pos, family, *, antonyms=None, gloss="g"):
    content = {
        "entry_kind": "lemma",
        "lemma": lemma,
        "pos": pos,
        "meanings": [{"gloss_l1": gloss}],
        "word_family_l2": family,
        "antonyms_l2": antonyms or [],
    }
    item = prepare_entry(uuid4(), "pl>es", content, pos)
    assert item is not None
    return item


def _lemmas_on_card(plan, lemma, pos):
    return [
        m["lemma"]
        for m in plan.members
        if not is_same_member(m.get("lemma"), m.get("pos"), lemma, pos)
    ]


def test_backfill_unions_bidirectional_influir_family():
    influir = _prepared(
        "influir",
        "verb",
        [
            {"lemma": "influencia", "pos": "noun", "article": "la", "gloss_l1": "wpływ"},
            {"lemma": "influyente", "pos": "adj", "gloss_l1": "wpływowy"},
            {"lemma": "influenciable", "pos": "adj", "gloss_l1": "podatny"},
        ],
        gloss="wpływać",
    )
    influyente = _prepared(
        "influyente",
        "adj",
        [
            {"lemma": "influir", "pos": "verb", "gloss_l1": "wpływać"},
            {"lemma": "influencia", "pos": "noun", "article": "la", "gloss_l1": "wpływ"},
            {"lemma": "influjo", "pos": "noun", "article": "el", "gloss_l1": "wpływ"},
        ],
        gloss="wpływowy",
    )
    influencia = _prepared(
        "influencia",
        "noun",
        [
            {"lemma": "influir", "pos": "verb", "gloss_l1": "wpływać"},
            {"lemma": "influyente", "pos": "adj", "gloss_l1": "wpływowy"},
            {"lemma": "influido", "pos": "adj", "gloss_l1": "pod wpływem"},
        ],
        gloss="wpływ",
    )
    plans = build_family_plans([influir, influyente, influencia])
    assert len(plans) == 1
    lemmas = {m["lemma"] for m in plans[0].members}
    assert {"influir", "influyente", "influencia", "influenciable", "influjo", "influido"} <= lemmas
    shown_influir = _lemmas_on_card(plans[0], "influir", "verb")
    shown_influyente = _lemmas_on_card(plans[0], "influyente", "adj")
    assert "influir" not in shown_influir
    assert "influyente" in shown_influir
    assert "influencia" in shown_influir
    assert shown_influir != shown_influyente
    assert "influyente" not in shown_influyente
    assert "influir" in shown_influyente


def test_backfill_unions_conversion_objetivo_adj_noun():
    """Adj i rzeczownik tej samej formy — bez wzajemnego wymienienia, wspólne derywaty."""
    adj = _prepared(
        "objetivo",
        "adj",
        [
            {"lemma": "la objetividad", "pos": "noun", "gloss_l1": "obiektywność"},
            {"lemma": "objetivamente", "pos": "adv", "gloss_l1": "obiektywnie"},
            {"lemma": "objetivar", "pos": "verb", "gloss_l1": "obiektywizować"},
            {"lemma": "la objetivación", "pos": "noun", "gloss_l1": "obiektywizacja"},
        ],
        gloss="obiektywny",
    )
    noun = _prepared(
        "el objetivo",
        "noun",
        [
            {"lemma": "objetividad", "pos": "noun", "gloss_l1": "obiektywność"},
            {"lemma": "objetivamente", "pos": "adv", "gloss_l1": "obiektywnie"},
            {"lemma": "objetivar", "pos": "verb", "gloss_l1": "obiektywizować"},
            {"lemma": "objetivación", "pos": "noun", "gloss_l1": "obiektywizacja"},
        ],
        gloss="cel",
    )
    plans = build_family_plans([adj, noun])
    assert len(plans) == 1
    assert len(plans[0].entry_ids) == 2
    shown_adj = _lemmas_on_card(plans[0], "objetivo", "adj")
    shown_noun = _lemmas_on_card(plans[0], "el objetivo", "noun")
    adj_keys = {canonical_lemma(x) for x in shown_adj}
    noun_keys = {canonical_lemma(x) for x in shown_noun}
    assert "objetivo" in adj_keys
    assert "objetivo" in noun_keys
    assert "objetividad" in adj_keys
    assert "objetividad" in noun_keys
    assert "el objetivo" in shown_adj
    assert "objetivo" in shown_noun
    assert "objetivo" not in shown_adj
    assert "el objetivo" not in shown_noun


def test_backfill_unions_conversion_even_with_empty_relatives():
    adj = _prepared("objetivo", "adj", [], gloss="obiektywny")
    noun = _prepared("el objetivo", "noun", [], gloss="cel")
    plans = build_family_plans([adj, noun])
    assert len(plans) == 1
    shown_adj = _lemmas_on_card(plans[0], "objetivo", "adj")
    shown_noun = _lemmas_on_card(plans[0], "el objetivo", "noun")
    assert shown_adj == ["el objetivo"]
    assert shown_noun == ["objetivo"]


def test_backfill_does_not_merge_libro_libre():
    libro = _prepared(
        "libro",
        "noun",
        [
            {"lemma": "libre", "pos": "adj", "gloss_l1": "wolny"},
            {"lemma": "librería", "pos": "noun", "article": "la", "gloss_l1": "księgarnia"},
        ],
    )
    libre = _prepared(
        "libre",
        "adj",
        [
            {"lemma": "libertad", "pos": "noun", "article": "la", "gloss_l1": "wolność"},
            {"lemma": "liberal", "pos": "adj", "gloss_l1": "liberalny"},
        ],
    )
    plans = build_family_plans([libro, libre])
    assert len(plans) == 2
    libro_plan = next(p for p in plans if any(m["lemma"] == "libro" for m in p.members))
    libre_plan = next(p for p in plans if any(m["lemma"] == "libre" for m in p.members))
    libro_lemmas = {m["lemma"] for m in libro_plan.members}
    libre_lemmas = {m["lemma"] for m in libre_plan.members}
    assert "libre" not in libro_lemmas
    assert "libro" not in libre_lemmas
    assert "librería" in libro_lemmas
    assert "libertad" in libre_lemmas


def test_backfill_filters_irrelevante_into_antonyms_when_missing():
    prepared = _prepared(
        "relevante",
        "adj",
        [
            {"lemma": "irrelevante", "pos": "adj", "gloss_l1": "nieistotny"},
            {"lemma": "relevancia", "pos": "noun", "article": "la", "gloss_l1": "istotność"},
        ],
        antonyms=[{"lemma": "trivial", "pos": "adj", "gloss_l1": "błahy"}],
    )
    assert [r["lemma"] for r in prepared.relatives] == ["relevancia"]
    assert prepared.extra_antonyms[0]["lemma"] == "irrelevante"
    plans = build_family_plans([prepared])
    assert len(plans) == 1
    assert {m["lemma"] for m in plans[0].members} == {"relevante", "relevancia"}
    content = {
        "antonyms_l2": [{"lemma": "trivial", "pos": "adj", "gloss_l1": "błahy"}],
    }
    merged = apply_extra_antonyms(content, prepared.extra_antonyms)
    assert [a["lemma"] for a in merged["antonyms_l2"]] == ["trivial", "irrelevante"]
    already = apply_extra_antonyms(
        {"antonyms_l2": [{"lemma": "irrelevante", "pos": "adj", "gloss_l1": "x"}]},
        prepared.extra_antonyms,
    )
    assert [a["lemma"] for a in already["antonyms_l2"]] == ["irrelevante"]


def test_head_item_lifts_article_from_lemma():
    item = _head_item(
        {
            "lemma": "el apunte",
            "pos": "noun",
            "meanings": [{"gloss_l1": "notatka"}],
        },
        learning_lang="es",
    )
    assert item is not None
    assert item["article"] == "el"
    assert item["lemma"] == "apunte"


def test_head_item_does_not_invent_article():
    item = _head_item(
        {
            "lemma": "apunte",
            "pos": "noun",
            "meanings": [{"gloss_l1": "notatka"}],
        },
        learning_lang="es",
    )
    assert item is not None
    assert item["article"] is None
    assert item["lemma"] == "apunte"


def test_candidate_family_lifts_article_from_lemma():
    items = _candidate_items(
        {
            "lemma": "apuntarse",
            "pos": "verb",
            "meanings": [{"gloss_l1": "zapisać się"}],
            "word_family_l2": [
                {"lemma": "el apunte", "pos": "noun", "gloss_l1": "notatka"},
            ],
        },
        learning_lang="es",
    )
    noun = next(i for i in items if i["pos"] == "noun")
    assert noun["article"] == "el"
    assert noun["lemma"] == "apunte"


def test_lift_article_from_lexical_lemma_when_member_is_bare():
    lifted = _lift_item_article(
        {"lemma": "apunte", "pos": "noun", "article": None, "gloss_l1": "notatka"},
        "es",
        extra_lemma="el apunte",
    )
    assert lifted["article"] == "el"
    assert lifted["lemma"] == "apunte"


def test_citation_articles_from_synonym():
    from app.services.word_families import citation_articles_from_content

    found = citation_articles_from_content(
        {
            "lemma": "el progreso",
            "pos": "noun",
            "meanings": [{"gloss_l1": "postęp"}],
            "synonyms_l2": [
                {"lemma": "avance", "pos": "noun", "article": "el", "gloss_l1": "postęp"},
            ],
        },
        "es",
    )
    assert found[member_key("avance", "noun")] == "el"


def test_project_family_hides_noun_missing_article():
    from app.services.word_families import project_family_items

    members = [
        SimpleNamespace(
            lemma="avanzar",
            pos="verb",
            article=None,
            gloss_l1="x",
            rank=0,
            lang_pair="pl>es",
        ),
        SimpleNamespace(
            lemma="avance",
            pos="noun",
            article=None,
            gloss_l1="y",
            rank=1,
            lang_pair="pl>es",
        ),
        SimpleNamespace(
            lemma="casa",
            pos="noun",
            article="la",
            gloss_l1="z",
            rank=2,
            lang_pair="pl>es",
        ),
    ]
    out = project_family_items(members, "avanzado", "adj")
    lemmas = [item["lemma"] for item in out]
    assert "avanzar" in lemmas
    assert "casa" in lemmas
    assert "avance" not in lemmas


def test_project_family_excludes_self_keeps_siblings():
    from app.services.word_families import project_family_items

    members = [
        SimpleNamespace(
            lemma="intermitente",
            pos="adj",
            article=None,
            gloss_l1="przerywany",
            rank=0,
            lang_pair="pl>es",
            lemma_key="intermitente",
        ),
        SimpleNamespace(
            lemma="el intermitente",
            pos="noun",
            article="el",
            gloss_l1="kierunkowskaz",
            rank=1,
            lang_pair="pl>es",
            lemma_key="intermitente",
        ),
        SimpleNamespace(
            lemma="la intermitencia",
            pos="noun",
            article="la",
            gloss_l1="intermitencja",
            rank=2,
            lang_pair="pl>es",
            lemma_key="intermitencia",
        ),
        SimpleNamespace(
            lemma="intermitentemente",
            pos="adv",
            article=None,
            gloss_l1="przerywanie",
            rank=3,
            lang_pair="pl>es",
            lemma_key="intermitentemente",
        ),
    ]
    out = project_family_items(members, "la intermitencia", "noun")
    keys = {member_key(item["lemma"], item["pos"]) for item in out}
    assert member_key("intermitencia", "noun") not in keys
    assert member_key("intermitente", "adj") in keys
    assert member_key("el intermitente", "noun") in keys
    assert member_key("intermitentemente", "adv") in keys


def test_family_json_lists_related_head_for_seed():
    from app.services.word_families import _candidate_items, _keys_of

    keys = _keys_of(
        _candidate_items(
            {
                "lemma": "el intermitente",
                "pos": "noun",
                "word_family_l2": [
                    {"lemma": "intermitente", "pos": "adj", "gloss_l1": "przerywany"},
                    {"lemma": "intermitencia", "pos": "noun", "article": "la", "gloss_l1": "x"},
                    {"lemma": "intermitentemente", "pos": "adv", "gloss_l1": "y"},
                ],
            },
            "es",
        )
    )
    assert member_key("la intermitencia", "noun") in keys
    assert member_key("intermitente", "adj") in keys


def test_lemma_variants_include_article_forms():
    from app.services.word_families import _lemma_variants_for_members

    members = [
        SimpleNamespace(lemma="la intermitencia", lemma_key="intermitencia"),
        SimpleNamespace(lemma="intermitente", lemma_key="intermitente"),
    ]
    variants = _lemma_variants_for_members(members, "es")
    assert "intermitencia" in variants
    assert "la intermitencia" in variants
    assert "el intermitente" in variants
    assert "intermitente" in variants

