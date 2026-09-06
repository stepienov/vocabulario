"""Darmowe hasła z Wikisłownika — bez sieci w tescie (gotowe strony)."""

from app.services.dictionary_lookup import (
    assemble_dictionary_candidates,
    parse_en_rest_l2,
    parse_en_translation_lines,
    parse_pl_l2_section,
    parse_pl_translations,
    readings_are_same_sense,
    strip_wiki_text,
)

PL_CASA = """
== casa ({{język angielski}}) ==
{{znaczenia}}
''rzeczownik''
: (1.1) {{rzad}} [[dom]]

== casa ({{język hiszpański}}) ==
{{znaczenia}}
''rzeczownik, rodzaj żeński''
: (1.1) [[dom]]
: (1.2) [[mieszkanie]]
''{{forma czasownika|es}}''
: (2.1) {{forma verbal|czasownik=casar|osoba=trzecia}}
"""

PL_DOM = """
== dom ({{język polski}}) ==
{{znaczenia}}
''rzeczownik, rodzaj męski''
: (1.1) budynek mieszkalny
{{tłumaczenia}}
* hiszpański: (1.1) [[casa]] {{ż}}; (1.2) [[hogar]] {{m}}
* angielski: (1.1) [[house]]
"""

EN_REST_CASA = {
    "es": [
        {
            "partOfSpeech": "Noun",
            "language": "Spanish",
            "definitions": [{"definition": '<a href="/wiki/house">house</a>'}],
        }
    ]
}

EN_HOUSE_TRANS = """
* Spanish: {{tt+|es|casa|f}}, {{t+|es|casalicio|m}}
* Polish: {{t+|pl|dom|m}}
"""

PL_TER = """
== ter ({{język polski}}) ==
{{znaczenia}}
''rzeczownik''
: (1.1) [[oko]]
{{tłumaczenia}}
* hiszpański: (1.1) [[ojo]] {{n}}

== ter ({{język hiszpański}}) ==
{{znaczenia}}
''rzeczownik, rodzaj męski''
: (1.1) [[auto]]
"""

PL_SONAR = """
== sonar ({{język polski}}) ==
{{znaczenia}}
''rzeczownik, rodzaj męski''
: (1.1) hydrolokator
{{tłumaczenia}}
* hiszpański: (1.1) [[sónar]] {{m}}

== sonar ({{język hiszpański}}) ==
{{znaczenia}}
''rzeczownik, rodzaj męski''
: (1.1) [[sonar]]
"""

EN_REST_TER = {
    "es": [
        {
            "partOfSpeech": "Noun",
            "language": "Spanish",
            "definitions": [{"definition": "car"}],
        }
    ],
    "pl": [
        {
            "partOfSpeech": "Noun",
            "language": "Polish",
            "definitions": [{"definition": "eye"}],
        }
    ],
}

EN_REST_SONAR = {
    "es": [
        {
            "partOfSpeech": "Noun",
            "language": "Spanish",
            "definitions": [{"definition": "sonar"}],
        }
    ],
    "pl": [
        {
            "partOfSpeech": "Noun",
            "language": "Polish",
            "definitions": [{"definition": "sonar"}],
        }
    ],
}


def test_strip_html_definition():
    assert strip_wiki_text('<a href="/wiki/house">house</a>') == "house"


def test_parse_pl_spanish_headword_has_polish_gloss_and_skips_verb_form():
    items = parse_pl_l2_section(
        PL_CASA.split("== casa ({{język hiszpański}}) ==")[1],
        lemma="casa",
    )
    assert len(items) == 1
    assert items[0]["pos"] == "noun"
    assert items[0]["gloss"].startswith("dom")
    assert items[0]["gender"] == "f"


def test_parse_pl_translations_to_spanish():
    items = parse_pl_translations(PL_DOM, target_lang="es")
    lemmas = [i["lemma"] for i in items]
    assert "casa" in lemmas
    hogar = next(i for i in items if i["lemma"] == "hogar")
    casa = next(i for i in items if i["lemma"] == "casa")
    assert casa["gender"] == "f"
    assert hogar["gender"] == "m"


def test_en_rest_detects_spanish_noun():
    rows = parse_en_rest_l2(EN_REST_CASA, learning_lang="es")
    assert rows[0]["pos"] == "noun"
    assert rows[0]["gloss"] == "house"


def test_en_translation_templates():
    items = parse_en_translation_lines(EN_HOUSE_TRANS, target_lang="es")
    assert items[0]["lemma"] == "casa"
    assert items[0]["gender"] == "f"


def test_assemble_l2_query_uses_polish_gloss_not_english():
    out = assemble_dictionary_candidates(
        query="casa",
        app_lang="pl",
        learning_lang="es",
        en_rest=EN_REST_CASA,
        app_wikitext=PL_CASA,
        en_translations="",
    )
    assert out
    assert out[0]["lemma"] in {"casa", "la casa"}
    assert "dom" in out[0]["gloss"]
    assert "house" not in out[0]["gloss"]
    assert out[0]["pos"] == "noun"
    assert all(not c.get("reading") for c in out)


def test_assemble_l1_query_returns_spanish_headword():
    out = assemble_dictionary_candidates(
        query="dom",
        app_lang="pl",
        learning_lang="es",
        en_rest={"pl": [{"partOfSpeech": "Noun", "definitions": [{"definition": "house"}]}]},
        app_wikitext=PL_DOM,
        en_translations="",
    )
    lemmas = {c["lemma"] for c in out}
    assert "la casa" in lemmas or "casa" in lemmas
    assert "el hogar" in lemmas
    assert "la hogar" not in lemmas
    assert all(not c.get("reading") for c in out)


def test_assemble_english_ui_uses_translation_subpage():
    out = assemble_dictionary_candidates(
        query="house",
        app_lang="en",
        learning_lang="es",
        en_rest={"en": [{"partOfSpeech": "Noun", "definitions": [{"definition": "building"}]}]},
        app_wikitext="",
        en_translations=EN_HOUSE_TRANS,
    )
    lemmas = {c["lemma"] for c in out}
    assert "la casa" in lemmas or "casa" in lemmas
    assert all(not c.get("reading") for c in out)


def test_same_sense_loanword_collapses_to_one_row():
    learning = {"lemma": "el sónar", "gloss": "sonar", "pos": "noun"}
    native = {"lemma": "el sónar", "gloss": "sonar", "pos": "noun"}
    assert readings_are_same_sense("sonar", learning, native)
    out = assemble_dictionary_candidates(
        query="sonar",
        app_lang="pl",
        learning_lang="es",
        en_rest=EN_REST_SONAR,
        app_wikitext=PL_SONAR,
        en_translations="",
    )
    assert out
    assert all(not c.get("reading") for c in out)
    lemmas = " ".join(c["lemma"] for c in out).casefold()
    assert "sonar" in lemmas or "sónar" in lemmas


def test_different_senses_keep_both_readings():
    out = assemble_dictionary_candidates(
        query="ter",
        app_lang="pl",
        learning_lang="es",
        en_rest=EN_REST_TER,
        app_wikitext=PL_TER,
        en_translations="",
    )
    by_reading = {c.get("reading"): c for c in out}
    assert set(by_reading) == {"learning", "native"}
    assert "ter" in by_reading["learning"]["lemma"].casefold()
    assert "auto" in by_reading["learning"]["gloss"]
    assert "ojo" in by_reading["native"]["lemma"].casefold()
    assert by_reading["native"].get("typed_as") == "ter"
