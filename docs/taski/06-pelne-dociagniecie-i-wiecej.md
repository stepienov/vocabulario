# Task 06. Pełne dociągnięcie i „Pokaż więcej propozycji” (serwer)

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 3, i część „Serwer: »Pokaż więcej propozycji«” w punkcie 1.

## Zakres

1. Pole `more` w `LookupRequest` i w kluczu `_inflight`.
2. `lookup_expand` przy `more` nie wraca wcześniej przy `ai_complete`, ani przed modelem, ani po nim.
3. Krótki prompt terry z ART2 i zdaniem o pustej liście, `reasoning_effort="none"`, limit 500.
4. Pole `added` w odpowiedzi.
5. Połączenie z puli zwolnione na czas modelu, zapis z ponownym odczytem `FOR UPDATE`.
6. `local_membership` na `lookup/expand`: zestawienie z kartami poza wspólnym zadaniem.

Poza zakresem: telefon (task 07), kategorie (task 08).

## Zależności

- Task 02 (`reasoning_effort`), task 04 (`local_membership`, `annotate`), task 05 (`NOUN_ARTICLE_RULE`).

## Pliki

- `backend/app/schemas/__init__.py`: `LookupRequest.more: bool = False`, `LookupResponse.added: int | None = None`,
- `backend/app/ai/prompts/v1.py`: `LOOKUP_EXPAND_SYSTEM_V2`, `LOOKUP_EXPAND_USER_V2`, `NO_MORE_RULE`,
- `backend/app/services/llm.py`: `lookup_expand`, `_already_block`,
- `backend/app/services/lexical.py`: `LookupOutcome.added`, `lookup_expand`, `lookup`,
- `backend/app/services/lookup_jobs.py`: `_key`, `ensure_expand_task`, `await_lookup_expand`, `_run_expand`,
- `backend/app/api/v1/learning.py`: endpoint `lookup_expand`, `_lookup_http`,
- testy: `backend/tests/test_lookup_jobs.py`, `test_lookup_query_cache.py`.

## Zachowanie

### Klucz i zadanie

```python
def _key(user_id, profile_id, text, more: bool) -> tuple[str, str, str, bool]
```

- zwykłe dociąganie i „więcej” tego samego hasła to dwa zadania,
- dwa „więcej” jedno po drugim, gdy pierwsze trwa, to jedno zadanie,
- `ensure_expand_task(user_id, profile_id, text, *, more=False)`, `await_lookup_expand(..., more=False)`.

`_run_expand` nie ładuje `User`. `LexicalService.lookup_expand` sprawdza właściciela profilu (`get_profile(user_id, profile_id)`), a `ValueError` daje 404, jak dziś.

Zadanie zwraca wynik bez zestawienia z kartami (`annotate=False`). Wynik zadania jest wspólny dla wszystkich czekających. Gdyby zestawiał karty, czekający z inną wartością `local_membership` dostałby nie swoją odpowiedź.

### `LexicalService.lookup_expand(user_id, profile_id, text, *, more=False)`

```
T1: profile = get_profile(...); row = _fetch_query_cache(pair, key)
    if not more and row and row.ai_complete:
        UPDATE hit_count = hit_count + 1 (atomowo); commit
        return LookupOutcome(rank(row.candidates), "db", True, added=0)
    already = list(row.candidates) if row else []
    commit                                   # połączenie wraca do puli
model: raw = llm.lookup_expand(text, app_lang, learning_lang, already)
       incoming = _raw_to_candidates(raw)
T2: row = _ensure_query_cache_row(pair, key)   # INSERT DO NOTHING + SELECT FOR UPDATE
    if not more and row.ai_complete:            # inne zadanie zapisało w czasie modelu
        return LookupOutcome(rank(row.candidates), "db", True, added=0)
    merged, added = append_lookup_candidates(list(row.candidates), incoming, ...)
    row.candidates = merged; ai_complete = True; hit_count += 1; updated_at = now
    flush
    return LookupOutcome(rank(merged), "ai", True, added=added)
```

`T2` commituje `_run_expand` razem z wierszem `lookup_events`, przed odesłaniem wyniku. Zerwanie połączenia przez telefon nie gubi listy, bo zadanie jest osłonięte `asyncio.shield`, jak dziś.

`LexicalService.lookup` (stary `POST /lookup`) woła `lookup_expand(user.id, profile_id, text)` bez `more`.

### Prompt terry

System (`LOOKUP_EXPAND_SYSTEM_V2`), tekst z punktu 3, w tym `NOUN_ARTICLE_RULE` i na końcu `NO_MORE_RULE`:

```python
NO_MORE_RULE = "If no other real reading exists, return an empty candidates list."
```

Użytkownik (`LOOKUP_EXPAND_USER_V2`):

```
L1: {native_name}. L2: {learning_name}. Query: "{text}".
{already_block}
pos is one of noun, verb, adj, adv, prep, conj, pron, det, interj, phrase, particle.
JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

`already_block`:

- lista niepusta: `Already shown, do not repeat these lemma+pos pairs:` i linie `- lemma=...; pos=...; gloss=...`,
- lista pusta: `Nothing shown yet.`

Dzisiejsze `_already_block` zwraca inny nagłówek (`Already stored (do NOT repeat…)`). Nowy tekst idzie w nowej funkcji albo w parametrze. `lookup_category_expand` zostaje przy starym nagłówku do taska 08.

```python
data = await self._chat_json(
    self.lookup_model, prompt, system=LOOKUP_EXPAND_SYSTEM_V2,
    max_tokens=500, reasoning_effort="none", purpose="lookup_expand",
)
```

Bez `LOOKUP_EXPAND_PROMPT_V1`, `language_pair_guidance` i `lookup_output_form_rules_text`.

### Endpoint

```python
@router.post("/lookup/expand")
async def lookup_expand(body, user_id = Depends(get_current_user_id)):
    outcome = await await_lookup_expand(user_id, body.profile_id, body.text, more=body.more)
    if not body.local_membership:
        async with async_session_factory() as db:
            outcome = await LexicalService(db).annotate_outcome(user_id, body.profile_id, outcome)
    return _lookup_http(outcome, body.text)
```

`annotate_outcome` to `_attach_lexical_ids` i `_annotate_candidates` dla gotowej listy. Stary telefon dostaje te same pola co dziś.

`_lookup_http` przepisuje `outcome.added` do `LookupResponse.added`. W odpowiedziach `lookup/cached` pole zostaje `None`.

## Kroki

1. Schematy i `LookupOutcome.added` (domyślnie `None`).
2. Prompty i `llm.lookup_expand`.
3. `LexicalService.lookup_expand` z dwiema transakcjami.
4. `lookup_jobs` z `more`.
5. Endpoint i `annotate_outcome`.
6. Testy.

## Sprawdzenie

Testy (`pytest`):

- `test_lookup_jobs.py`: zadanie bez `more` w toku i wywołanie z `more=True` dla tego samego hasła tworzą dwa zadania. Dwa wywołania z `more=True` tworzą jedno. Istniejące testy dostają argument `more`.
- Wiersz z `ai_complete=true`, `more=False`: atrapa modelu nie wołana, `added=0`.
- Ten sam wiersz, `more=True`: atrapa wołana z listą „już pokazane”, nowe hasło doklejone, stare zostały, `added=1`, `ai_complete=true`.
- Atrapa oddaje hasło, które już jest: `added=0`, wiersz bez zmian w `candidates`.
- `more=True`, a w czasie atrapy inne zadanie ustawia `ai_complete=true` i dopisuje hasło: wynik ma oba hasła (brak drugiego wczesnego powrotu).
- W czasie atrapy modelu pula nie ma wypożyczonego połączenia zadania.
- `local_membership=False`: odpowiedź z `learning_card_id` dla hasła, które jest kartą. `True`: bez pól nauki.
- Atrapa `client.chat.completions.create`: `reasoning_effort="none"`, `max_completion_tokens=500`, model `llm_lookup_model`, system kończy się `NO_MORE_RULE`.

Produkcja (po 01, 02, 04, 05), curl z tokenem konta kontrolnego:

- portugalski (Brazylia) → turecki, `casa` z wierszem `[ev]`, `more=true`: jeden `llm_usage` `lookup_expand`, `reasoning_tokens=0`, czas modelu około 1 s. Bez `kasa`. `added=0` albo nowe prawdziwe tłumaczenia,
- `Waser` przy niemiecki → wietnamski bez wiersza, `more=false`: `nước`,
- `zamek` przy polski → hiszpański: rzeczowniki z rodzajnikiem,
- `app_logs.duration_ms` `lookup/expand` poniżej 2,5 s (dziś typowo 11,4 s).

## Ryzyka

- Telefon starszej wersji nie wysyła `more` i dostaje dzisiejsze zachowanie, z krótszym promptem. Prompt zmienia się dla wszystkich. Pomiar 25 na 25 i weryfikacja z 8 listopada dotyczyły właśnie tego promptu.
- `added` przy `more=false` na wierszu bez `ai_complete` liczy też hasła, które pochodzą z modelu po raz pierwszy. Telefon pokazuje „Nie ma więcej propozycji.” tylko po tapnięciu „więcej” (task 07), więc ta wartość nie myli użytkownika.
