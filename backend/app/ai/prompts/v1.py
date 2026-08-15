"""Wersjonowane prompty AI — zgodnie z PLAN_IMPLEMENTACJI.md sekcja 5."""

from app.ai.language_typology import (
    LANG_NAMES_EN,
    lang_name_en,
    language_pair_guidance,
)

# Alias PL dla kompatybilności (nazwy w promptach PL UI historycznie).
LANG_NAMES_PL: dict[str, str] = {
    "pl": "polski",
    "es": "hiszpański",
    "en": "angielski",
    "de": "niemiecki",
    "fr": "francuski",
    "it": "włoski",
    "pt": "portugalski",
    "uk": "ukraiński",
    "ru": "rosyjski",
    "cs": "czeski",
    "sk": "słowacki",
    "zh": "chiński",
    "ja": "japoński",
    "ko": "koreański",
    "ar": "arabski",
    "hi": "hindi",
    "tr": "turecki",
    "nl": "niderlandzki",
    "sv": "szwedzki",
    "no": "norweski",
    "da": "duński",
    "fi": "fiński",
    "el": "grecki",
    "he": "hebrajski",
    "th": "tajski",
    "vi": "wietnamski",
    "id": "indonezyjski",
}


def lang_name_pl(code: str) -> str:
    c = (code or "").strip().lower()
    return LANG_NAMES_PL.get(c) or LANG_NAMES_EN.get(c) or code


LOOKUP_OUTPUT_FORM_RULES = """
OUTPUT FORM — MANDATORY FOR EVERY CANDIDATE (all languages, all scripts)
The user query may be ANY shape (typo, missing diacritics, plural, conjugated verb,
declined noun, wrong case, mixed alphabet). Your job is to INTERPRET that generously,
but every field you RETURN must be the dictionary citation form — never echo the query.

lemma (always in L2={learning_name}):
- verb → infinitive / citation infinitive for that language
- noun → singular dictionary headword; include definite article when the language uses one
  (Spanish el/la, French le/la, German der/die/das, Italian il/la, Portuguese o/a, …)
- adjective → base citation form (no article)
- other POS → standard dictionary headword for that language

gloss (always in L1={native_name}):
- noun → singular dictionary form (the form on a flashcard back)
- verb → infinitive / canonical citation form for {native_name}
- adjective → base citation form
- fix spelling and diacritics, but NEVER copy the user's inflection, number, case,
  or conjugation from the query string

CRITICAL: interpretation ≠ output. Examples (query → gloss / lemma):
- "libry" (PL plural OR typo OR anything) → gloss "libra", lemma "la libra" — NOT "libry",
  NOT "litry"/"liry" invented to rhyme with the query
- "books" → gloss "book"; "książki" → gloss "książka"; "hablando" → lemma "hablar"
- "Häuser" → lemma "das Haus"; "книги" → singular dictionary forms in both languages
- "食べた" → lemma dictionary citation (e.g. 食べる); gloss L1 infinitive/base form

Never fabricate inflected glosses for unrelated lemmas. Every gloss must be the real
dictionary form of THAT word's translation, in {native_name}.
"""

LOOKUP_SYSTEM_V1 = (
    "Bilingual dictionary lookup. Return ONLY valid L2 headwords as JSON. "
    "INTERPRET the query generously: typos, missing diacritics, plurals, conjugations, "
    "any alphabet — high recall, union all plausible readings. "
    "OUTPUT always dictionary citation forms: lemma = L2 headword, gloss = L1 headword "
    "(singular noun / infinitive verb / base adjective) — never echo the query shape. "
    "If the string fits L1 and L2, return BOTH. JSON only."
)

LOOKUP_PROMPT_V1 = """You are a bilingual lexicographer for ONE language pair.

{pair_guidance}

L1 (app / native language): {native_name}
L2 (learning language — every candidate.lemma MUST be in this language): {learning_name}
CEFR: {cefr}
User query string: "{text}"

Treat the query ONLY as {native_name} and/or {learning_name} (not a third language).

FIRST, INTERPRET THE QUERY (very important — high recall)
- Users type on mobile keyboards and are lazy/careless. Before interpreting:
  - Ignore surrounding and stray punctuation and spaces (commas, periods, quotes,
    e.g. "ksiazka." / " libro , " → "ksiazka" / "libro").
  - Assume diacritics may be MISSING or wrong. A word typed without accents is the
    SAME word: "czesc" = "cześć"/"część", "zubr" = "żubr", "ksiazka" = "książka",
    "gdansk" = "Gdańsk", "nino" = "niño", "cafe" = "café".
  - Assume small typos: transposed letters ("ksaizka"→"książka"), doubled or dropped
    letters, and adjacent-key slips.
  - The query may be an INFLECTED form: plural, conjugated verb, case ending, etc.
    Treat it as a search key pointing to the dictionary headword — not as the form
    to return. "libry" may be plural of "libra", a typo for "libro", or another
    near-miss — consider ALL plausible readings.
  - Works for every script and language in the pair (Latin, Cyrillic, CJK, Arabic, …).

GOAL — HIGH RECALL
Return up to 8 DISTINCT L2 headword proposals the user might plausibly mean.
Build the list as a UNION of ALL plausible interpretations — do NOT stop after the
first one. When unsure whether a candidate belongs, INCLUDE it (extra candidate is
cheap; a missing one breaks the app). Only return [] if nothing is remotely close.

DIACRITIC COMPLETION HAS PRIORITY (this is the #1 source of bugs)
- If stripping diacritics from a real, common word gives EXACTLY the query, that word
  is the primary intent. ALWAYS include its reading, and list it BEFORE looser
  typo-based guesses of a different word.
- Example: L1=Polish query "ksiazka" → "książka" → L2 translation (gloss "książka").
  You may ALSO add "kiszka" (typo reading) AFTER it, but you must NOT omit "książka".

INCLUDE ALL THAT APPLY (each as its own candidate):

1) L2 reading
   - "{text}" is (or is a typo / missing-diacritics form of) a real L2 dictionary headword
     → candidate with that L2 lemma (correct orthography/diacritics) + gloss in L1.
   - Example: L2=Polish, query "brat" → lemma "brat", gloss "brother".
   - Example: L2=Polish, query "brac" → lemma "brać", gloss "to take".

2) L1 reading
   - "{text}" is (or is a typo / missing-diacritics form of) a real L1 word
     → one candidate per distinct L2 translation; gloss = the intended L1 word
       (corrected spelling, WITH diacritics).
   - Example: L1=Polish, L2=Spanish, query "ksiazka" → lemma "libro", gloss "książka".
   - Example: L1=English, query "fart" → L2 translations with gloss "fart".

3) Both at once
   - If the same string is a valid word in L1 AND in L2, return BOTH (1) and (2).
   - Homographs across the pair are common (EN/PL brat, EN/ES red, …).

TYPO / DIACRITICS RULES
- Missing or wrong diacritics NEVER count as an "edit" — treat as the same word.
- On top of that, allow edit distance ≤ 2 and letter transpositions.
- Correct orthography in the OUTPUT fields (lemma / gloss), not by copying the query.
- Do not invent non-words.

{lookup_output_form_rules}

POS FIELD (strict — same for every language pair)
- pos MUST be exactly one English bucket: noun, verb, adj, adv, prep, conj, pron, det, interj
- NEVER localized names (no "sustantivo", "rzeczownik", "verbo", "Nom", …)
- NEVER gender or number in pos (no "masculino", "femenino", "męski", "feminine", …)
- Gender is shown ONLY via the article in lemma (el = masculine, la = feminine, etc.)

DEDUPE & ORDER
- Same headword once per pos bucket. Different POS senses may both appear.
- Order: exact matches, then diacritic-completed matches, then looser typo near-misses.

Return ONLY JSON:
{{
  "candidates": [
    {{"lemma": "...", "pos": "...", "gloss": "..."}}
  ]
}}
"""

LOOKUP_L1_TYPO_PROMPT_V1 = """The user typed an L1 (native) word, most likely WITHOUT
diacritics and/or with a small typo. Recover what they meant. Be high-recall.

{pair_guidance}

L1: {native_name}
L2 (lemmas to return): {learning_name}
Typed string: "{text}"

STEP 1 — interpret the query: ignore stray punctuation/spaces; assume diacritics are
missing or wrong; assume small typos (transposed / doubled / dropped letters,
adjacent-key slips); the query may be plural, conjugated, or otherwise inflected —
treat that as a clue to the headword, not as the form to output.

STEP 2 — find EVERY plausible intended word (L1 and/or L2):
- FIRST and most important: the diacritic-completed word. If adding accents to "{text}"
  yields a real {native_name} word, that is the primary intent — include it FIRST.
  Example: "ksiazka" → "książka"; "zubr" → "żubr"; "czesc" → "cześć"/"część".
- THEN any word within edit distance ≤ 2 or one transposition.
- List MULTIPLE candidate intended words when several are plausible (do not commit to
  only one). Better to offer an extra than to miss the right one.

STEP 3 — for each reading, output L2 translation(s) (max 8 total).

{lookup_output_form_rules}

Also, if "{text}" (or a 1-edit / inflected form) is itself a valid L2 headword,
include that L2 lemma too (in citation form).

POS: exactly noun|verb|adj|adv|prep|conj|pron|det|interj — English only, no gender.

Return ONLY JSON:
{{
  "candidates": [
    {{"lemma": "...", "pos": "...", "gloss": "..."}}
  ]
}}
"""


def lookup_output_form_rules_text(native: str, learning: str) -> str:
    return LOOKUP_OUTPUT_FORM_RULES.format(
        native_name=lang_name_en(native),
        learning_name=lang_name_en(learning),
    )


ENRICHMENT_CORE_PROMPT_V1 = """Jesteś ekspertem leksykograficznym. Tworzysz rdzeń karty słówka (BEZ przykładów zdań, BEZ koniugacji, BEZ similar_words).

{pair_guidance}

Para językowa: L1 (ojczysty) = {native}, L2 (uczony) = {learning}
Lemat (L2): {lemma}
Część mowy: {pos_line}

Zwróć WYŁĄCZNIE JSON:
{{
  "schema_version": "vocabulario.card.v1",
  "lemma": "słowo w L2",
  "language": "{learning}",
  "pos": "noun|verb|adj|...",
  "ipa": "transkrypcja IPA",
  "ui_hints": {{
    "script": "Latn|Cyrl|Arab|Hans|Jpan|Kore|Deva|Thai|Hebr|Grek",
    "rtl": false,
    "show_conjugation": true,
    "conjugation_kind": "person_tense|agglutinative|aspect_particles|minimal|none",
    "has_articles": false,
    "has_cases": false,
    "has_gender": false
  }},
  "meanings": [
    {{
      "gloss_l1": "sens w L1 — kolejno od najczęstszego",
      "synonyms_l1": ["synonimy gloss_l1 w L1 — ta sama część mowy co gloss_l1"],
      "examples": [],
      "usages": [
        {{"l2": "kolokacja w L2 pokazująca ten sens", "l1": "jej tłumaczenie w L1"}}
      ]
    }}
  ],
  "synonyms_l2": [
    {{"lemma": "synonim w L2", "pos": "ta sama część mowy co lemat", "gloss_l1": "tłumaczenie na {native}"}}
  ],
  "antonyms_l2": [
    {{"lemma": "antonim w L2", "pos": "ta sama część mowy co lemat", "gloss_l1": "tłumaczenie na {native}"}}
  ],
  "word_family_l2": [
    {{"lemma": "wyraz pokrewny w L2 (inny od lematu)", "pos": "noun|verb|adj|...", "gloss_l1": "tłumaczenie na {native}"}}
  ],
  "notes": null,
  "confidence": 0.95
}}

Reguły:
- Pole examples zostaw jako pustą tablicę [].
- pos: konkretna wartość (noun, verb, adj, adv, ...) — nigdy "unknown".
- gloss_l1 = istniejące słowo języka {native}. Jeśli nie znasz lematu, podaj
  najbliższe realne tłumaczenie — nigdy nie twórz słowa przez dodanie
  końcówki {native} do lematu L2.
- Język L2 = {learning}, tłumaczeń L1 = {native}.
- ui_hints: ustaw show_conjugation zgodnie z typologią L2 (np. chiński/tajski → false).
- NIE generuj: similar_words, conjugation, przykładów zdań.

Znaczenia (meanings) — najważniejsza część karty:
- KOLEJNOŚĆ według częstości użycia. Pierwsze znaczenie to takie, które słownik
  dwujęzyczny {learning}–{native} podaje jako pierwsze i z którym uczący się
  zetknie się najczęściej. Nigdy nie zaczynaj od sensu rzadkiego, książkowego
  ani przenośnego, jeśli istnieje sens codzienny.
- MAKSYMALNIE 3 znaczenia: jedno główne i do dwóch pobocznych. Liczba wynika
  ze słowa, nie z limitu — jeśli sens jest praktycznie jeden, podaj DOKŁADNIE
  jedno znaczenie i nie dorabiaj drugiego.
- ZGRUPUJ sensy bliskoznaczne w jedno znaczenie.
- ZAKAZ sensów rzadkich, archaicznych, slangowych i niszowych.
- Znaczenia opisują WYŁĄCZNIE goły lemat (bez stałego przyimka wymaganego do sensu).
  Stałe „lemat + przyimek” z innym sensu → periphrases (osobny krok), nie meanings.
- usages = krótkie ZWROTY / kolokacje (nie pełne zdania); ilustrują goły lemat.
- Poziom {cefr} wpływa na dobór słownictwa w tłumaczeniach, NIE na liczbę znaczeń.
- usages: 2–4 prawdziwe kolokacje w {learning} z tłumaczeniem na {native}.
- Jeśli dwa sensy mają to samo słowo L1 (np. PL „lot”), ROZRÓŻNIJ gloss_l1
  krótkim dopiskiem w nawiasie, np. „lot (samolot)” / „lot (ptaka)” — nie zostawiaj
  identycznego gloss_l1 dla różnych sensów.
- Forma zwrotna z innym sensu tylko gdy należy do 3 najczęstszych I dotyczy formy
  zwrotnej jako lematu karty.

Synonimy — DEFINICJA:
Synonim = inne słowo TEJ SAMEJ części mowy, które w tym znaczeniu można użyć
ZAMIAST gloss_l1 (L1) lub lematu (L2).

synonyms_l1: tylko {native}, ta sama POS co gloss_l1.
synonyms_l2 / antonyms_l2: obiekty {{lemma, pos, gloss_l1}}, ta sama POS co lemat.
ZAKAZ w synonyms_l2 / antonyms_l2: inna POS, derywaty z tej samej rodziny
  wyrazów, ogólniki, powtórzenia lematu.

Wyrazy pokrewne (word_family_l2) — rodzina wyrazów / wspólny rdzeń:
- Inne lematy L2 z TEGO SAMEGO rdzenia morfologicznego co hasło karty
  (np. trabajar → trabajo, trabajador; escribir → escritura, escritor;
  aguantar → aguante, aguantador, aguantado, inaguantable).
- DOZWOLONA (i oczekiwana) inna część mowy niż lemat — tu trafiają derywaty.
- Dla produktywnych rodzin podaj 4–10 NAJCZĘSTSZYCH, realnych lematów.
  Typowe sloty (gdy istnieją i są częste w L2):
  • rzeczownik odczasownikowy / abstrakcyjny (aguante, trabajo)
  • agent / osoba (aguantador, trabajador) — także forma żeńska, jeśli osobna
  • imiesłów / adj odczasownikowy używany jako lemat (aguantado, cansado)
  • antonimiczny derywat z negacją (inaguantable, imposible) gdy częsty
  • inne częste derywaty (czasownik zwrotny jako osobny lemat tylko gdy
    słownikowy i inny sens — inaczej pomiń)
- NIE pomijaj oczywistych, wysokoczęstotliwych derywatów (np. -dor/-tora,
  -ción/-sión, -miento, -ado/-ido jako adj, in-/des- + rdzeń).
- Jeśli brak wyraźnej rodziny → pusta tablica [].
- ZAKAZ: powtórzenie lematu karty, synonimy/antonimy bez wspólnego rdzenia,
  formy fleksyjne tego samego lematu (odmiana → conjugation, nie tu),
  kolokacje wielowyrazowe, hapaxy i neologizmy.
- Format: obiekty {{lemma, pos, gloss_l1}} — pole pos OBOWIĄZKOWE
  (noun|verb|adj|adv|…), nigdy puste.
"""

EXAMPLES_PROMPT_V1 = """Jesteś ekspertem od przykładów zdań do nauki języków.

{pair_guidance}

Para językowa: L1 = {native}, L2 = {learning}
Lemat (L2): {lemma}
Część mowy: {pos}
Znaczenia (gloss_l1) — w TEJ KOLEJNOŚCI, po jednym bloku examples na znaczenie:
{glosses}

Dla KAŻDEGO znaczenia z listy wygeneruj DOKŁADNIE 3 pełne ZDANIA w tablicy
examples — po jednym na poziom A2, B2 i C2.

Każde zdanie obsługuje całe pasmo poziomów, więc różnica między nimi musi być
wyraźna:
- A2 — dla początkującego (zobaczą je poziomy A1 i A2): krótkie, czas
  teraźniejszy / formy podstawowe typowe dla L2, podstawowe słownictwo.
- B2 — dla średnio zaawansowanego (poziomy B1 i B2): dłuższe, zdanie złożone,
  bogatsza morfologia L2.
- C2 — dla zaawansowanego (poziomy C1 i C2): naturalne i idiomatyczne.

TWARDY ZAKAZ powtórzeń między znaczeniami:
- Żadne zdanie l2 NIE MOŻE się powtórzyć w innym znaczeniu (ani lekko
  parafrazowane to samo zdanie).
- Zdania przy znaczeniu N muszą ilustrować WYŁĄCZNIE sens N — nie kopiuj
  przykładów z sensu 1 do sensu 2.
- Jeśli gloss_l1 wygląda podobnie (np. „lot (samolot)” vs „lot (ptaka)”),
  konteksty muszą być wyraźnie różne (np. lotnisko vs ptak/motyl).
- Tablica meanings musi mieć TĘ SAMĄ DŁUGOŚĆ i KOLEJNOŚĆ co lista znaczeń powyżej.

Tekst L2 w skrypcie L2; tłumaczenie L1 w skrypcie L1.
Każdy przykład: {{"l2": "zdanie w L2", "l1": "tłumaczenie w L1", "cefr": "A2"}}
{retry_note}

Zwróć WYŁĄCZNIE JSON:
{{
  "meanings": [
    {{
      "gloss_l1": "to samo co w liście znaczeń (ta sama kolejność)",
      "examples": [
        {{"l2": "...", "l1": "...", "cefr": "A2"}},
        {{"l2": "...", "l1": "...", "cefr": "B2"}},
        {{"l2": "...", "l1": "...", "cefr": "C2"}}
      ]
    }}
  ]
}}
"""


def build_enrichment_core_prompt(
    *,
    native: str,
    learning: str,
    lemma: str,
    pos: str,
    cefr: str,
) -> str:
    known_pos = pos and pos.lower() != "unknown"
    return ENRICHMENT_CORE_PROMPT_V1.format(
        native=native,
        learning=learning,
        lemma=lemma,
        pos=pos if known_pos else "(ustal samodzielnie)",
        pos_line=pos if known_pos else "nie podano — ustal ją samodzielnie z lematu",
        cefr=cefr,
        pair_guidance=language_pair_guidance(native=native, learning=learning),
    )


def build_examples_prompt(
    *,
    native: str,
    learning: str,
    lemma: str,
    pos: str,
    glosses: list[str],
    retry: bool = False,
) -> str:
    retry_note = (
        "POPRZEDNIA ODPOWIEDŹ BYŁA BŁĘDNA LUB NIEKOMPLETNA. Każde znaczenie musi mieć "
        "dokładnie 3 zdania (A2, B2, C2). ZAKAZ powtarzania tego samego l2 między "
        "znaczeniami — każde znaczenie dostaje własne, unikalne zdania."
        if retry
        else ""
    )
    return EXAMPLES_PROMPT_V1.format(
        native=native,
        learning=learning,
        lemma=lemma,
        pos=pos,
        glosses="; ".join(glosses),
        retry_note=retry_note,
        pair_guidance=language_pair_guidance(native=native, learning=learning),
    )


# Zachowane dla kompatybilności wewnętrznej — nie używaj do pełnej karty.
ENRICHMENT_PROMPT_V1 = ENRICHMENT_CORE_PROMPT_V1


def build_similar_words_prompt(
    *,
    native: str,
    learning: str,
    lemma: str,
    pos: str,
    count: int,
) -> str:
    return SIMILAR_WORDS_PROMPT_V1.format(
        native=native,
        learning=learning,
        lemma=lemma,
        pos=pos,
        pos_form=pos_form_label(pos),
        filler_cefr=FILLER_CEFR,
        count=count,
    )


def build_similar_words_fill_prompt(
    *,
    native: str,
    learning: str,
    pos: str,
    exclude: list[str],
    count: int,
) -> str:
    return SIMILAR_WORDS_FILL_PROMPT_V1.format(
        native=native,
        learning=learning,
        pos=pos,
        pos_form=pos_form_label(pos),
        filler_cefr=FILLER_CEFR,
        exclude=", ".join(exclude) if exclude else "(brak)",
        count=count,
    )


def build_enrichment_prompt(
    *,
    native: str,
    learning: str,
    lemma: str,
    pos: str,
    cefr: str,
) -> str:
    return build_enrichment_core_prompt(
        native=native,
        learning=learning,
        lemma=lemma,
        pos=pos,
        cefr=cefr,
    )

_POS_FORMS = {
    "verb": "bezokolicznik",
    "noun": "mianownik, z rodzajnikiem jeśli język go używa",
    "adj": "forma podstawowa, rodzaj męski, liczba pojedyncza",
    "adv": "forma podstawowa",
}


def pos_form_label(pos: str) -> str:
    return _POS_FORMS.get((pos or "").lower(), "podstawowa forma słownikowa")


SIMILAR_WORDS_SYSTEM_V1 = (
    "Przygotowujesz materiały do fiszek językowych. "
    "Zwracasz zawsze pełną, żądaną liczbę pozycji — każdą inną od pozostałych. "
    "Podajesz wyłącznie prawdziwe słowa ze słownika, nigdy form wymyślonych. "
    "Tylko JSON zgodny ze schematem."
)

# Dystraktor ma być pułapką, nie słowem do nauki, więc wypełniacze bierzemy
# ze stałego poziomu średnio zaawansowanego. Przy poziomie uczącego się listę
# domykały słowa w rodzaju „comer”, „vivir”, „abrir” — zbyt oczywiste na dystraktor.
FILLER_CEFR = "B2"

SIMILAR_WORDS_PROMPT_V1 = """Przygotowujesz fiszkę do nauki języka {learning} dla osoby mówiącej po {native}.

Słowo na fiszce: {lemma}
Część mowy: {pos}

Fiszka ma tryb wyboru odpowiedzi, więc obok poprawnej odpowiedzi trzeba pokazać
inne słowa. Podaj {count} takich słów.

Warunki — każdy obowiązkowy:
1. Ta sama część mowy co słowo na fiszce: {pos}
2. Prawdziwe słowo języka {learning} — nigdy forma wymyślona ani zniekształcona
3. Inne słowo niż „{lemma}” — nie jego odmiana i nie wyraz pochodny od tego rdzenia
4. Forma słownikowa: {pos_form}
5. Każda pozycja inna od pozostałych na liście
6. Krótkie tłumaczenie na {native} — 1–3 słowa

Kolejność wypełniania listy:
Najpierw wpisz słowa możliwie podobne do „{lemma}” na piśmie lub w wymowie —
takie, z którymi uczący się może je pomylić.

Podobnych szukaj systematycznie i WYCZERP te sposoby, zanim sięgniesz
po wypełniacze:
a) ta sama końcówka, inny początek — dopisz do końcówki „{lemma}” różne
   przedrostki i rdzenie; zwykle daje to najwięcej trafień
b) zmiana jednej litery w „{lemma}”
c) dodanie lub usunięcie jednej litery
d) ten sam początek, inna końcówka
e) słowo o innym zapisie, ale bardzo bliskim brzmieniu
Gdy podobne się skończą, dopełnij listę do {count} słowami z poziomu {filler_cefr}.
Te nie muszą być podobne, ale trzymaj poziom: nie wpisuj podstawowych słów
z A1–A2 ani rzadkich, literackich i książkowych. Ma to być słownictwo, które
świadomy użytkownik języka spotyka w prasie i rozmowie.

Zwróć pełne {count} pozycji.
"""

SIMILAR_WORDS_FILL_PROMPT_V1 = """Przygotowujesz fiszkę do nauki języka {learning} dla osoby mówiącej po {native}.

Do puli odpowiedzi w quizie brakuje słów. Podaj {count} słów.

Warunki — każdy obowiązkowy:
1. Część mowy: {pos}
2. Prawdziwe słowa języka {learning}
3. Forma słownikowa: {pos_form}
4. Słownictwo z poziomu {filler_cefr} — ani podstawowe z A1–A2, ani rzadkie
   i literackie; takie, które spotyka się w prasie i rozmowie
5. Każda pozycja inna od pozostałych
6. Żadne nie może być na tej liście: {exclude}
7. Krótkie tłumaczenie na {native} — 1–3 słowa

Nie muszą być do niczego podobne. Zwróć pełne {count} pozycji.
"""

IMPORT_FORMAT_SYSTEM_V1 = (
    "Jesteś warstwą ANALIZY FORMATU importu w Vocabulario. "
    "Dostajesz SUROWĄ próbkę pliku/wklejki (nie gotowe notatki). "
    "Zwracasz JSON z instrukcją segmentacji: jak dzielić tekst na fiszki i pola. "
    "Backend wykona tę instrukcję deterministycznie na CAŁYM pliku. "
    "Wnioskuj z próbki — szczególnie rozróżniaj separator MIĘDZY kartami "
    "od separatora MIĘDZY terminem a definicją (Quizlet pozwala ustawić oba dowolnie). "
    "Tylko JSON."
)

IMPORT_FORMAT_PROMPT_V1 = """Użytkownik importuje fiszki. Najpierw musisz opisać FORMAT pliku.

Para językowa: L1={native_name}, L2={learning_name}
Hint rodzaju źródła: {kind_hint}
Znane nazwy pól (jeśli już z Anki/DB): {field_names}

SUROWA próbka tekstu (może być obcięta; zachowaj wnioski z tego, co widać):
-----
{raw_sample}
-----

Zadanie:
1. Rozpoznaj format (Quizlet export, Anki, TSV, CSV, bloki wieloliniowe, lista słów…).
2. Zwróć instrukcję segmentacji:
   - already_segmented=true TYLKO gdy to już uporządkowane notatki z polami (apkg / Anki notes).
   - card_separator = jak dzielić na OSOBNE fiszki:
       newline | blank_lines | semicolon | custom_string | none
     Quizlet „Exportar”: często JEDNA linia: term,def;term,def;term,def
     → card_separator=semicolon, field_delimiter=comma, field_split=first_only
   - field_delimiter = separator WEWNĄTRZ fiszki (tab/comma/semicolon/none)
   - field_split=first_only gdy definicja może zawierać ten sam znak co delimiter
     (np. przecinek w tłumaczeniu)
   - row_mode: zwykle delimited dla Quizlet/TSV; multiline_first_rest dla bloków
   - append_continuation_lines_to_answer gdy trzeba
3. preview_notes: 3–8 notatek [front, back] PO Twojej instrukcji (osobne fiszki!).
4. rationale po polsku.

WAŻNE:
- NIE myl card_separator z field_delimiter.
- Jeśli widać wiele „term,def” rozdzielonych średnikami w jednej linii — to WIELE fiszek,
  nie jedna.
- Nie kopiuj CSS/JS Anki. Nie wymyślaj treści spoza próbki.
"""

IMPORT_CLASSIFY_SYSTEM_V1 = (
    "Klasyfikujesz zaimportowane fiszki pod karty Vocabulario. "
    "Dla każdej notatki ustalasz entry_kind i headword_l2 (język uczony). "
    "Cel: wyciągnąć LEMATY słownikowe do pełnych kart Vocabulario (jak lookup). "
    "Dla zwrotów/konstrukcji podaj base_lemma (goły lemat). "
    "valid=false tylko przy pustce / śmieciach / braku treści L2. Tylko JSON."
)

IMPORT_CLASSIFY_PROMPT_V1 = """Użytkownik importuje fiszki do Vocabulario (tryb bogatych kart).

Para: L1={native_name}, L2={learning_name}

Notatki (każda = lista pól; zwykle [front L2, back L1]):
{notes_json}

Dla KAŻDEJ notatki (po indeksie) zwróć wpis:
- entry_kind:
  - lemma — pojedyncze hasło słownikowe (fumar, el banco)
  - construction — peryfraza / wzorzec (volver a hacer algo, dejar de + inf.)
  - phrase — krótki zwrot (pedir perdón, hacer la cama)
  - sentence — pełne zdanie / dialog
  - other — reszta sensowna do nauki
- headword_l2 — forma w L2 (front jeśli to L2; nie tłumaczenie L1)
- gloss_l1 — z tyłu fiszki jeśli jest, inaczej null
- base_lemma — opcjonalnie goły czasownik/rzeczownik bazy (volver)
- pattern — opcjonalnie wzorzec (volver a + infinitivo)
- pos — verb|noun|adj|phrase|construction|sentence|…
- valid — false tylko jeśli brak treści do nauki
- invalid_reason — gdy valid=false

WAŻNE:
- „volver a hacer algo” = construction + base_lemma=\"volver\" (z tego powstanie karta lematu).
- Zdania bez sensownego lematu: entry_kind=sentence; backend odrzuci je z trybu Vocabulario.
- Pojedyncze słowa / article+noun = lemma.
Zwróć entries dla wszystkich indeksów 0..N-1.
rationale po polsku.
"""

IMPORT_ADAPTIVE_SYSTEM_V1 = (
    "Budujesz bogatą kartę Vocabulario dla zwrotu / konstrukcji / zdania. "
    "Przykłady i użycia są obowiązkowe. Pełnej tabeli koniugacji NIE generujesz. "
    "Tylko JSON."
)

IMPORT_ADAPTIVE_PROMPT_V1 = """Zbuduj kartę Vocabulario (adaptive) dla jednostki nauki.

Para: L1={native_name}, L2={learning_name}
CEFR użytkownika: {cefr}
entry_kind: {entry_kind}
headword (L2): {headword}
gloss z importu (L1, może być pusty): {gloss}
base_lemma (opcjonalnie): {base_lemma}
pattern (opcjonalnie): {pattern}

Wymagania:
1. lemma = headword (dokładnie to, czego się uczymy — nie redukuj do base_lemma)
2. 1–2 meanings z gloss_l1 (użyj gloss z importu jeśli sensowny)
3. usages: 2–4 krótkie wskazówki użycia w L1
4. examples: min. 3 zdania (l2 + l1 + cefr A2/B2/C2) z użyciem headword
5. pattern — uzupełnij jeśli construction (np. volver a + infinitivo)
6. related_lemma — base_lemma jeśli pasuje
7. Bez pełnej conjugation; notes opcjonalnie po polsku

Nie zmyślaj nieistniejących konstrukcji. Tylko JSON.
"""

IMPORT_STRUCTURE_SYSTEM_V1 = (
    "Jesteś warstwą decyzji importu w aplikacji Vocabulario. "
    "Dostajesz próbkę pliku/wklejki (Anki, Quizlet Export, CSV/TSV, lista słów) "
    "i MUSISZ zwrócić JSON ze strategią wyciągnięcia haseł L2. "
    "Bez tej strategii backend nie wie, jak zbudować karty. "
    "Hasło L2 = forma słownikowa w języku uczonym (lemma / bezokolicznik), "
    "NIE tłumaczenie L1, NIE nazwa czasu, NIE zdanie przykładowe, NIE tabela odmiany."
)

IMPORT_STRUCTURE_PROMPT_V1 = """Użytkownik importuje materiał do Vocabulario.

Kontekst aplikacji:
- Język ojczysty (L1): {native_name}
- Język uczony (L2): {learning_name}
- Po Twojej decyzji backend WYCIĄGNIE hasła L2 z CAŁEGO pliku według Twojej strategii,
  potem ZWALIDUJE exact (hasło musi być prawdziwym słowem L1 lub L2),
  a użytkownik zatwierdzi listę → powstanie jedna karta Vocabulario na unikalne hasło L2
  (enrichment AI robi Vocabulario osobno — Ty tylko wskazujesz SKĄD brać lemma).

Źródło:
- Format: {kind}
- Liczba notatek/wierszy: {total_notes}
- Nazwy pól (jeśli znane): {field_names}

Próbka notatek (każda = lista pól w kolejności; HTML może być surowy):
{sample_json}

Twoje zadanie (obowiązkowe):
1. Rozpoznaj format (Quizlet term+def, Anki notes, HTML cards, plain list…).
2. Wskaż JEDNO źródło hasła L2 (indeks pola / klasa HTML / plain_list).
3. W rationale napisz czarno na białym po polsku:
   - co to za dane,
   - które pole = hasło L2,
   - które pola IGNOROWAĆ (L1, czas, przykład, odmiana),
   - że z każdego unikalnego hasła L2 powstanie osobna karta po walidacji.
4. sample_headwords: 5–15 realnych haseł L2 z próbki po Twojej strategii.
5. unique_estimate: ile unikalnych haseł L2 w całej talii (ta sama lemma w wielu
   czasach Anki = jedno hasło).

Strategia:
- field_index — stały indeks pola (0-based) we wszystkich notatkach
- html_class — karty HTML; podaj klasę CSS z hasłem L2 (np. answer-word)
- plain_list — każdy wiersz to już jedno hasło L2 (jedna kolumna)

l2_field_label: krótka etykieta źródła hasła (np. "kolumna 0 (Quizlet term)",
"pole Spanish", "class=answer-word").
"""

IMPORT_DISPLAY_SYSTEM_V1 = (
    "Jesteś warstwą layoutu importu fiszek w Vocabulario. "
    "Notatki są JUŻ posegmentowane (wcześniejsza analiza formatu / Anki fields). "
    "Dostajesz próbkę notatek i zwracasz JSON: które pole to hasło (prompt), "
    "które to odpowiedź, oraz SZABLON bloków UI (front/back) z field_index "
    "ORAZ intencją prezentacji (align/size/semantic/tts). "
    "Karta ma wyglądać spójnie ze stylem Vocabulario (czysto, mobilnie). "
    "Nie kopiujesz CSS/JS Anki. Nie zmyślasz treści — tylko mapowanie i strukturę. "
    "Tylko JSON."
)

IMPORT_DISPLAY_PROMPT_V1 = """Użytkownik chce ZACHOWAĆ swoje fiszki (nie wyciągamy samych lematów słownikowych).
Notatki poniżej są już podzielone na fiszki i pola — NIE dziel ich od nowa.

Para językowa: L1={native_name}, L2={learning_name}
Format: {kind}
Liczba notatek: {total_notes}
Nazwy pól: {field_names}

Próbka notatek (każda = lista pól; może być HTML):
{sample_json}

Zadanie:
1. Wykryj języki w próbce (potwierdź L1/L2).
2. Dla każdego indeksu pola ustaw role:
   prompt | answer | secondary | example | meta | detail | ignore
3. Zbuduj prompt_blocks (front) i answer_blocks (tył) jako SZABLON:
   - Używaj field_index / l2_field_index / l1_field_index zamiast wklejać długi tekst.
   - type ∈ headword, gloss, bilingual, list, table, note, chip, section, divider, text
   - section: heading + collapsed + children (1 poziom)
   - Tabela odmiany/koniugacji w HTML → type=table ALBO section z field_index na pole HTML
     (NIE type=pre, NIE ściana tekstu)
   - FRONT: WYŁĄCZNIE 1× headword (align=center, size=lemma, semantic=headword, tts L2).
     NIE wstawiaj na front: oboczności, chipów meta, przykładów, odmiany, przycisków ▶.
   - BACK kolejność:
     (a) gloss = czyste znaczenie L1 (semantic=translation, size=gloss) — BEZ zdań przykładów
     (b) opcjonalnie chip oboczności / irregularity (meta) — TYLKO na answer
     (c) section „Przykłady” z bilingual (ES+PL) gdy przykłady są w tym samym polu co gloss
         albo w osobnych polach example
     (d) section „Odmiana” collapsed z tabelami z pola conjugation/HTML
   - Jeśli jedno pole zawiera „znaczenie + przykłady” (Meanings_Block):
     ustaw je jako gloss (field_index) — backend rozdzieli pierwszą linię / pary przykładów.
   - Usuń Anki chrome: <script>, play-btn / ▶ → to NIE jest tekst karty; użyj tts na headword.
   - Dla każdego bloku ustaw: align, size, semantic, tts (lub null)
4. prompt_style: word | phrase | sentence | html_block
5. answer_needs_structure=true tylko gdy prawa strona jest długa i NIE masz osobnego pola HTML tabel
6. bidirectional=true TYLKO gdy pewnie: headword=L2 + gloss=czyste L1; inaczej false
7. rationale po polsku

Przykład A (Anki 4 pola: Spanish, Meanings_Block, Irregularity, Conjugation):
- roles: prompt, answer, meta, detail
- prompt: headword(Spanish)
- answer: gloss(Meanings_Block) + chip(Irregularity) + section Odmiana[field Conjugation → tables]
- bidirectional=true

Przykład B (Quizlet term/definition):
- prompt: headword(term) · answer: gloss(definition) · bidirectional=true
"""

IMPORT_LAYOUT_SYSTEM_V1 = IMPORT_DISPLAY_SYSTEM_V1
IMPORT_LAYOUT_PROMPT_V1 = IMPORT_DISPLAY_PROMPT_V1

IMPORT_ANSWER_STRUCTURE_SYSTEM_V1 = (
    "Dzielisz treść prawej strony fiszki na czytelne bloki UI (JSON). "
    "Nie dodajesz nowych faktów — tylko nagłówki, sekcje, zwijanie. Tylko JSON."
)

IMPORT_ANSWER_STRUCTURE_PROMPT_V1 = """Poniżej próbki prawej strony fiszki (po oczyszczeniu HTML).
Zaproponuj strategię podziału na bloki mobilne.

Para: L1={native_name}, L2={learning_name}

Próbki:
{samples_json}

Zwróć:
- strategy: paragraphs | headings | keep_pre | sections_from_sample
- heading_hints: typowe nagłówki jeśli widać
- sample_blocks: layout DLA PIERWSZEJ próbki z wypełnionym text (nie field_index)
- Nieużywane pola bloku = null
- rationale po polsku
"""

