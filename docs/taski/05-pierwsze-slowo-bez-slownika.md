# Task 05. Pierwsze słowo bez Wikisłownika (serwer)

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 2.

## Zakres

Gałąź `lookup_cached`, gdy wiersza `lookup_query_cache` nie ma albo jest pusty bez `ai_complete`:

1. Jedno `search_db` bez wyszukiwania literówek (`_fuzzy_l1_db_candidates`).
2. Brak pewnego trafienia: jedno wywołanie luny z krótkim promptem, `reasoning_effort="none"`, limit 400. Bez Wikisłownika i bez wyścigu z budżetem.
3. Połączenie z puli zwolnione na czas modelu.
4. Wspólna stała ze zdaniem o rodzajniku (ART2), używana też przez taski 06, 08 i 10.

Poza zakresem: telefon (task 07: brak automatycznego expand przy niepustej odpowiedzi), szukanie kategorii (task 08), `lookup/expand` (task 06). Wikisłownik zostaje w `correction_evidence.py`.

## Zależności

- Task 02: `reasoning_effort` w `_chat_json`, zapisy `llm_usage` w tle.
- Task 04: `annotate`, historia w tle, `get_current_user_id`.

## Pliki

- `backend/app/ai/prompts/v1.py`: nowe `NOUN_ARTICLE_RULE`, `LOOKUP_DRAFT_SYSTEM_V2`, `LOOKUP_DRAFT_USER_V2`,
- `backend/app/services/llm.py`: `lookup_draft`,
- `backend/app/services/lexical.py`: `lookup_cached` (gałąź braku wiersza), nowa `_db_exact_candidates`, `_light_draft_candidates`,
- testy: `backend/tests/test_lookup_draft_race.py` (przepisany), `test_lookup_query_cache.py`, `test_lookup_candidates.py`.

## Zachowanie

### `NOUN_ARTICLE_RULE`

```python
NOUN_ARTICLE_RULE = (
    "Noun lemma: in Spanish, French, Italian, Portuguese and German it starts with the "
    "singular definite article (el/la, le/la/l', il/lo/la/l', o/a, der/die/das); in other "
    "languages it has no article and no classifier."
)
```

Tekst dosłownie jak w punkcie 2. Bez wstawiania nazw języków pary.

### Prompt luny

System (`LOOKUP_DRAFT_SYSTEM_V2`):

```
Dictionary lookup. JSON only. If the query is a real L1 word, the first candidates are its ordinary L2 translations and the gloss is that L1 word. Add an L2 headword only when the query is exactly that headword, ignoring case and diacritics. Do not return a word only because it sounds similar. lemma is the L2 citation form. gloss is the L1 citation form. {NOUN_ARTICLE_RULE}
```

Użytkownik (`LOOKUP_DRAFT_USER_V2`):

```
L1: {native_name}. L2: {learning_name}. Query: "{text}". At most 4 candidates. pos: noun, verb, adj, adv, or other. JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

`lookup_draft`:

```python
data = await self._chat_json(
    self.light_model, prompt, system=LOOKUP_DRAFT_SYSTEM_V2,
    max_tokens=400, reasoning_effort="none", purpose="lookup_draft",
)
```

Bez `language_pair_guidance`. `LOOKUP_DRAFT_PROMPT_V1` zostaje w pliku, dopóki nic go nie używa, potem do usunięcia w tym samym tasku.

### `lookup_cached`, gałąź braku wiersza

```
profile, row = odczyt jak dziś (albo z lookup_cached_fast)
await db.commit()                       # koniec transakcji, połączenie wraca do puli
exact = await _db_exact_candidates(profile, text)   # search_db + _rank_lookup_candidates
if any confident in exact:
    merged = await _merge_into_query_cache(pair, key, confident, ...)   # ai_complete zostaje false
    return _present_lookup(..., merged, "db", False, annotate=annotate)
await db.commit()                       # przed modelem bez otwartej transakcji
draft = await _light_draft_candidates(profile, text, user_id=user_id)
if draft:
    merged = await _merge_into_query_cache(pair, key, draft, ...)
    return _present_lookup(..., merged, "ai", False, annotate=annotate)
return LookupOutcome([], "db", False)   # bez wiersza cache
```

- `_db_exact_candidates` to pierwsza połowa dzisiejszego `_db_first_candidates`, bez `_fuzzy_l1_db_candidates`. `_db_first_candidates` zostaje dla `lookup_category_cached` do taska 08.
- `_dictionary_candidates` i `collect_first_lookup_hits` przestają być wołane z tej gałęzi. `collect_first_lookup_hits` i `LOOKUP_DRAFT_BUDGET_S` usunąć razem z ich testami, jeśli `rg` nie pokaże innego użycia.
- `_light_draft_candidates` zostaje opakowaniem z `bind_llm_usage_context` i łapaniem wyjątku. Błąd modelu daje pustą listę, czyli pustą odpowiedź.
- Propozycje modelu przechodzą przez `_raw_to_candidates` i w `_present_lookup` przez `_rank_lookup_candidates` (`sanitize_lookup_candidates`, `canonicalize_lookup_candidate`), tak jak dziś.
- Pusty wynik nie tworzy wiersza cache. Pusty wiersz, który już był, nie dostaje `hit_count` z tej gałęzi w sesji żądania. Licznik podbija zadanie historii z taska 04 (`cache_row_id`).
- `_merge_into_query_cache` zostaje bez zmian: `INSERT … ON CONFLICT DO NOTHING`, `SELECT … FOR UPDATE`, złączenie w Pythonie. Dwa równoczesne żądania z tym samym nowym hasłem dają jeden wiersz z propozycjami obu.
- Endpoint robi `commit` po `_merge_into_query_cache`, przed odpowiedzią. Bez tego następne szukanie nie widzi słowa.

`source` odpowiedzi: `db` przy trafieniu w `lexical_entries`, `ai` przy modelu. `ai_complete` zawsze fałszywe na tej gałęzi.

Ta gałąź działa tak samo dla starego i nowego telefonu. Stary telefon przy `ai_complete=false` sam woła `lookup/expand`, jak dziś.

## Kroki

1. `NOUN_ARTICLE_RULE` i prompty V2.
2. `lookup_draft` z nowymi parametrami. Test z atrapą `client.chat.completions.create`: dostaje `reasoning_effort="none"`, `max_completion_tokens=400`, bez `temperature`, a wiadomość systemowa kończy się `NOUN_ARTICLE_RULE`.
3. `_db_exact_candidates` i nowa gałąź w `lookup_cached` z dwoma `commit`.
4. Usunięcie wyścigu i jego testów.
5. Testy gałęzi.

## Sprawdzenie

Testy (`pytest`):

- Hasło z pewnym trafieniem w `lexical_entries`: wiersz cache z `ai_complete=false`, `lookup_draft` (atrapa) nie wołany, `lookup_dictionary_candidates` (atrapa) nie wołany.
- Hasło bez trafienia, atrapa luny z `el castillo`: odpowiedź `source=ai`, `ai_complete=false`, wiersz cache z tą propozycją.
- Atrapa luny z pustą listą: odpowiedź pusta, wiersza cache nie ma.
- Atrapa luny rzucająca wyjątek: odpowiedź pusta, 200.
- Dwa równoczesne żądania z różnymi atrapami wyniku: oba 200, jeden wiersz, propozycje obu.
- W czasie atrapy modelu (`asyncio.Event`) pula nie ma wypożyczonego połączenia tej sesji (`engine.pool.checkedout()` nie rośnie o 1).

Produkcja (po 01 i 02), hasła spoza `lookup_query_cache` dla pary profilu:

- portugalski (Brazylia) → turecki, `casa`: pierwsza propozycja `ev`; niemiecki → wietnamski, `Wasser`: `nước`,
- polski → hiszpański, `zamek`: `el castillo` i `la cerradura`; włoski → portugalski, `acqua`: `a água`,
- jeden wiersz `llm_usage` z `purpose=lookup_draft`, `reasoning_tokens=0`, czas modelu około 1 s,
- `app_logs.duration_ms` poniżej 2 s,
- w logu żądania brak wywołań Wikisłownika (`dictionary_lookup`),
- drugie wpisanie tego samego hasła idzie szybką gałęzią z taska 04, bez nowego `lookup_draft`.

## Ryzyka

- Literówka w języku ojczystym, którą dziś łapało `_fuzzy_l1_db_candidates`, trafia teraz do luny. Krótki prompt ma zasadę „nie zwracaj podobnych brzmieniem”, więc przy literówce może oddać pustkę. Wtedy telefon woła pełne szukanie z taska 06, które literówki naprawia (pomiar 25 na 25).
- Klasyfikator wietnamski (`ngôi nhà`) i pomyłka szkicu utrwalona we wspólnym cache (`aqua`). Ryzyka przyjęte w punkcie 2.
