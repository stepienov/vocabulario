# Analiza: uszczelnienie systemu językowego Vocabulario — 15 języków L2 na sztywno

**Data:** 2026-08-05 (rev. 5)  
**Status:** specyfikacja **gotowa do implementacji** — patrz §15  
**Autor:** analiza na podstawie stanu repozytorium `vocabulario` (backend + Android)

---

## 0. Decyzje zatwierdzone

### Rev. 2 — LSP / morfologia

| # | Decyzja | Ustalenie |
|---|---------|-----------|
| 1 | **Inflection** | **Pełne dane morfologiczne** na karcie — wszystkie czasy/formy istotne dla języka, **w tym rzadkie i zaawansowane (C2)**. Enrichment nie skraca zestawu „dla uproszczenia”. |
| 2 | **15. język** | **`vi` (Vietnamese)** zamiast `nl`. |
| 3 | **Kompatybilność wsteczna** | **Brak.** Produkt nie był wydany — **zastępujemy stare podejście w całości**. |
| 4 | **Deklinacja / fleksja nominalna** | **Pełna** — enrichment pobiera wszystko użyteczne dla lematu. |
| 5 | **Migracja** | **Żadnej.** Jedna implementacja LSP od zera. |

### Rev. 3 — język aplikacji + UI

| # | Decyzja | Ustalenie |
|---|---------|-----------|
| 6 | **15 UI = 15 L2** | W ramach featurea: **pełne słowniki UI** (`strings.xml` + mapy etykiet) dla **wszystkich 15** języków — symetria z LSP. |
| 7 | **Jeden język „aplikacji”** | **Brak rozróżnienia** `native_lang` vs `ui_lang`. Jest tylko **`app_lang`** — język, w którym użytkownik chce widzieć aplikację i glossy na kartach. Nie weryfikujemy „prawdziwego” języka ojczystego. |
| 8 | **Dwa ustawienia użytkownika** | **`app_lang`** (język aplikacji / tłumaczeń na kartach) + **`learning_lang`** (język nauki). Koniec. |
| 9 | **Domyślny `app_lang`** | Przy pierwszym uruchomieniu: **locale telefonu**, jeśli jest na liście 15; inaczej fallback **`en`**. Użytkownik może zmienić w dowolnym momencie. |
| 10 | **Bez dodatkowych języków UI** | Nie dodajemy `ur`, `bn`, `id` itd. — tylko **te same 15 kodów** co L2. |
| 11 | **Bez etapów językowych** | **Wszystkie** LSP + słowniki UI w **jednym** wdrożeniu. |

### Rev. 4 — szczegóły językowe i techniczne

Patrz tabela §13 (portugalski rozdzielony, arabski książkowy, import, koszt OpenAI…).

### Rev. 5 — UI, ustawienia, gotowość

| # | Decyzja | Ustalenie |
|---|---------|-----------|
| 17 | **Tłumaczenia UI (5 nowych)** | **Wygenerowane** OpenAI (`gpt-4o-mini`, ~45k tokenów): `values-it/ja/ko/tr/vi/strings.xml`. Audyt przed release. |
| 18 | **Czasy podstawowe** | Tabela §13.4 — per język nauki. |
| 19 | **Etykiety czasów** | `tense_label_lang`: **`app_lang`** (domyślnie) lub `learning_lang`. |
| 20 | **Ustawienia + karta** | Zależne od `learning_lang` — §13.6. |
| 21 | **Gotowość** | Spec ✅ / kod ❌ — §15. |

**Podział odpowiedzialności:**
- **Enrichment (backend / LLM)** → generuje i zapisuje **komplet** morfologii + metadane językowe; glossy i `examples[].l1` w języku **`app_lang`** z profilu.
- **UI (Android)** → `values-{app_lang}/strings.xml` dla chrome aplikacji; **filtruje wyświetlanie** inflection (domyślne czasy / przypadki w practice).

---

## 1. Streszczenie wykonawcze

Vocabulario buduje karty słówek przez pipeline **lookup → enrichment (LLM) → cache → karta użytkownika**. Obecny kod (generyczny prompt + ~25 `LanguagePack`) **zostanie usunięty** i zastąpiony systemem **LSP (Language Spec Package)** dla **dokładnie 15 języków L2**.

Każdy język dostaje:
- dedykowane prompty (lookup, core, examples, **inflection**, similar, correction),
- pełną specyfikację morfologii (czasy, przypadki, formy — **bez skrótów**),
- walidatory strukturalne po LLM,
- golden tests.

**Oczekiwany efekt:** przewidywalna, kompletna karta słowa — od A2 po C2 — bez halucynacji paradigmatów i bez „pustych” tabel z placeholderami.

---

## 2. Kontekst biznesowy

### 2.1 Problem, który rozwiązujemy

| Problem | Skutek |
|--------|--------|
| Jeden prompt „dopasuj się do L2” | Błędne odmiany (np. PL present z m/ż), placeholdery `—` |
| Niepełna morfologia | Użytkownik C2 nie ma dostępu do rzadkich czasów / przypadków |
| 25 języków bez specyfikacji | Nierówna jakość, trudne testowanie |
| Brak walidacji po LLM | Zła treść w cache |

### 2.2 Cele produktowe

1. **Kompletność danych** — karta = maksimum użytecznej wiedzy o lemacie w danym L2.
2. **Uszczelnienie** — LSP + walidatory; zero placeholderów; poprawne paradigmy per język.
3. **15 języków zrobionych porządnie** — nie 25 „na skróty”.
4. **Czysty start techniczny** — jeden kontrakt, jeden pipeline, bez legacy.

### 2.3 Poza scope

- 16. język L2 / `app_lang` bez pełnego LSP + pełnego `strings.xml`.
- Migracja / wsparcie starych formatów JSON.
- Weryfikacja „czy użytkownik naprawdę jest native speakerem X”.

---

## 3. Stan obecny (do usunięcia)

Poniższe traktujemy jako **referencję historyczną** — **nie utrzymujemy** po wdrożeniu LSP.

| Element | Plik / miejsce | Działanie |
|---------|----------------|-----------|
| Prompty v1 | `backend/app/ai/prompts/v1.py` | **Usunąć** |
| `conjugation.py` + `CONJUGATION_*` | `backend/app/ai/conjugation.py` | **Zastąpić** `lsp/inflection` |
| `language_packs.py` (25 j.) | `backend/app/ai/language_packs.py` | **Zastąpić** `lsp/{code}/manifest.yaml` |
| `language_typology.py` (hinty) | wchłonięte do LSP | **Uprościć / usunąć** |
| `schema_version: "1.0"`, pole `conjugation` | content JSON | **Zastąpić** nowym schematem + `inflection` |
| `SUPPORTED_LEARNING_LANGS` (25) | Android `Constants.kt` | **15 języków** |
| `SUPPORTED_UI_LANGS` (10) + `native_lang` / `ui_lang` | Android + backend | **Scalić w `app_lang`**; **15** pełnych `strings.xml` |
| `LanguagePacks.kt` (lustro BE) | Android | **Generowane z LSP** lub jeden manifest |
| `vocabulario.adaptive.v1`, `import_display.v1` | osobna decyzja | Import może zostać, ale **bez** starych pól koniugacji |

---

## 4. Propozycja docelowa (to-be)

### 4.1 Zasady projektowe

1. **`SUPPORTED_L2_LANGS`** — dokładnie 15 kodów; API odrzuca inne (`400`).
2. **LSP per język** — manifest + prompty + walidatory + fixtures.
3. **Inflection = pełny zestaw** — manifest definiuje **wszystkie** kategorie morfologiczne obowiązkowe dla POS; prompt wymusza wypełnienie; walidator sprawdza kompletność (nie skrócony podzbiór).
4. **Deklinacja nominalna** — tam gdzie język ma przypadki: **pełna tabela** dla lematu (wszystkie przypadki × liczby, z uwzględnieniem rodzaju / klasy deklinacji).
5. **UI ≠ enrichment** — ustawienia użytkownika (`selected_tenses`, `selected_cases`) dotyczą **tylko widoku**; JSON karty zawsze pełny.
6. **Hard cutover** — brak fallbacku na v1, brak migracji DB pod stary format.
7. **Wersjonowanie LSP** (`lsp_version`) — dla przyszłych poprawek promptów w dev.
8. **Dwa języki użytkownika** — `app_lang` + `learning_lang`; żadnych innych pól językowych w profilu.

### 4.2 Model językowy użytkownika (rev. 3)

```
Użytkownik
├── app_lang      ← język aplikacji (UI + glossy L1 na kartach)
│                 domyślnie: locale telefonu (jeśli ∈ 15), else en
│                 zmiana: Ustawienia → Język aplikacji
└── learning_lang ← język, którego się uczy (lemma, inflection, przykłady L2)
                  zmiana: onboarding / Ustawienia → Język nauki
```

**Co znika w kodzie i API:**
- `native_lang` jako osobne pole → **`app_lang`**
- `ui_lang` na `User` → **usunąć** (duplikat)
- Etykiety w UI typu „język ojczysty” → **„Język aplikacji”**
- Logika „zsynchronizuj ui_lang z native_lang” → **jedno pole**

**Backend / enrichment:**
- `lang_pair_key(app_lang, learning_lang)` w cache — ta sama idea, inna nazwa pola.
- Prompty: *„Pisz gloss_l1 i tłumaczenia przykładów w języku {app_lang}”*.
- Nie pytamy użytkownika o „native” — tylko o **`app_lang`**.

### 4.3 Model warstwowy (dane karty)

```
┌──────────────────────────────────────────────────┐
│  Card Schema (vocabulario.card.v1) — jedyny     │
├──────────────────────────────────────────────────┤
│  inflection — PEŁNA morfologia (verbs + nouns…) │
│  language_specific — pinyin, root, aspect, …      │
├──────────────────────────────────────────────────┤
│  LSP × 15 — manifest + prompty + walidatory     │
├──────────────────────────────────────────────────┤
│  UI display prefs (nie wpływają na enrichment)    │
└──────────────────────────────────────────────────┘
```

### 4.4 Pipeline (nowy)

```
lookup(lsp) → core(lsp) → examples(lsp) → inflection(lsp) → similar(lsp)
    → validate_all(lsp) → lexical_entries.content → learning_card
```

Każdy krok: **structured output** + walidator LSP. Retry 1× z błędem walidacji → `enrichment_failed`.

### 4.5 Zasada „pełnych danych” (inflection + deklinacja)

| Warstwa | Odpowiedzialność |
|---------|------------------|
| **Manifest LSP** | Lista **wszystkich** tense_key / case_key / form_key obowiązkowych per POS |
| **Prompt inflection** | „Wypełnij **każdy** klucz z manifestu rzeczywistą formą lub **pomiń całą kategorię** jeśli gramatycznie niemożliwa (np. PL perfective + present)” |
| **Walidator** | Sprawdza zgodność z manifestem i regułami gramatycznymi; **zakaz** `—`, pustych stringów, obcych siatek osobowych |
| **Karta JSON** | Przechowuje komplet |
| **Android** | Domyślnie pokazuje podzbiór; użytkownik może włączyć wszystko (Settings → wszystkie czasy / wszystkie przypadki) |

---

## 5. Lista 15 języków — L2 nauki **i** język aplikacji (`app_lang`)

Ta sama lista kodów ISO dla **`learning_lang`** i **`app_lang`**. Użytkownik może np. mieć `app_lang=ja` i `learning_lang=zh` — system nie ocenia, czy to „ma sens”.

| # | Kod | Język (endonim) | Uwagi |
|---|-----|-----------------|-------|
| 1 | `en` | English | fallback domyślny |
| 2 | `es` | Español | |
| 3 | `fr` | Français | |
| 4 | `de` | Deutsch | |
| 5 | `it` | Italiano | **nowy** pełny `strings.xml` |
| 6 | `pt-br` | Português (Brasil) | osobny kod API + osobny prompt LSP |
| 7 | `pt-pt` | Português (Portugal) | osobny kod API + osobny prompt LSP |
| 8 | `zh` | 中文 | |
| 9 | `ja` | 日本語 | **nowy** pełny `strings.xml` |
| 10 | `ko` | 한국어 | **nowy** pełny `strings.xml` |
| 11 | `ar` | العربية | RTL |
| 12 | `ru` | Русский | |
| 13 | `hi` | हिन्दी | |
| 14 | `tr` | Türkçe | **nowy** pełny `strings.xml` |
| 15 | `vi` | Tiếng Việt | **nowy** pełny `strings.xml` |
| 16 | `pl` | Polski | język produktu / dev |

**Uwaga:** po rozdzieleniu portugalskiego lista ma **16 kodów** (jedyny wyjątek od pierwotnej „15” — za Twoją decyzją).

**Nie wchodzą:** `nl`, `sv`, `no`, `da`, `fi`, `el`, `cs`, `th`, `id`, `he`, `uk`, `ur`, `bn`, …

### 5.1 Scope featurea: pełne słowniki UI (16 ×)

W ramach **tego samego featurea LSP** dostarczamy kompletne tłumaczenia interfejsu.

**Ile to jest tekstów?** W repozytorium jest **349 kluczy** `string` na język (np. `practice_title`, `settings_save`). Wcześniej podałem ~700 — **to był błąd**; przepraszam. Dla 5 nowych języków interfejsu = ok. **5 × 349 ≈ 1 745** nowych tłumaczeń.

| Artefakt | Opis | Lokalizacja |
|----------|------|-------------|
| **String resources** | Wszystkie klucze `R.string.*` | `res/values-{code}/strings.xml` × 16 |
| **POS labels** | noun, verb, adj, … | `POS_LABELS` × 16 |
| **Etykiety czasów / przypadków** | Z manifestu LSP | `lsp/ui_labels/{code}.yaml` → skrypt |
| **RTL** | Arabski | manifest + testy |
| **Test kompletności** | CI: każdy klucz wzorca w 16 językach | `scripts/check_ui_strings.py` |

| Kod | `strings.xml` dziś | W featurezie |
|-----|-------------------|--------------|
| en, es, fr, de, pt, zh, hi, ar, ru, pl | istnieją (349 kluczy) | audyt; `pt` → etykiety `pt-br` / `pt-pt` |
| it, ja, ko, tr, vi | **wygenerowane** (rev. 5) | audyt jakości + `check_ui_strings.py` |

**Domyślny `app_lang`:** język telefonu jeśli jest na liście 16, inaczej angielski.

### 5.2 Rozszerzenia karty per język nauki

Pełne dane zawsze w JSON; poniżej — dodatkowe pola i sekcje UI (benchmark: Duolingo, Pleco, Anki).

| Język | Dodatkowe dane | Wygląd karty |
|-------|----------------|--------------|
| **en** | phrasal verbs, nieregularności | sekcja irregular |
| **es** | vosotros, ser/estar | siatka 2. os. lm. |
| **fr** | liaison, elision | adnotacje fonetyczne |
| **de** | rozdzielny przedimek, rodzajnik | linia „przedimek” |
| **it** | — | standard romance |
| **pt-br** | você/tu, odmiana BR | badge „Brasil” |
| **pt-pt** | bezokolicznik osobowy | tabela infinitivo pessoal |
| **zh** | pinyin z tonami, tradycyjne znaki, klasyfikatory | znaki + pinyin; przełącznik uproszczone/tradycyjne |
| **ja** | kana, romaji (opcja), keigo | kanji + kana; romaji z ustawień |
| **ko** | poziomy grzeczności, partykuły | macierz końcówek |
| **ar** | arabski książkowy, harakat, korzeń | RTL; korzeń; forma z diakrytykami |
| **ru** | aspekt, para aspektowa | badge aspektu |
| **hi** | dewanagari + IAST | oba zapisy obok siebie |
| **tr** | harmonia samogłosek | rozbicie aglutynacji |
| **vi** | 6 tonów, klasyfikatory, północ | lemma z tonami |
| **pl** | aspekt | bez zmian vs spec |

### 5.3 (archiwum) Skąd wzięła się myląca „fazowość”

Wcześniejsza sugestia etapów i języków spoza listy 15 **odrzucona** w rev. 3 i **11**. Nie stosujemy.

## 6. Kontrakt karty (`schema_version: "vocabulario.card.v1"`)

Jedyny format contentu karty słownikowej (zastępuje `1.0` + `conjugation`):

```json
{
  "schema_version": "vocabulario.card.v1",
  "lsp_version": "pl-1.0.0",
  "lemma": "…",
  "language": "pl",
  "pos": "verb",
  "ipa": "…",
  "headword_note": null,
  "ui_hints": {
    "script": "Latn",
    "rtl": false,
    "inflection_kind": "person_tense|agglutinative|root_pattern|particles|analytic",
    "has_gender": true,
    "has_articles": false,
    "has_aspect": true,
    "has_cases": true
  },
  "meanings": [ "…" ],
  "synonyms_l2": [],
  "antonyms_l2": [],
  "similar_words": [],
  "inflection": {
    "verbs": { "tenses": {}, "non_finite": {} },
    "nouns": { "declension": {}, "plural": {} },
    "adjectives": { "declension": {}, "comparison": {} },
    "adverbs": {},
    "pronouns": {},
    "periphrases": []
  },
  "language_specific": {},
  "notes": null,
  "confidence": 0.95
}
```

- Pole **`inflection`** zastępuje **`conjugation`** — obejmuje **czasowniki, rzeczowniki, przymiotniki** i inne kategorie z manifestu LSP.
- Struktura wewnętrzna `inflection` **różni się per język** (walidowana przez JSON Schema z LSP).
- `ui_hints` **nie ogranicza** enrichment — tylko podpowiada UI (skrypt, RTL, rodzaj tabeli).

---

## 7. Specyfikacja karty per język — **pełne dane enrichment**

Poniżej: co **musi** wygenerować enrichment (nie: co domyślnie pokazuje UI).  
Zasada: **wszystkie wymienione kategorie** — realne formy, bez placeholderów. Jeśli kategoria gramatycznie nie istnieje dla lematu → **brak klucza**, nie pusta tabela.

---

### 7.1 English (`en`)

| Obszar | Pełne dane na karcie |
|--------|----------------------|
| Lemma | czasownik bez „to”; rzeczownik bez article w headword |
| IPA | British + American w `language_specific.variants` |
| **Verbs — wszystkie czasy** | present_simple, present_continuous, present_perfect, present_perfect_continuous, past_simple, past_continuous, past_perfect, past_perfect_continuous, future_simple (will), future_continuous, future_perfect, future_perfect_continuous, going_to (present/past/future), conditionals (zero, first, second, third, mixed) |
| **Osoby** | I, you, he/she/it, we, you, they — w każdym czasie osobowym |
| **Non-finite** | bare_infinitive, to_infinitive, present_participle (-ing), past_participle |
| **Nouns** | countable/uncountable, plural (regular + irregular), possessive ('s / ') |
| **Adjectives** | comparative, superlative (regular + irregular); gradable vs non-gradable |
| **Pronouns** | personal, possessive, reflexive — jeśli lemat to pronoun |

---

### 7.2 Spanish (`es`)

| Obszar | Pełne dane |
|--------|------------|
| **Wszystkie czasy** | presente, pretérito perfecto, pretérito indefinido, pretérito imperfecto, pretérito pluscuamperfecto, futuro simple, futuro perfecto, condicional simple, condicional compuesto, presente de subjuntivo, imperfecto de subjuntivo, pluscuamperfecto de subjuntivo, futuro de subjuntivo, imperativo afirmativo, imperativo negativo |
| **Non-finite** | infinitivo, gerundio, participio (w tym compuesto gdzie dotyczy) |
| **Osoby** | yo, tú, vos (gdzie regionalnie), él/ella/usted, nosotros, vosotros, ellos/ellas/ustedes |
| **Nouns** | gender, article, **pełna deklinacja** (sg/pl × 4 przypadki tam gdzie forma się różni — ES: mainly article + noun form; pełny paradigm sg/pl) |
| **Adjectives** | gender agreement forms, short forms, superlative (ísimo) |
| **Verbs** | stem_change_type, spelling_change, auxiliary (haber/ser/estar), reflexive (se) |
| **Periphrases** | idiomatyczne dla lematu (tener que, acabar de, …) |

---

### 7.3 French (`fr`)

| Obszar | Pełne dane |
|--------|------------|
| **Czasy** | présent, passé composé, imparfait, plus-que-parfait, passé simple (literary — **tak, dla C2**), passé antérieur, futur simple, futur antérieur, conditionnel présent, conditionnel passé, subjonctif présent, subjonctif passé, impératif |
| **Non-finite** | infinitif, participe présent, participe passé, gérondif |
| **Osoby** | je, tu, il/elle, nous, vous, ils/elles |
| **Nouns** | gender, article, **pełna deklinacja** (sg/pl; liaison notes) |
| **Adjectives** | feminine, plural, irregular (beau/bel, …) |
| **Verbs** | groupe, auxiliary (avoir/être), pronominal |

---

### 7.4 German (`de`)

| Obszar | Pełne dane |
|--------|------------|
| **Czasy** | Präsens, Präteritum, Perfekt, Plusquamperfekt, Futur I, Futur II, Konjunktiv I, Konjunktiv II, Imperativ |
| **Non-finite** | Infinitiv, Partizip I, Partizip II |
| **Osoby** | ich, du, er/sie/es, wir, ihr, sie/Sie |
| **Nouns** | genus, **pełna deklinacja: 4 przypadki × 2 liczby** (Nominativ, Akkusativ, Dativ, Genitiv) |
| **Adjectives** | weak/strong/mixed declension — pełna tabela przy przykładowym noun |
| **Verbs** | auxiliary, separable prefix, Modalverben patterns, vowel change |

---

### 7.5 Italian (`it`)

| Obszar | Pełne dane |
|--------|------------|
| **Czasy** | presente, passato prossimo, imperfetto, trapassato prossimo, passato remoto, trapassato remoto, futuro semplice, futuro anteriore, condizionale presente, condizionale passato, congiuntivo presente, congiuntivo imperfetto, congiuntivo passato, congiuntivo trapassato, imperativo |
| **Non-finite** | infinito, gerundio, participio |
| **Nouns** | gender, article, **pełna deklinacja** (sg/pl; IT: głównie article + forma rzeczownika) |
| **Adjectives** | gender/number agreement, comparativo, superlativo |

---

### 7.6 Portuguese (`pt`)

| Obszar | Pełne dane |
|--------|------------|
| Wariant | `language_specific.variant`: `pt-BR` / `pt-PT` (obie formy gdzie się różnią) |
| **Czasy** | presente, pretérito perfeito, pretérito imperfeito, pretérito mais-que-perfeito, futuro do presente, futuro do pretérito, condicional, imperativo, conjuntivo presente, conjuntivo imperfeito, conjuntivo futuro, conjuntivo perfeito, conjuntivo mais-que-perfeito |
| **Non-finite** | infinitivo, gerúndio, particípio |
| **Nouns** | gender, article, pełna deklinacja sg/pl |
| **Personal infinitive** | **tak** — pełna tabela (charakterystyczne dla PT) |

---

### 7.7 Chinese — Mandarin (`zh`)

| Obszar | Pełne dane |
|--------|------------|
| Lemma | simplified (Hans); `language_specific.traditional` |
| **Pinyin** | z tonami (obowiązkowe) |
| **Verbs** | aspekt: 了 / 过 / 着 / 在 — **wszystkie kombinacje istotne** dla lematu z przykładami; resultative / directional complements |
| **Nouns** | **classifiers** (pełna lista typowych dla lematu), 个/张/… |
| **Numerals + measure** | przykładowe konstrukcje liczebnik + classifier + noun |
| **Aspect / modality particles** | 吗, 呢, 吧, 啊 — w `language_specific` z przykładami |
| Brak | tabela osób IE — **nie generować** |

---

### 7.8 Japanese (`ja`)

| Obszar | Pełne dane |
|--------|------------|
| Lemma + **kana** + **romaji** (opcjonalnie) |
| **Verb forms** | dictionary, masu (polite), plain, negative (plain/polite), past (plain/polite), te-form, ta-form, potential, passive, causative, causative-passive, imperative, conditional (ば / たら / なら / と), volitional |
| **Honorific register** | 尊敬語 / 謙譲語 / 丁寧語 — formy kluczowe dla C2 w `language_specific.keigo` |
| **Adjectives** | i-adj / na-adj — pełna odmiana (kū vs shī) |
| **Nouns** | counters (全 relevant classifiers) |

---

### 7.9 Korean (`ko`)

| Obszar | Pełne dane |
|--------|------------|
| **Verb endings** | declarative (formal/informal), interrogative, imperative, propositive; past, future; honorific (시), modest, … |
| **Honorific levels** | **pełna macierz** dla C2 (해요체, 합니다체, 하오체, 하게체, 한다체, …) — w manifest |
| **Nouns** | particles (이/가, 을/를, 에, 에서, …) z przykładami dla lematu |
| **Numbers** | native vs sino-korean z lematem |

---

### 7.10 Arabic (`ar`)

| Obszar | Pełne dane |
|--------|------------|
| MSA | standard |
| **Vocalized forms** | tashkeel dla kluczowych form |
| **Verbs** | past (perfect), present (imperfect), jussive, subjunctive, imperative; **passive** voice; **Form I–X** |
| **Osoby** | pełna macierz 1/2/3 × sg/pl × gender |
| **Nouns** | gender, **pełna deklinacja** (3 przypadki × 2 liczby × definite/indefinite) |
| **Broken plurals** | wszystkie wzorce dla lematu |
| **Root** | ج-ذ-ب w `language_specific` |

---

### 7.11 Russian (`ru`)

| Obszar | Pełne dane |
|--------|------------|
| **Aspect** | perfective / imperfective (obowiązkowe) |
| **Verbs** | present (tylko impf.), past (gender/number), future (simple/compound), imperative, conditional (бы), active participles, passive participles, gerund (deeprichastie) |
| **Nouns** | **pełna deklinacja: 6 przypadków × sg/pl** |
| **Adjectives** | pełna deklinacja jako przymiotnik i jako przymiotnikowy zaimek |
| **Short forms** | krótkie formy przymiotnika |

---

### 7.12 Hindi (`hi`)

| Obszar | Pełne dane |
|--------|------------|
| Devanagari + **romanization** (jeden standard IAST) |
| **Verbs** | present habitual, present progressive, present perfect, past habitual, past progressive, past perfect, future, subjunctive, imperative; **ergative** alignment w past |
| **Osoby** | sg/pl × 3 + honorific (आप) |
| **Nouns** | gender, **pełna deklinacja** (direct/oblique × sg/pl) |
| **Postpositions** | zestaw z przykładami |

---

### 7.13 Turkish (`tr`)

| Obszar | Pełne dane |
|--------|------------|
| **Verbs** | aorist, progressive, past (dı/di/du/dü), future, inferential (miş), conditional, necessitative, ability, optative, imperative |
| **Osoby** | ben, sen, o, biz, siz, onlar |
| **Nouns** | **pełna deklinacja** (6 przypadków × sg/pl) |
| **Vowel harmony** | walidator |
| **Agglutination chain** | rozbicie na morfemy w `language_specific` dla C2 |

---

### 7.14 Vietnamese (`vi`)

**Typ:** izolujący, **tony**, **classifiers**, brak koniugacji osóbowej jak w ES.

| Obszar | Pełne dane |
|--------|------------|
| Lemma | z pełnymi znakami diakrytycznymymi (tony) |
| **IPA / tone** | `language_specific.tone_pattern` (np. ma, má, mà, mã, mạ) |
| **Verbs** | **không odmiana osobowa** — zamiast tego: aspekt / czas przez **auxiliaries** (đã, đang, sẽ, vừa, mới) × **wszystkie kombinacje** istotne dla lematu |
| **Serial verb constructions** | dla czasowników wieloczłonowych |
| **Nouns** | **classifiers** (con, cái, chiếc, người, …) — pełna lista dla lematu |
| **Pronouns** | system kinship / formality (tôi, tao, mình, anh, chị, …) w `language_specific` |
| **Regional** | `language_specific.register`: Northern vs Southern variants gdzie różne |
| **Adjectives** | pozycja (trước/sau noun), reduplikacja |
| Brak | tabela yo/tú / placeholder conjugation |

---

### 7.15 Polish (`pl`) — referencyjna jakość

| Obszar | Pełne dane |
|--------|------------|
| **Aspect** | perfective / imperfective / biaspectual — obowiązkowe |
| **Verbs — wszystkie tryby/czasy** | teraźniejszy (tylko impf.), przeszły, przyszły (złożony + prosty), rozkazujący, przypuszczający, **imiesłów przyszły / przeszły**, bezokolicznik |
| **Osoby** | pełne siatki per czas (present: ja…one bez m/ż; past: pełna siatka m/ż) |
| **Nouns** | **pełna deklinacja: 7 przypadków × sg/pl** + vocative gdzie żywy |
| **Adjectives** | **pełna deklinacja** (hard/soft; per case/number/gender) |
| **Numerals** | odmiana z rzeczownikiem (jeśli lemat = liczebnik) |
| **Aspect pair** | link do pary dokonana/niedokonana w `language_specific` |
| **Zasady** | perfective → brak teraźniejszego; **zero placeholderów** |

---

## 8. Architektura LSP

### 8.1 Struktura katalogów

```
backend/app/lsp/
  registry.py
  loader.py
  shared/schemas/
  en/manifest.yaml + prompts/ + validators/ + fixtures/
  …
  vi/manifest.yaml
  pl/manifest.yaml
```

### 8.2 Manifest — przykład pól (`manifest.yaml`)

```yaml
code: pl
name_en: Polish
script: Latn
inflection_kind: person_tense

verbs:
  required_tenses:
    - czas_terazniejszy      # only imperfective
    - czas_przeszly
    - czas_przyszly
    - tryb_rozkazujacy
    - tryb_przypuszczajacy
  non_finite:
    - bezokolicznik
    - imieslow_przeszly
    - imieslow_przyszly
  person_grids:
    czas_terazniejszy: [ja, ty, on, ona, ono, my, wy, oni, one]
    czas_przeszly: [ja_m, ja_f, ty_m, ty_f, on, ona, ono, my_mv, my_fv, wy_mv, wy_fv, oni, one]

nouns:
  cases: [mianownik, dopełniacz, celownik, biernik, narzędnik, miejscownik, wołacz]
  numbers: [sg, pl]
  gender: [m_personal, m_animate, m_inanimate, f, n]

adjectives:
  full_declension: true
```

### 8.3 Prompty

| Krok | Wymaganie |
|------|-----------|
| **inflection** | „Wygeneruj **wszystkie** klucze z manifestu. C2-complete. Bez skracania.” |
| **core** | POS, znaczenia, ipa, `language_specific` |
| **correction** | reguły LSP + pełna weryfikacja zgłoszeń |

Structured output: JSON Schema **per L2 × step**, generowana z manifestu.

### 8.4 Walidacja

- Kompletność względem manifestu (dla danego POS).
- Reguły gramatyczne (PL aspect, RU present, VI no person table).
- Brak placeholderów.
- Retry → fail.

---

## 9. Zmiany techniczne — inventarz (bez legacy)

### 9.1 Backend — **zastąpić / usunąć**

| Akcja | Szczegóły |
|-------|-----------|
| **Usunąć** | `prompts/v1.py`, stary `conjugation.py`, stary `language_packs.py` (25 j.), `language_typology.py` (jeśli wchłonięte) |
| **Nowe** | `backend/app/lsp/**` — jedyny system promptów |
| **Nowe** | `enrichment.py` — tylko LSP pipeline |
| **Nowe** | `inflection` w JSON zamiast `conjugation` |
| **API** | `learning_lang in SUPPORTED_L2_LANGS` — hard reject |
| **Cache** | `lexical_entries.content` tylko `vocabulario.card.v1` |
| **Testy** | 15 × golden; CI gate 100% |

### 9.2 Android — **zastąpić**

| Akcja | Szczegóły |
|-------|-----------|
| `SUPPORTED_LEARNING_LANGS` | dokładnie 15 (z `vi`, bez `nl` i reszty) |
| `SUPPORTED_APP_LANGS` | **te same 15** kodów co L2 |
| `native_lang` + `ui_lang` | **Scalić w `app_lang`**; jeden picker w ustawieniach |
| `LanguagePacks` | z manifestu LSP (codegen) |
| **15 × `strings.xml`** | pełne słowniki UI + CI check kompletności |
| `FlashcardBackContent` | render `inflection` (verbs + nouns + adj) |
| **Display prefs** | `selected_tenses`, `selected_cases` — **tylko UI**, nie wpływają na API enrichment |
| **Usunąć** | parsowanie `conjugation`, stare klucze ES-only |

### 9.3 DevOps

- `scripts/lsp_sync.py` — manifest → Kotlin + JSON Schema.
- E2E: 15 × (verb, noun, adj) golden smoke.
- Monitoring tokenów (pełna morfologia = wyższy koszt LLM — budżetować).

---

## 10. Plan implementacji (jedno wdrożenie — wszystkie 15)

Sekcja „Faza 0/1/2” poniżej to **kolejność prac wewnętrznych** (spec → kod → QA), **nie** wydawanie produktu kawałkami. **Definition of Done** featurea = komplet dla **wszystkich 15** języków naraz.

### Checklist DoD

**Spec i kontrakt**
- [x] Lista 15 języków (`vi`, nie `nl`)
- [x] Pełna morfologia + hard cutover
- [x] 15 UI = 15 L2; `app_lang` zamiast native/ui
- [x] Bez etapów językowych — wszystkie 15 w jednym release
- [ ] Manifest template + JSON Schema `vocabulario.card.v1`
- [ ] Master list kluczy `strings.xml` + `check_ui_strings.py`
- [ ] Rozstrzygnięcia z §13 (pt, ar, codegen, split inflection, import)

**Backend — wszystkie 15 LSP**
- [ ] LSP registry + loader
- [ ] 15 × manifest + prompty + walidatory + golden tests
- [ ] Nowy enrichment end-to-end (bez starego kodu)
- [ ] Usunięcie: `prompts/v1`, `conjugation`, 25-lang packs

**Android — wszystkie 15**
- [ ] `app_lang` (rename), `SUPPORTED_*` = 15 kodów
- [ ] 15 × pełne `strings.xml` + POS labels + etykiety LSP
- [ ] Render pełnego `inflection` + display prefs
- [ ] Usunięcie: `ui_lang`, `conjugation`, stare klucze ES-only

**QA i koszty**
- [ ] Checklist QA × 15 języków (LSP + UI locale)
- [ ] Profilowanie kosztu tokenów (pełna morfologia)
- [ ] E2E smoke: 15 × (verb, noun, adj)

---

## 11. Ryzyka

| Ryzyko | Mitigacja |
|--------|-----------|
| Rozmiar JSON / tokeny LLM | Podział inflection na verb / noun / adj step; streaming merge |
| Jakość AR/HI/ZH | Native review fixtures; iteracja LSP |
| VI regionalizm | Oznaczanie wariantu w `language_specific` |
| Złożoność 15 × pełnych manifestów | YAML + codegen; wspólne fragmenty promptów |

---

## 12. KPI

| KPI | Cel |
|-----|-----|
| Validator pass rate | > 97% |
| Correction rate (inflection) | < 2% kart |
| Golden tests | 100% × 15 L2 |
| Czas enrichment (verb PL, pełny) | < 90 s (szac.; do pomiaru) |

---

## 13. Decyzje zatwierdzone (rev. 4)

| # | Temat | Decyzja |
|---|-------|---------|
| 1 | Portugalski | **`pt-br` i `pt-pt`** — osobne kody, prompty, API. Lista **16 języków**. |
| 2 | Arabski | **Tylko arabski książkowy** (jak Duolingo) — bez dialektów. |
| 3 | Chiński | Uproszczone + tradycyjne na karcie; rozszerzony layout — §5.2. |
| 4 | Wietnamski | Północny standard + tony na lemacie. |
| 5 | Hindi | Dewanagari + zapis łaciński IAST. |
| 6 | Japoński | Kana zawsze; romaji opcjonalnie w ustawieniach. |
| 7 | LSP → Android | **Skrypt** `lsp_sync.py`. |
| 8 | Odmiana w modelu | **Jedno zapytanie** — test §13.3. |
| 9 | Import | **Przepisać** pod nowy format karty; **usunąć** stare. |
| 10 | Wzorzec tłumaczeń UI | **Angielski** — §13.2. |
| 11 | 5 nowych języków UI | **Zrobione (rev. 5):** it, ja, ko, tr, vi — po 349 kluczy. Audyt przed produkcją. |
| 12 | Profile | **Dowolna liczba** par; osobne listy/karty; przeładowanie app. |
| 13 | Widok odmiany | Filtr czasów z ustawień — §13.1. |
| 14 | Koszt OpenAI | **Jakość**; oszczędność przez 1 zapytanie + cache. |

### 13.1 „Pełna odmiana” vs to, co widać na ekranie

**Nie ma dwóch trybów.** Są dwa poziomy:
1. **W danych karty** — model generuje całą odmianę.
2. **Na ekranie** — **Ustawienia → Wybrane czasy** filtruje, co pokazać na tyle fiszki (lista, szczegół, ćwiczenia — ten sam filtr).

**Ćwiczenia** = quiz (zgadnij / wpisz). **Nauka** = przewijanie kart. Oba używają tego samego widoku tyłu karty.

### 13.2 Wzorzec tłumaczeń interfejsu (punkt 10)

Jeden plik wzorcowy (`values-en/strings.xml`). Automat sprawdza, czy **wszystkie 349 kluczy** są w każdym z 16 języków. Brak klucza = błąd w CI.

### 13.3 Test: 1 vs 3 zapytania o odmianę

Słowa: `rzucić`, `hablar`, `كتب`. Wynik: **11 891** tokenów (1×) vs **23 741** (3×). **Decyzja: 1 zapytanie.** Szczegóły: `docs/inflection-shot-test-results.json`.

### 13.4 Czasy „podstawowe” (domyślnie zaznaczone w ustawieniach)

Przy **nowym profilu** lub pustym `selected_tenses` — poniższe klucze. Użytkownik może zmienić w ustawieniach. Źródło prawdy po wdrożeniu LSP: `manifest.yaml` → `default_selected_tenses`.

| Język | Domyślnie widoczne czasy / sekcje | Uwagi |
|-------|-----------------------------------|-------|
| **en** | `present_simple`, `past_simple`, `present_continuous` | |
| **es** | `presente`, `preterito_indefinido`, `preterito_imperfecto` | |
| **fr** | `present`, `passe_compose`, `imparfait` | |
| **de** | `prasens`, `perfekt`, `prateritum` | |
| **it** | `presente`, `passato_prossimo`, `imperfetto` | |
| **pt-br** | `presente`, `preterito_perfeito`, `preterito_imperfeito` | jak BR |
| **pt-pt** | `presente`, `preterito_perfeito`, `preterito_imperfeito` | + sekcja infinitivo pessoal na karcie |
| **pl** | `czas_terazniejszy`, `czas_przeszly` | bezokolicznik w non_finite |
| **ru** | `nastoyashchee`, `proshedshee` | |
| **ar** | `perfect`, `imperfect` | arabski książkowy |
| **tr** | `simdi_zaman`, `gecmis_zaman` | |
| **hi** | `present`, `past` | |
| **ja** | `polite_nonpast`, `polite_past`, `te_form` | |
| **ko** | `polite_present`, `polite_past` | |
| **zh** | *brak tabeli czasów* | domyślnie: **pinyin + klasyfikatory + aspekt** (sekcje z §5.2) |
| **vi** | *brak tabeli czasów* | domyślnie: **tony + klasyfikatory** |

Dla **zh** i **vi** w ustawieniach zamiast „Wybrane czasy” pokazujemy **„Sekcje karty”** (tony, klasyfikatory, aspekt itd.) — zależne od manifestu LSP.

### 13.5 Etykiety czasów: język aplikacji vs język nauki

Nowe pole ustawień: **`tense_label_lang`** ∈ `{ app_lang, learning_lang }`, **domyślnie `app_lang`**.

| Wartość | Przykład (app=pl, nauka=es) | Etykieta „Pretérito indefinido” |
|---------|------------------------------|----------------------------------|
| `app_lang` | polski | „Czas przeszły prosty” (z `lsp/ui_labels/pl.yaml`) |
| `learning_lang` | hiszpański | „Pretérito indefinido” (z manifestu ES) |

Implementacja:
- Android: `SettingsScreen` — przełącznik; `FlashcardBackContent` / `CardDetailContent` — `tenseLabel()` bierze `app_lang` lub `learning_lang` z profilu.
- Backend: opcjonalnie zapis w `UserSettings` (globalne) lub `LanguageProfile` (per para).
- **Rekomendacja:** per **profil** (`LanguageProfile.tense_label_lang`) — spójne z `selected_tenses`.

### 13.6 Ustawienia i karta — zależność od `learning_lang`

Ekran **Ustawienia** i **tył karty** muszą reagować na aktywny język nauki:

| Element | Zachowanie |
|---------|------------|
| **Wybrane czasy** | Katalog z `LanguagePacks` / LSP dla `learning_lang`; ukryte gdy język bez odmiany (zh, vi). |
| **Sekcje karty (zh/vi)** | Osobny picker sekcji z manifestu (pinyin, klasyfikatory, tony…). |
| **Layout karty** | `ui_hints.inflection_kind` + §5.2 — np. RTL dla `ar`, kanji+kana dla `ja`, korzeń dla `ar`. |
| **Ćwiczenia** | Ten sam filtr co tył karty; kierunek tłumaczenia bez zmian. |
| **Zmiana profilu** | Przeładowanie app (Twoja decyzja #12) — przeładowanie katalogów czasów i layoutu. |

**Stan kodu dziś:** `LanguagePacks` i `SettingsScreen` częściowo to robią, ale:
- katalog jest na sztywno w Kotlin (25 języków, nie 16),
- brak `tense_label_lang`,
- zh/vi mają `showConjugationDefault = false` bez alternatywnego pickera sekcji,
- layout karty nie ma jeszcze bloków per §5.2.

---

## 14. Podsumowanie

**16 języków**, **16 słowników UI** (5 nowych wygenerowanych), **16 pakietów LSP**, jedno wdrożenie. Specyfikacja rev. 5 **zamknięta** — start kodu od §15.

---

## 15. Gotowość do implementacji (przegląd kodu 2026-08-05)

### 15.1 Co jest gotowe (spec + przygotowanie)

| Obszar | Status |
|--------|--------|
| Decyzje produktowe (§0, §13) | ✅ Zamknięte |
| Lista 16 języków + rozszerzenia karty (§5.2) | ✅ |
| Czasy podstawowe (§13.4) | ✅ |
| Kontrakt karty `vocabulario.card.v1` (§6) | ✅ Opisany |
| Spec per język morfologia (§7) | ✅ |
| UI strings it/ja/ko/tr/vi | ✅ Wygenerowane (audyt TODO) |
| `locales_config.xml` | ✅ +5 locale |
| Test kosztu odmiany | ✅ 1 zapytanie |
| Skrypty pomocnicze | ✅ `translate_ui_strings.py`, `inflection_shot_test.py` |

### 15.2 Czego **nie ma** w kodzie (do zrobienia)

| Obszar | Stan dziś | Akcja |
|--------|-----------|-------|
| **`backend/app/lsp/`** | ❌ Brak | Zbudować od zera — jedyny system promptów |
| **Enrichment** | ❌ Stary `prompts/v1` + `conjugation` | Zastąpić pipeline LSP |
| **`inflection` w JSON** | ❌ Nadal `conjugation` + `schema 1.0` | Nowy schemat |
| **Android `Constants.kt`** | ❌ 25 języków nauki, 10 UI | 16 + `pt-br`/`pt-pt` |
| **`native_lang` + `ui_lang`** | ❌ Dwa pola | Scalić w `app_lang` |
| **`tense_label_lang`** | ❌ Brak | Dodać do profilu + UI |
| **Ustawienia per L2** | ⚠️ Częściowe | Picker sekcji zh/vi; layout §5.2 |
| **`LanguagePacks.kt`** | ⚠️ 25 języków, zh/vi puste | Codegen z LSP lub ręcznie 16 |
| **Import** | ❌ `adaptive.v1`, `import_display.v1` | Przepisać / usunąć |
| **`check_ui_strings.py`** | ❌ Brak | CI 16 × 349 kluczy |
| **Golden tests × 16** | ❌ Brak | Per LSP |
| **POS_LABELS** | ⚠️ 10 języków | Uzupełnić it, ja, ko, tr, vi |

### 15.3 Werdykt (aktualizacja po starcie implementacji 2026-08-05)

| | |
|---|---|
| **Dokumentacja** | ✅ Gotowa |
| **LSP fundament** | ✅ `backend/app/lsp/` — loader, registry, validate, prompts |
| **Manifest `pl`** | ✅ `backend/app/lsp/pl/manifest.yaml` |
| **Enrichment LSP** | ✅ `learning_lang=pl` → `vocabulario.card.v1` + `inflection` (+ `conjugation` mirror dla Androida) |
| **API** | ✅ `GET /api/v1/meta/lsp`, `GET /api/v1/meta/lsp/pl` |
| **Testy** | ✅ `tests/test_lsp_pl.py` (10 testów łącznie z conjugation) |
| **Pozostałe 15 LSP** | ❌ Do zrobienia |
| **Android** | ❌ 16 języków, `app_lang`, `inflection` UI |
| **Legacy usunięcie** | ❌ `prompts/v1` nadal dla innych języków |

### 15.4 Kolejność prac (wewnętrzna)

1. Manifest template + JSON Schema `card.v1`
2. LSP `pl` pełny → pipeline enrichment → walidator
3. Android: `app_lang`, 16 języków, `inflection` render
4. Pozostałe 15 LSP + golden tests
5. Import rewrite, usunięcie legacy
6. Audyt tłumaczeń UI + `check_ui_strings.py`

---

*Następny krok implementacji: `docs/lsp-manifest-template.yaml` + manifest `pl`.*
