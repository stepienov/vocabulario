"""Wersjonowane prompty AI — zgodnie z PLAN_IMPLEMENTACJI.md sekcja 5."""

from app.ai.conjugation import conjugation_rules_for_prompt

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
}


def lang_name_pl(code: str) -> str:
    return LANG_NAMES_PL.get((code or "").strip().lower(), code)


LOOKUP_SYSTEM_V1 = (
    "Lookup słownikowy: zwracasz wyłącznie prawdziwe hasła jako JSON. "
    "Nie zmyślaj znaczeń dla nieistniejących ciągów. "
    "Gdy zapytanie jest dokładnym hasłem w języku uczonym, ten lemat MUSI być "
    "pierwszym kandydatem — nie zastępuj go formą zwrotną ani derywatem. "
    "Gdy zapytanie to literówka, lemat poprawki musi być inny niż zapytanie. "
    "Rzeczowniki z rodzajnikiem. Bez zwrotów i bez peryfraz. Tylko JSON."
)

LOOKUP_PROMPT_V1 = """Jesteś leksykografem. Użytkownik szuka JEDNEGO hasła w słowniku.

Język ojczysty użytkownika: {native_name}
Język, którego się uczy: {learning_name}
Poziom CEFR: {cefr}
Wpisane zapytanie: "{text}"

Zapytanie czytaj wyłącznie jako {native_name} albo {learning_name}.
Nie interpretuj go jako słowa z innego języka, chyba że ten język jest jednym z dwóch powyżej.

ZADANIE
Zwróć listę kandydatów — prawdziwych haseł w języku {learning_name}, które użytkownik
mógł mieć na myśli (max 8, od najbardziej prawdopodobnego).

KROK A — czy „{text}” jest prawdziwym hasłem?
Jeśli „{text}” jest standardowym hasłem słownikowym w języku {learning_name}
(np. popularny bezokolicznik, rzeczownik, przymiotnik), MUSI znaleźć się na liście
jako PIERWSZY kandydat, z lemma dokładnie równym „{text}” (dla rzeczownika:
z prawidłowym rodzajnikiem, jeśli w języku {learning_name} tak się hasłuje).
Dopiero PO dokładnym trafieniu wolno dodać formy pokrewne (zwrotne, rzeczownik odczasownikowy).
ZAKAZANE: pominąć dokładne trafienie i zwrócić tylko derywaty
(np. wpisano „contar” → ŹLE: same contarse / el contar bez „contar”).
ZAKAZANE: zmyślać znaczenie dla ciągu, którego nie znasz ze słownika.
ZAKAZANE: zwrócić lemma = „{text}” z wymyślonym glossem, gdy słowo nie istnieje.

KROK B — literówka (gdy „{text}” NIE jest pewnym hasłem)
Zaproponuj najbliższe PRAWDZIWE hasła w języku {learning_name}.
- Lemat poprawki MUSI różnić się od „{text}”.
- Odległość edycyjna najwyżej 2: zamiana litery, przestawienie, brakująca
  albo nadmiarowa litera (także na początku lub na końcu), sąsiad na klawiaturze.
- Przykład: „cabar” → „acabar” (brakujące „a” na początku) — TO JEST poprawka, nie odrzucaj jej.
- Długość zbliżona (różnica długości najwyżej 2).
- Nie proponuj słów tylko dlatego, że dzielą długi wspólny początek albo zawierają
  „{text}” jako fragment, jeśli odległość edycyjna przekracza 2
  (np. „cabar” ↛ „cabalgada”).

KROK C — tłumaczenie z języka ojczystego
Jeśli „{text}” jest prawdziwym słowem w języku {native_name}, podaj jego
odpowiedniki w języku {learning_name}.

FORMA KAŻDEGO KANDYDATA (język {learning_name}):
- czasownik → bezokolicznik (np. apoyar, apoyarse, contar)
- rzeczownik → ZAWSZE z rodzajnikiem: el/la/los/las + rzeczownik (np. el apoyo, el contar)
- przymiotnik → forma podstawowa męska lp. (np. vacío)
- inne → pojedynczy lemat

ZAKAZANE:
- zwroty wielowyrazowe (np. „el apoyo mutuo”)
- czasownik + przyimek (np. „apoyar a”, „dejar de”)
- pominięcie dokładnego lematu na rzecz formy zwrotnej albo homonimicznego rzeczownika
- zdania poza polem gloss

PRZYKŁADY

Wpisał „contar” (prawdziwy czasownik hiszpański):
DOBRZE (kolejność): contar (verb, liczyć / opowiadać), potem opcjonalnie contarse, el contar
ŹLE: tylko contarse i el contar — bez „contar”

Wpisał „apoyar” (prawdziwy czasownik hiszpański):
DOBRZE: apoyar (verb, wspierać), apoyarse (verb, opierać się), el apoyo (noun, wsparcie)
ŹLE: apoyo bez rodzajnika; el apoyo mutuo; apoyar a
ŹLE: same apoyarse / el apoyo bez „apoyar”

Wpisał „aprneder” (literówka):
DOBRZE: aprender
ŹLE: aprovechar, el aprendizaje — tylko wspólny początek

Wpisał „cabar” (nie istnieje w hiszpańskim):
DOBRZE: caber (verb, mieścić się) — zamiana a→e
DOBRZE: cavar (verb, kopać) — zamiana b→v
DOBRZE: acabar (verb, kończyć) — brakujące „a” na początku (odległość 1)
ŹLE: lemma „cabar” z jakimkolwiek glossem — zmyślanie nieistniejącego hasła
ŹLE: cabalgada — wspólny początek, odległość edycyjna > 2

Wpisał „red” przy języku uczonym = hiszpański, ojczystym = polski:
DOBRZE: la red (sieć) — „red” istnieje po hiszpańsku
ŹLE: rojo — to byłoby czytanie zapytania po angielsku

Zwróć WYŁĄCZNIE JSON:
{{
  "candidates": [
    {{"lemma": "...", "pos": "...", "gloss": "..."}}
  ]
}}
"""


ENRICHMENT_CORE_PROMPT_V1 = """Jesteś ekspertem leksykograficznym. Tworzysz rdzeń karty słówka (BEZ przykładów zdań, BEZ koniugacji, BEZ similar_words).

Para językowa: L1 (ojczysty) = {native}, L2 (uczony) = {learning}
Lemat (L2): {lemma}
Część mowy: {pos_line}

Zwróć WYŁĄCZNIE JSON:
{{
  "schema_version": "1.0",
  "lemma": "słowo w L2",
  "language": "{learning}",
  "pos": "noun|verb|adj|...",
  "ipa": "transkrypcja IPA",
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
- NIE generuj: similar_words, conjugation, przykładów zdań.

Znaczenia (meanings) — najważniejsza część karty:
- KOLEJNOŚĆ według częstości użycia. Pierwsze znaczenie to takie, które słownik
  dwujęzyczny {learning}–{native} podaje jako pierwsze i z którym uczący się
  zetknie się najczęściej. Nigdy nie zaczynaj od sensu rzadkiego, książkowego
  ani przenośnego, jeśli istnieje sens codzienny.
- MAKSYMALNIE 3 znaczenia: jedno główne i do dwóch pobocznych. Liczba wynika
  ze słowa, nie z limitu — jeśli sens jest praktycznie jeden, podaj DOKŁADNIE
  jedno znaczenie i nie dorabiaj drugiego.
- ZGRUPUJ sensy bliskoznaczne w jedno znaczenie. „ścielić” i „pościelić” to jeden
  sens; „dążyć” i „zmierzać” to jeden sens. Najczęstsze tłumaczenie wpisz
  jako gloss_l1, pozostałe do synonyms_l1 — nie jako osobne znaczenia.
- Jeśli po zgrupowaniu zostaje więcej niż 3 sensy, zostaw 3 NAJCZĘŚCIEJ używane
  w codziennym języku, a resztę pomiń.
- ZAKAZ sensów rzadkich, archaicznych, slangowych i niszowych, nawet jeśli
  słownik je notuje.
- Odrębnym sensem NIE jest wariant stylistyczny tego samego znaczenia ani jego
  węższy podtyp — takie warianty idą do synonyms_l1 albo wypadają.
- Znaczenia opisują WYŁĄCZNIE goły lemat (bez stałego przyimka / dopełnienia
  wymaganego do tego sensu). Jeśli sens wymaga stałej konstrukcji
  „lemat + przyimek” (albo innego stałego schematu), NIE jest to znaczenie
  gołego lematu — należy do conjugation.periphrases (generowanej osobno).
  Tu go nie podawaj ani jako osobnego gloss_l1, ani jako usages.
  Przykłady ZAKAZANE w meanings:
  - acabar de + infinitivo → „właśnie coś zrobić”
  - ir a + infinitivo → „zamierzać”
  - volver a + infinitivo → „znów coś zrobić”
  - dejar de + infinitivo → „przestać”
  - tener que / hay que → „musieć”
  - contar con + N → „liczyć na” / „dysponować”
  - acabar con + N → „położyć kres / likwidować”
  - tender a + infinitivo → „dążyć / skłaniać się”
  Test: gdyby usunąć przyimek z L2, czy gloss_l1 nadal ma sens dla samego
  lematu? Jeśli NIE (np. „liczyć na” bez „con”) — to NIE jest meaning.
- usages przy znaczeniu muszą ilustrować goły lemat (contar el dinero,
  contar una historia) — nie stałe „lemat + przyimek” z innym sensu.
- Forma zwrotna z innym sensu (acabarse → „skończyć się”) może być osobnym
  znaczeniem tylko gdy należy do 3 najczęstszych I dotyczy formy zwrotnej
  jako lematu karty; przy karcie „acabar” nie dorabiaj acabarse jako 3. sensu.
- Poziom {cefr} wpływa na dobór słownictwa w tłumaczeniach, NIE na liczbę
  znaczeń. Nie pomijaj częstego sensu, bo wygląda na trudny.
- usages: 2–4 prawdziwe kolokacje w {learning} pokazujące dany sens, każda
  z tłumaczeniem na {native}. Tłumacz całą kolokację, nie samo słowo — ma być
  naturalne w {native}, a nie kalką słowo w słowo.

Przykłady liczby znaczeń — L2 = es, L1 = pl:
perro → 1 znaczenie: "pies".
  ŹLE: "pies", "samiec psa" (podtyp tego samego sensu), "człowiek" (slang).
querer → 2 znaczenia: "chcieć", "kochać" — dwa naprawdę różne sensy.
contar → 2 znaczenia (NIE trzy):
  1. gloss_l1 "liczyć"     usages: contar el dinero, contar hasta diez
  2. gloss_l1 "opowiadać"  usages: contar una historia, contar un chiste
  ŹLE: "liczyć na" z usages contar con alguien — to peryfraza contar con,
       nie znaczenie gołego contar (trafia do conjugation.periphrases).
acabar → 1 znaczenie główne:
  1. gloss_l1 "kończyć"  usages: acabar el trabajo, acabar la reunión
  ŹLE: "właśnie zrobić" (acabar de) oraz "likwidować" (acabar con) — peryfrazy.
echar → sensów jest więcej niż 3, więc zostają 3 najczęstsze:
  1. gloss_l1 "rzucać"    usages: echar una piedra → rzucić kamieniem
  2. gloss_l1 "wlewać"    usages: echar agua en el vaso → nalać wody do szklanki
  3. gloss_l1 "wyrzucać"  usages: echar a alguien del trabajo → zwolnić kogoś z pracy
  ŹLE: "rzucać", "ciskać", "miotać" — jeden sens w trzech wariantach;
  „ciskać” i „miotać” to synonyms_l1 pierwszego znaczenia.

Synonimy — DEFINICJA (obowiązkowa):
Synonim = inne słowo TEJ SAMEJ części mowy, które w tym znaczeniu można użyć ZAMIAST gloss_l1 (L1) lub lematu (L2).

synonyms_l1:
- Tylko słowa w języku {native}.
- MUSZĄ mieć tę samą część mowy co gloss_l1 danego znaczenia.
- Jeśli gloss_l1 to czasownik (np. „oferować”) → synonyms_l1 to inne CZASOWNIKI (np. „darować”, „przedstawiać”).
- Jeśli gloss_l1 to rzeczownik (np. „oferta”) → synonyms_l1 to inne RZECZOWNIKI (np. „propozycja”, „wstawka”).
- Jeśli gloss_l1 to przymiotnik → synonyms_l1 to inne PRZYMIOTNIKI.

synonyms_l2 (poziom karty):
- 2–4 synonimy lematu w języku {learning}.
- Każdy jako obiekt: lemma, pos, gloss_l1.
- MUSZĄ mieć tę samą część mowy co lemat ({pos}).
- verb → inne czasowniki (infinitiv); noun → inne rzeczowniki (z el/la jeśli tak jest w lemacie).
- gloss_l1 = krótkie tłumaczenie tego synonimu na {native} (1–3 słowa).

antonyms_l2 (poziom karty):
- 1–3 antonimy lematu w języku {learning}.
- Ten sam format co synonyms_l2: {{"lemma", "pos", "gloss_l1"}}.
- Ta sama część mowy co lemat.
- gloss_l1 = krótkie tłumaczenie antonimu na {native}.

ZAKAZANE w synonimach i antonimach:
- Inna część mowy niż lemat (np. dla „oferować” ZAKAZ: oferta, propozycja — to rzeczowniki).
- Derywaty i słowa z tej samej rodziny (ofrecer → la oferta, oferować → oferta).
- Ogólniki, wyjaśnienia, kolokacje, tłumaczenia dosłowne z innej POS.
- Powtórzenia lematu.
- Same stringi zamiast obiektów — zawsze obiekt z lemma, pos, gloss_l1.

Przykład — ofrecer (verb), gloss_l1 głównego znaczenia: „oferować”:
DOBRZE synonyms_l1: darować, przedstawiać, udzielać
ŹLE synonyms_l1: oferta, propozycja (rzeczowniki!), oferent (rzeczownik)
DOBRZE synonyms_l2:
  {{"lemma": "regalar", "pos": "verb", "gloss_l1": "darować"}},
  {{"lemma": "brindar", "pos": "verb", "gloss_l1": "oferować"}},
  {{"lemma": "presentar", "pos": "verb", "gloss_l1": "przedstawiać"}}
ŹLE synonyms_l2: "regalar", la oferta, la propuesta
DOBRZE antonyms_l2:
  {{"lemma": "rechazar", "pos": "verb", "gloss_l1": "odrzucać"}}
"""

EXAMPLES_PROMPT_V1 = """Jesteś ekspertem od przykładów zdań do nauki języków.

Para językowa: L1 = {native}, L2 = {learning}
Lemat (L2): {lemma}
Część mowy: {pos}
Znaczenia (gloss_l1): {glosses}

Dla KAŻDEGO znaczenia wygeneruj DOKŁADNIE 3 przykłady zdań w tablicy examples —
po jednym na poziom A2, B2 i C2.

Każde zdanie obsługuje całe pasmo poziomów, więc różnica między nimi musi być
wyraźna:
- A2 — dla początkującego (zobaczą je poziomy A1 i A2): krótkie, czas
  teraźniejszy, podstawowe słownictwo.
- B2 — dla średnio zaawansowanego (poziomy B1 i B2): dłuższe, zdanie złożone,
  czasy przeszłe lub przyszłe.
- C2 — dla zaawansowanego (poziomy C1 i C2): naturalne i idiomatyczne, bogate
  słownictwo, konstrukcje rzadsze w mowie potocznej.

Każde zdanie MUSI pokazywać dokładnie to znaczenie, przy którym stoi.
Każdy przykład: {{"l2": "zdanie w L2", "l1": "tłumaczenie w L1", "cefr": "A2"}}
{retry_note}

Zwróć WYŁĄCZNIE JSON:
{{
  "meanings": [
    {{
      "gloss_l1": "to samo co w liście znaczeń",
      "examples": [
        {{"l2": "...", "l1": "...", "cefr": "A2"}},
        {{"l2": "...", "l1": "...", "cefr": "B2"}},
        {{"l2": "...", "l1": "...", "cefr": "C2"}}
      ]
    }}
  ]
}}
"""

CONJUGATION_ONLY_PROMPT_V1 = """Jesteś ekspertem od hiszpańskiej koniugacji czasowników.

Lemat (L2): {lemma}

Zwróć WYŁĄCZNIE JSON:
{{
  "conjugation": {{
    "non_finite": {{"gerundio": "...", "participio": "..."}},
    "tenses": {{}},
    "periphrases": []
  }}
}}

{conjugation_rules}
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
        "POPRZEDNIA ODPOWIEDŹ BYŁA NIEKOMPLETNA. Każde znaczenie musi mieć dokładnie "
        "3 przykłady: jeden z cefr A2, jeden z B2 i jeden z C2."
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
    )


def build_conjugation_prompt(*, lemma: str) -> str:
    return CONJUGATION_ONLY_PROMPT_V1.format(
        lemma=lemma,
        conjugation_rules=conjugation_rules_for_prompt(lemma),
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
