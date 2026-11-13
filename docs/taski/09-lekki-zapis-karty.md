# Task 09. Lekki zapis karty

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 5.

## Zakres

Serwer:

1. `POST /lists/{id}/words` i `POST /cards` sprawdzają duplikat lekkim odczytem (`id`, `lemma_l2`, `pos`) i nie robią hydracji ani rodziny wyrazów przed odpowiedzią.
2. `spawn_enrich` przyjmuje `source_card_id`.
3. Hydracja z `lexical_entries` i `attach_card_to_word_family` w zadaniu w tle, przed semaforem wzbogacania.
4. `attach_card_to_word_family` raz po zapisie wyniku modelu, gdy hydracja nic nie znalazła.

Telefon:

5. Po 409 synchronizacja przyrostowa i ponowne zestawienie kafelka zamiast samego przycisku dodania.

Poza zakresem: podział rdzenia (task 10), import (task 11).

## Zależności

- Task 02: `lexical_cache_miss` w tle.
- Task 03: kafelek `pending` po zapisie wchodzi w odpytywanie z limitem.
- Część telefonu: task 07 (zestawienie z Room, obserwacja kart, `inFlightAdds`).

## Pliki

Serwer:

- `backend/app/services/word_lists.py`: nowa `find_card_key_anywhere`, `find_card_anywhere`,
- `backend/app/api/v1/learning.py`: `create_card`, `add_word_to_list`,
- `backend/app/services/card_jobs.py`: `spawn_enrich`, `_run_claimed_enrich`, nowa `_hydrate_before_queue`, `_enrich_card_unlocked`,
- testy: `backend/tests/test_lexical_cache.py`, `test_enrichment_pipeline.py`, `test_word_family.py`, nowe przypadki dla endpointów.

Telefon:

- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt`: `addToList`, `createListAndAdd`, gałąź `createCard` (okolice linii 890), `revertCreating`,
- `android/app/src/main/java/com/vocabulario/app/data/api/ApiErrors.kt` (rozpoznanie kodu 409 `word_already_on_list`, już jest).

## Zachowanie serwera

### Lekki odczyt duplikatu

```python
async def find_card_key_anywhere(db, user_id, profile_id, lemma, pos) -> UUID | None
```

`select(LearningCard.id, LearningCard.lemma_l2, LearningCard.pos)` dla żywych kart użytkownika i profilu. Wiersze idą do `select_live_card_for_lemma`. Funkcja przyjmuje obiekty z atrybutami `lemma_l2` i `pos`, więc wiersze `Row` z SQLAlchemy działają bez zmian. Zwraca `id` trafienia.

`find_card_anywhere` zostaje dla importu i innych wołających, którzy potrzebują pełnej karty. Może wołać `find_card_key_anywhere` i po trafieniu `db.get(LearningCard, id)`.

Unikalny indeks `uq_learning_cards_live_lemma_pos` zostaje drugą zaporą: równoczesne dodania tej samej lemy kończą się jednym wierszem i 409 z `IntegrityError`, jak dziś.

### Endpointy

`create_card` i `add_word_to_list`:

1. profil (i wiersz `word_lists` w `add_word_to_list`),
2. `find_card_key_anywhere`, trafienie: 409 `word_already_on_list`,
3. wstawienie `learning_cards` z `build_pending_content` i `pending`, `flush`,
4. lista systemowa: `srs_state`,
5. `create_card`: dotychczasowe `find_lookup_event_for_card`,
6. `source_card_id` z body: sama kontrola własności (`_owned_source_card`), bez zmiany karty źródłowej,
7. `commit` (z dotychczasową obsługą `IntegrityError` → 409), `refresh`,
8. `spawn_enrich(card.id, source_card_id=source.id if source else None)`.

Bez `hydrate_from_lexical_cache` i bez `attach_card_to_word_family`. Odpowiedź niesie szkic treści i `pending`. `CardResponse.enrichment_active` (task 03) jest w niej `true`, bo `spawn_enrich` dodał kartę do `_claimed`.

`best_lookup_candidate` dalej startuje tylko przy nierozwiązanym słowie (`already_resolved` fałszywe), jak dziś.

### Zadanie w tle

```python
def spawn_enrich(card_id: UUID, *, source_card_id: UUID | None = None) -> None
```

`_run_claimed_enrich(card_id, source_card_id)`:

```
if await _hydrate_before_queue(card_id, source_card_id):
    return
async with _enrich_semaphore():
    await asyncio.wait_for(_enrich_card_unlocked(card_id, source_card_id), _ENRICH_TIMEOUT_S)
```

`_hydrate_before_queue`, własna sesja:

- karta usunięta, `ready` z pełną treścią, `failed`, `prep_problem`, `learnable` z przyszłym `retry_at`: `True` (nic do roboty, ta sama lista warunków co dziś na początku `_enrich_card_unlocked`),
- `hydrate_from_lexical_cache(db, card, profile)`:
  - trafienie: `commit` treści, potem `attach_card_to_word_family(db, profile, card, source_card=source)`, `commit`, dotychczasowe `notify_cards_ready`, `True`,
  - pudło: `False`, bez zmian w bazie (`lexical_cache_miss` w tle, task 02).
- `source` to karta `source_card_id`, sprawdzona jak w `_owned_source_card` (ten sam użytkownik i profil, nieusunięta). Brak albo cudza: `None`.

`_enrich_card_unlocked` przestaje wołać hydrację na początku, bo zrobiło ją `_hydrate_before_queue`. Po zapisie wyniku modelu (`_enrich_lemma_staged` i gałąź adaptacyjna) jedno `attach_card_to_word_family(db, profile, card, source_card=source)` i `commit`, raz na zadanie.

Wznowienie (`resume_pending_enrichment`, watchdog, `get_card`) woła `spawn_enrich` bez `source_card_id`. Wtedy działa dotychczasowe `_seed_family_from_citing_cards` wewnątrz `attach_card_to_word_family`. Karta źródłowa nie dostanie od razu nowego członka rodziny. To ryzyko jest przyjęte w punkcie 5.

## Zachowanie telefonu

Po błędzie z kodem `word_already_on_list` w `addToList`, `createListAndAdd` i gałęzi `createCard`:

- `revertCreating(candidate)` jak dziś, kafelek wychodzi z `inFlightAdds`,
- `repository.syncNow(fullReplace = false)` w tle,
- obserwacja kart z taska 07 zestawi kafelek po synchronizacji: ikona i nazwa listy, na której karta jest,
- komunikat `err_word_on_list` jak dziś.

Inne błędy bez zmian.

## Kroki

1. `find_card_key_anywhere` i test z kartą o długim `content` (odczyt nie bierze `content`).
2. `spawn_enrich(source_card_id)`, `_hydrate_before_queue`, `attach_card_to_word_family` po wyniku modelu. Testy zadania.
3. Endpointy bez hydracji i rodziny. Testy endpointów.
4. Telefon: 409.

## Sprawdzenie

Testy serwera (`pytest`):

- `POST /lists/{id}/words` dla słowa, które jest w `lexical_entries`: odpowiedź `pending`, w tym żądaniu brak wywołania `hydrate_from_lexical_cache` (atrapa). Po zadaniu karta `ready`, treść z `lexical_entries`.
- Trzy zadania wzbogacania trzymają semafor (atrapa modelu czeka na `asyncio.Event`), czwarta karta ze słowem z `lexical_entries` dochodzi do `ready` bez czekania na semafor.
- `source_card_id` podany: po zadaniu karta źródłowa ma nowe słowo w rodzinie. `source_card_id` cudzego użytkownika: karta źródłowa bez zmian.
- `enviar` czasownik przy zapisanym `enviar` czasowniku: 409. `enviar` z `pos=noun`: 201, osobna karta. `el prado` przy karcie `prado` tej samej części mowy: 409.
- Dwa równoczesne dodania tej samej lemy: jedno 201, jedno 409.

Produkcja (po 01 i 02), konto kontrolne:

- `POST /lists/{id}/words` z `enviar` (czasownik, z glosą): w tym `request_id` brak `lexical_cache_miss`, `enrich_cache_hit` i `llm_usage`; `app_logs.duration_ms` poniżej 300 ms, krawędź poniżej 600 ms (dziś p50 5,9 s),
- odpowiedź: `pending`, szkic treści; `srs_state` dla listy systemowej,
- kafelek: nazwa listy, kółko, „Tworzę kartę…”, ptaszek przy `learnable`,
- drugie dodanie: 409, po synchronizacji kafelek z ikoną i nazwą listy.

## Ryzyka

- Karta, która dziś wracała `ready` w odpowiedzi (12 na 253 w 90 dniach), dostaje ptaszek po pierwszym `GET /cards/{id}`, około 2,5 s później. Przyjęte w punkcie 5.
- Proces padnie między odpowiedzią a zadaniem: karta zostaje `pending`, wznowienie ją podejmie bez `source_card_id`. Przyjęte.
