# Task 04. Szybka odpowiedź z gotowego zapisu (serwer)

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 1, „Instrukcja implementacji”, części „Serwer: szybka odpowiedź”.

## Zakres

1. Pole `local_membership` w `LookupRequest`.
2. `POST /lookup/cached` przy `local_membership=true` i trafieniu w gotowy wiersz: jedno zapytanie SQL, odpowiedź bez kart, list i `lexical_entries`, bez commitu.
3. Przy `local_membership=true` także pozostałe gałęzie `lookup_cached` nie czytają kart ani list.
4. Historia `lookup_events` i `hit_count` w tle, atomowym `UPDATE`, dla wszystkich gałęzi `lookup/cached`.

Poza zakresem: gałąź bez wiersza (task 05), `lookup/expand` i `more` (task 06), szukanie kategorii (task 08), telefon (task 07).

## Zależności

- Task 02: `spawn_background`.
- Pomiar ma sens po tasku 01.

## Pliki

- `backend/app/schemas/__init__.py`: `LookupRequest.local_membership: bool = False`,
- `backend/app/core/deps.py`: nowa zależność `get_current_user_id`,
- `backend/app/api/v1/learning.py`: endpoint `lookup_cached`,
- `backend/app/services/lexical.py`: nowa `lookup_cached_fast`, parametr `annotate` w `_present_lookup`, `lookup_cached`,
- `backend/app/services/lookup_events.py`: nowa `record_lookup_event_background`,
- testy: `backend/tests/test_lookup_query_cache.py`, `test_lookup_jobs.py` (nowe przypadki), nowy `test_lookup_cached_fast.py`.

## Zachowanie

### `get_current_user_id`

```python
async def get_current_user_id(credentials = Depends(security)) -> UUID
```

Ten sam dekod tokenu co `get_current_user` (`decode_token`, `verify_token_type(payload, "access")`), te same błędy 401 `not_authenticated` i `invalid_token`. Bez odczytu `users`.

### Endpoint

```python
@router.post("/lookup/cached", response_model=LookupResponse)
async def lookup_cached(body, user_id = Depends(get_current_user_id), db = Depends(get_db)):
```

- `local_membership=true`: najpierw `LexicalService(db).lookup_cached_fast(user_id, body.profile_id, body.text)`. Gdy zwróci wynik, odpowiedź idzie od razu.
- W pozostałych przypadkach endpoint ładuje `User` (`select(User).where(User.id == user_id)`). Brak wiersza daje 401 `user_not_found`, tak jak dziś `get_current_user`. Potem dotychczasowe `service.lookup_cached(user, ..., annotate=not body.local_membership)`.
- `commit` sesji żądania zostaje tylko na gałęziach, które coś zapisały w cache (`_merge_into_query_cache`). Gałąź szybka nie robi commitu.
- Historia: zamiast `await record_lookup_event(db, ...)` jest `record_lookup_event_background(...)`, po zbudowaniu odpowiedzi, przed `return`.

### `lookup_cached_fast`

Jedno zapytanie:

```sql
SELECT p.app_lang, p.learning_lang, c.id, c.candidates, c.ai_complete
FROM language_profiles p
LEFT JOIN lookup_query_cache c
  ON c.lang_pair = p.app_lang || '>' || p.learning_lang
 AND c.input_norm = :key
WHERE p.id = :profile_id AND p.user_id = :user_id
```

`:key` to `self._query_cache_key(text)` (dotychczasowy klucz). Format pary to `lang_pair_key` z `deps.py` (`f"{native}>{learning}"`). Zapytanie pisać w SQLAlchemy Core (`select(...).outerjoin(...)`) z tym samym wyrażeniem łączenia, żeby nie rozjechało się z `lang_pair_key`.

- Brak wiersza profilu: `ValueError("Profile not found")`. Endpoint zamienia go na 404, tak jak dziś. Usunięte konto z ważnym tokenem dostaje więc 404 zamiast 401. To jest przyjęte w punkcie 1.
- Wiersz cache jest i ma propozycje albo `ai_complete`: `LookupOutcome(ranked, "db", bool(ai_complete))`, gdzie `ranked = self._rank_lookup_candidates(list(candidates), text, learning_lang=...)`. Bez `_attach_lexical_ids` i bez `_annotate_candidates`.
- W pozostałych przypadkach `None`. Endpoint idzie dotychczasową drogą.

Funkcja zwraca też `pair` i `cache_row_id`, żeby zadanie w tle miało je bez drugiego odczytu.

Po zapytaniu: `await db.rollback()`. Transakcja otwarta przez `SELECT` zamyka się przed odpowiedzią i połączenie wraca do puli.

### `_present_lookup(..., annotate: bool = True)`

Przy `annotate=False` pomija `_attach_lexical_ids` i `_annotate_candidates`. Kandydaci mają tylko pola zapisane w cache (`lemma`, `pos`, `gloss` i, jeśli są, `reading`, `typed_as`). `_lookup_http` wypełnia brakujące pola wartościami domyślnymi.

`lookup_cached` przekazuje `annotate` do każdego wywołania `_present_lookup`. Gałąź gotowego wiersza w `lookup_cached` przestaje robić `row.hit_count = row.hit_count + 1` (to robi zadanie w tle). To samo w ostatniej gałęzi (pusty wynik przy istniejącym wierszu). `_merge_into_query_cache` zostaje bez zmian, bo i tak trzyma wiersz `FOR UPDATE` przy zapisie propozycji.

### Historia i licznik w tle

```python
def record_lookup_event_background(*, user_id, profile_id, lang_pair, query, source,
                                   candidates, ai_complete, cache_row_id, request_id) -> None
```

Woła `spawn_background` z zadaniem, które w nowej sesji:

1. gdy `cache_row_id` nie jest `None`: `UPDATE lookup_query_cache SET hit_count = hit_count + 1, updated_at = now() WHERE id = :id`,
2. wstawia `LookupEvent` z tymi samymi polami co `record_lookup_event`, z `lang_pair` z argumentu (bez odczytu profilu) i `request_id` z argumentu,
3. `commit`.

Błąd: `logger.exception`, bez wpływu na odpowiedź.

`cache_row_id` przekazujemy tylko z gałęzi, które dziś podbijały licznik: gotowy wiersz i pusty wynik przy istniejącym wierszu. Gałęzie z `_merge_into_query_cache` podbijają licznik same.

`create_card` dowiązuje kartę do `lookup_events` z ostatnich 15 minut. Zadanie w tle kończy się w milisekundach po odpowiedzi, więc karta tworzona po tapnięciu dodania znajdzie wiersz historii.

## Kroki

1. `get_current_user_id` i test 401.
2. `LookupRequest.local_membership`.
3. `_present_lookup(annotate=...)` i przekazanie w `lookup_cached`.
4. `lookup_cached_fast` z testem: profil cudzy daje `ValueError`, brak wiersza daje `None`, wiersz z propozycjami daje wynik bez pól nauki.
5. `record_lookup_event_background`, endpoint.
6. Testy istniejące, które czytają `lookup_events` albo `hit_count` po `lookup/cached`, wołają `drain_background` przed odczytem.

## Sprawdzenie

Testy (`pytest`):

- `local_membership=true`, gotowy wiersz: odpowiedź ma kandydatów bez `learning_card_id`, `list_id`, `list_name`, `in_learning=false`, nawet gdy użytkownik ma kartę tego hasła. W logu SQL testu (`echo` albo licznik zdarzeń `before_cursor_execute`) jest jedno zapytanie do bazy na ścieżce żądania.
- `local_membership=false` (domyślnie), ten sam wiersz: odpowiedź jak dziś, z `learning_card_id` i `list_name`.
- Po `drain_background`: jeden nowy `lookup_events` z `source=db`, `ai_complete` jak w wierszu, `request_id` żądania. `hit_count` wiersza wzrósł o 1.
- Dwa równoczesne `lookup/cached` tego samego hasła: oba 200, `hit_count` wzrósł o 2.
- Token użytkownika bez wiersza `users`, `local_membership=true`: 404. To samo przy `false`: 401 `user_not_found`.

Produkcja, po tasku 01 i 02, konto `nowy4@test.com`, `prado`, wywołanie z `local_membership=true` (curl z tokenem konta kontrolnego, zanim wyjdzie telefon z taskiem 07):

- `app_logs.duration_ms` poniżej 150 ms, krawędź Railway poniżej 600 ms,
- odpowiedź: trzy propozycje, `ai_complete=true`, bez identyfikatorów kart i list,
- brak nowego wiersza w `llm_usage`,
- w ciągu paru sekund nowy `lookup_events` (`query=prado`, `source=db`, `candidate_count=3`), `hit_count` +1,
- to samo bez `local_membership`: odpowiedź z polami nauki, jak dziś.

## Ryzyka

- Telefon z taskiem 07 wysyła `local_membership=true` i dostaje kafelki bez pól nauki. Jeśli serwer z taskiem 04 nie byłby wdrożony, stary serwer zignoruje pole i odda pola nauki. Telefon i tak liczy ikony z Room. Kolejność wdrożeń nie jest więc krytyczna.
- `_rank_lookup_candidates` musi dostać te same dane co dziś w `_present_lookup`. Test porównuje kolejność kandydatów z obu ścieżek dla tego samego wiersza.
