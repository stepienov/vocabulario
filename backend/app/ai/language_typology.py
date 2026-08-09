"""Typologia językowa do promptów AI — wskazówki ogólne, nie kazuistyka per para.

LLM dostaje sygnały: pismo, morfologia, czy w ogóle renderować odmianę itd.
Konkretną strukturę (osoby, czasy, etykiety) zwraca w JSON dla UI.
"""

from __future__ import annotations

# Nazwy w języku angielskim (stabilne w promptach niezależnie od UI użytkownika).
LANG_NAMES_EN: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "hi": "Hindi",
    "tr": "Turkish",
    "nl": "Dutch",
    "pl": "Polish",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
    "he": "Hebrew",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "cs": "Czech",
    "uk": "Ukrainian",
    "sk": "Slovak",
}

# ISO 15924-ish script tags for TTS / UI direction hints.
LANG_SCRIPT: dict[str, str] = {
    "en": "Latn",
    "es": "Latn",
    "fr": "Latn",
    "de": "Latn",
    "it": "Latn",
    "pt": "Latn",
    "nl": "Latn",
    "pl": "Latn",
    "sv": "Latn",
    "no": "Latn",
    "da": "Latn",
    "fi": "Latn",
    "tr": "Latn",
    "id": "Latn",
    "vi": "Latn",
    "cs": "Latn",
    "uk": "Cyrl",
    "ru": "Cyrl",
    "el": "Grek",
    "zh": "Hans",
    "ja": "Jpan",
    "ko": "Kore",
    "ar": "Arab",
    "he": "Hebr",
    "hi": "Deva",
    "th": "Thai",
}

# High-level morphology hints (not exhaustive rules — guidance for the model).
LANG_MORPHOLOGY_HINTS: dict[str, str] = {
    "en": (
        "Limited person conjugation (mostly 3sg -s in present). "
        "Rich tense/aspect auxiliaries (will, have, be + -ing). "
        "No grammatical gender on nouns; articles a/the."
    ),
    "es": (
        "Rich person×tense conjugation (incl. vosotros in European Spanish). "
        "Gendered nouns + articles el/la. Subjunctive mood is productive."
    ),
    "fr": (
        "Rich conjugation; many silent endings — IPA/liaison matter. "
        "Gendered nouns + articles. Passé composé vs imparfait."
    ),
    "de": (
        "Person×tense conjugation; strong/weak verbs. "
        "Four cases (Nom/Acc/Dat/Gen). Gendered nouns + articles."
    ),
    "it": (
        "Rich person×tense conjugation. Gendered nouns + articles. "
        "Passato prossimo vs imperfetto."
    ),
    "pt": (
        "Rich conjugation (European vs Brazilian person sets may differ — prefer learner-standard). "
        "Gendered nouns + articles."
    ),
    "pl": (
        "Rich conjugation + aspect (perfective/imperfective pairs). "
        "Present tense has NO speaker-gender distinction (only past/future compound/conditional). "
        "Perfective verbs have NO present tense — omit czas_terazniejszy, do not use placeholders. "
        "Seven cases on nouns; gendered. No articles."
    ),
    "ru": (
        "Rich conjugation + aspect pairs. Six cases. "
        "Cyrillic script. No articles."
    ),
    "uk": (
        "Rich conjugation + aspect. Cases. Cyrillic. No articles."
    ),
    "cs": (
        "Rich conjugation + aspect. Seven cases. No articles."
    ),
    "ar": (
        "Root-and-pattern morphology; person/gender/number on verbs. "
        "Arabic script, RTL. Definite article ال. Dual number exists."
    ),
    "he": (
        "Root-and-pattern; binyanim. Hebrew script, RTL. Definite ה."
    ),
    "zh": (
        "No conjugation by person/tense — particles and aspect markers (了/过/着). "
        "Han characters. Measure words. Tones (mark in IPA/pinyin when helpful)."
    ),
    "ja": (
        "Agglutinative verb endings (politeness levels). No person agreement. "
        "Kanji/kana. Particles mark case-like roles."
    ),
    "ko": (
        "Agglutinative endings + honorifics. No person agreement like IE languages. Hangul."
    ),
    "hi": (
        "Person/number/gender agreement on verbs; aspect/tense auxiliaries. Devanagari."
    ),
    "tr": (
        "Agglutinative; person suffixes; vowel harmony. No grammatical gender. Latin script."
    ),
    "nl": (
        "Moderate conjugation; gendered/common nouns; articles de/het."
    ),
    "sv": (
        "Limited person inflection; tense forms; definite suffixes on nouns."
    ),
    "no": (
        "Limited person inflection; tense forms; definite suffixes."
    ),
    "da": (
        "Limited person inflection; tense forms; definite suffixes."
    ),
    "fi": (
        "Rich case system (~15); person conjugation on verbs; no articles; agglutination."
    ),
    "el": (
        "Person×tense conjugation; cases; gendered nouns; Greek script."
    ),
    "th": (
        "No conjugation by person/tense — particles and serial verbs. Thai script. Tones."
    ),
    "vi": (
        "No conjugation by person/tense — particles/aspect. Latin script with diacritics. Tones."
    ),
    "id": (
        "Little inflection; affixation (me-/di-/ter-). No conjugation table like IE languages."
    ),
}


def lang_name_en(code: str) -> str:
    c = (code or "").strip().lower()
    return LANG_NAMES_EN.get(c, c or "unknown")


def lang_script(code: str) -> str:
    return LANG_SCRIPT.get((code or "").strip().lower(), "Latn")


def morphology_hint(code: str) -> str:
    c = (code or "").strip().lower()
    return LANG_MORPHOLOGY_HINTS.get(
        c,
        "Infer morphology from your knowledge of this language: "
        "person agreement, tenses/aspect, cases, gender, articles, script.",
    )


def language_pair_guidance(*, native: str, learning: str) -> str:
    """Blok wstrzykiwany do promptów — para L1/L2 + jak sygnalizować UI."""
    n, l = (native or "").strip().lower(), (learning or "").strip().lower()
    return f"""
LANGUAGE PAIR CONTEXT
- L1 (learner's native): {lang_name_en(n)} [{n}], script={lang_script(n)}
- L2 (language being learned): {lang_name_en(l)} [{l}], script={lang_script(l)}
- L2 morphology (guidance, not a rigid checklist): {morphology_hint(l)}
- L1 morphology (for glosses/explanations): {morphology_hint(n)}

ADAPT — do NOT assume Spanish (or any single language) paradigms:
- Headword form: use the dictionary citation form natural for L2
  (infinitive / lemma / dictionary form). Add articles ONLY if L2 dictionaries
  normally list nouns with articles.
- If L2 has little/no person conjugation (e.g. English, Chinese, Thai, Vietnamese,
  Indonesian), do NOT invent Spanish-style yo/tú tables.
- If L2 is highly inflected, provide a useful paradigm for learners.
- Always write L2 text in the correct script for L2; L1 glosses in L1 script.
- RTL scripts (Arabic, Hebrew): still return plain strings; the client handles direction.

UI RENDER SIGNALS (include in JSON when the schema allows `ui_hints`):
{{
  "ui_hints": {{
    "script": "{lang_script(l)}",
    "rtl": {"true" if lang_script(l) in ("Arab", "Hebr") else "false"},
    "show_conjugation": true_or_false,
    "conjugation_kind": "person_tense|agglutinative|aspect_particles|minimal|none",
    "has_articles": true_or_false,
    "has_cases": true_or_false,
    "has_gender": true_or_false,
    "person_order": ["keys in display order"],
    "person_labels": {{"key": "short label in L2 or standard abbr"}},
    "tense_labels": {{"tense_key": "short learner-facing label in L2 or Latin grammatical name"}},
    "non_finite_labels": {{"key": "label"}}
  }}
}}
Set show_conjugation=false and conjugation=null when a paradigm table would not help learners.
""".strip()
