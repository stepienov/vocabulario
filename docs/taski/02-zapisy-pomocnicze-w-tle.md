# Task 02. Zapisy pomocnicze w tle

Dokument źródłowy: `docs/optymalizacja-requestow.md`, rozdział 0, „Zapisy pomocnicze na ścieżce odpowiedzi”, i sekcja „Jak czytać czasy”.

## Zakres

1. Wspólny mechanizm zapisów w tle (`spawn_background`).
2. Wiersz `app_logs` z `AppLogMiddleware` idzie w tle, po oddaniu odpowiedzi.
3. Po wywołaniu modelu `log_event(llm_call)`, `llm_usage` i `llm_call_payloads` idą w tle, jednym zadaniem, w jednej sesji.
4. Inne `log_event` na ścieżkach szukania i wzbogacania idą w tle (`lexical_cache_miss`, `_log_enrich_pipeline`).
5. `_chat_json` i `_chat_json_openai` przyjmują `reasoning_effort`.

Poza zakresem: zmiana treści logów, zmiana tabel, nowe metryki.

## Zależności

Task 00 (testy `[pg]`). Kod nie zależy od innych tasków. Pomiar efektu ma sens po tasku 01.

## Warunek startu

- `rg -n '"pg:' backend/pyproject.toml` i `rg -n "def pg\b|async def pg\b" backend/tests/conftest.py` dają wynik (task 00).
- `rg -n "spawn_background" backend/app` nie daje wyniku. Gdy daje, task jest częściowo zrobiony: przerwij i opisz stan.

## Pliki

- nowy `backend/app/services/background.py`,
- `backend/app/core/app_log_middleware.py` (`AppLogMiddleware.dispatch`),
- `backend/app/services/app_log.py` (`log_event` bez zmian, nowy wrapper `log_event_background`),
- `backend/app/services/llm_usage.py` (`record_llm_usage`),
- `backend/app/services/llm.py` (`_chat_json`, `_chat_json_openai`),
- `backend/app/services/card_jobs.py` (`hydrate_from_lexical_cache` → `lexical_cache_miss`, `_log_enrich_pipeline`),
- `backend/app/main.py` (`lifespan`: opróżnienie kolejki przy zamknięciu),
- testy: `backend/tests/test_app_log.py`, `test_llm_usage.py`, `test_llm_debug.py`, nowy `test_background.py`.

## Zachowanie

### `spawn_background`

```python
def spawn_background(factory: Callable[[], Awaitable[None]], *, name: str) -> None
async def drain_background(timeout_s: float) -> None
```

- `spawn_background` woła `asyncio.create_task(_run(factory))` i trzyma zadanie w module-level `set` do końca. Bez silnej referencji zadanie może zniknąć z odśmiecaczem.
- `_run` bierze `asyncio.Semaphore(8)`. Zapisy w tle nie zajmują więcej niż 8 połączeń z puli naraz, a pula ma 15.
- Gdy w zbiorze jest już 1000 zadań, nowe zadanie nie powstaje. Licznik pominiętych rośnie, a `logger.warning` raz na 100 pominięć. Zapis pomocniczy nie może zablokować procesu.
- Wyjątek w zadaniu: `logger.exception`, bez propagacji.
- `asyncio.create_task` kopiuje `ContextVar` z chwili wywołania. `request_id_var`, `user_id_var`, `profile_id_var` i kontekst `llm_usage` są więc w zadaniu takie jak w chwili `spawn_background`. Zadanie musi powstać przed `clear_request_context()` i `clear_llm_usage_context()`.
- `drain_background(timeout_s)` czeka na wszystkie zadania ze zbioru, najwyżej `timeout_s`. `lifespan` w `main.py` woła je po `yield` z `timeout_s=5`, zanim anuluje watchdog.

### Middleware

`AppLogMiddleware.dispatch`:

- ścieżka udana: zamiast `await log_event(...)` jest `spawn_background(lambda: log_event(...), name="app_log_http")`, potem `clear_request_context()` i `return response`,
- ścieżka wyjątku: to samo, potem `raise`.

`duration_ms` dalej liczy czas do oddania odpowiedzi przez `call_next`. Teraz pokrywa się z czasem widzianym przez krawędź Railway, z dokładnością do drogi sieciowej.

### Wywołanie modelu

W `_chat_json` (gałąź OpenAI, Anthropic i mock) trzy `await` po wywołaniu (`log_event`, `record_llm_usage`) zastępuje jedno `spawn_background(..., name="llm_usage")`. Zadanie robi kolejno:

1. `log_event(event="llm_call", ...)` z tymi samymi polami co dziś,
2. `record_llm_usage(...)` z tymi samymi argumentami.

`record_llm_usage` robi oba wiersze w jednej sesji i jednej transakcji:

```python
async with async_session_factory() as db:
    db.add(usage_row)
    await db.flush()          # najpierw rodzic, potem dziecko: llm_call_payloads_llm_usage_id_fkey
    if store:
        db.add(LlmCallPayload(llm_usage_id=row_id, ...))
    await db.commit()
```

Komentarz w dzisiejszym kodzie mówi, że wspólny `flush` potrafi wstawić dziecko przed rodzicem. Jawny `flush` po rodzicu temu zapobiega. Błąd zapisu payloadu nie może zgubić metryki, więc payload idzie w `begin_nested()` (SAVEPOINT): błąd payloadu cofa tylko savepoint, a `llm_usage` się commituje.

`record_llm_usage` dalej zwraca `UUID | None`. Testy, które czekają na wiersz (`test_llm_debug.py`), wołają funkcję bezpośrednio i nic się dla nich nie zmienia.

### `reasoning_effort`

`_chat_json(..., reasoning_effort: str | None = None)` przekazuje wartość do `_chat_json_openai`. Tam, gdy `_is_reasoning_model(model)` i wartość nie jest `None`, `kwargs["reasoning_effort"] = reasoning_effort`. Dla innych modeli i dla Anthropic parametr jest pomijany. Domyślne `None` zostawia dzisiejsze zachowanie wszystkich istniejących wywołań.

`build_llm_request_json` dostaje `reasoning_effort`, żeby payload pokazywał, z jakim ustawieniem poszło wywołanie.

### Inne logi

- `hydrate_from_lexical_cache`: `lexical_cache_miss` przez `spawn_background`.
- `_log_enrich_pipeline` w `card_jobs.py`: przez `spawn_background`.
- Pozostałe `log_event` (import, poprawki, admin) zostają bez zmian. Nie są na ścieżce szukania ani zapisu słowa.

## Kroki

1. `background.py` z `spawn_background`, `drain_background` i testem jednostkowym (limit, wyjątek, kopia kontekstu, opróżnienie).
2. Middleware.
3. `record_llm_usage` w jednej sesji.
4. `_chat_json`: zapis w tle i `reasoning_effort`.
5. Logi w `card_jobs.py`.
6. `lifespan`: `drain_background(5)`.
7. Testy, które sprawdzają wiersz `app_logs` albo `llm_usage` po żądaniu, wołają `await drain_background(1)` przed odczytem.

## Sprawdzenie

Lokalnie, wykonawca:

- `pytest` zielony, z testami `pg`.
- `test_background.py`: limit 1000 (tysiąc pierwsze zadanie nie powstaje, licznik pominiętych 1), wyjątek w zadaniu nie wychodzi na zewnątrz, `drain_background(1)` czeka na zadanie, które śpi 0,1 s, i wraca po czasie przy zadaniu, które śpi 10 s.
- `spawn_background` w kontekście z `request_id_var = X`, a po nim `clear_request_context()`: atrapa `log_event` dostaje `request_id = X`.
- `[pg]` żądanie przez `pg_client` do `/health` i do `/api/v1/me`: odpowiedź wraca, zanim atrapa zapisu (`asyncio.Event` w podmienionym `log_event`) zostanie zwolniona. Po zwolnieniu i `drain_background(1)` wiersz `app_logs` jest w bazie.
- `[pg]` `record_llm_usage` z `store=True`: oba wiersze w bazie, `llm_call_payloads.created_at - llm_usage.created_at` poniżej 10 ms (jedna transakcja). Z payloadem, którego zapis rzuca (atrapa `LlmCallPayload` z niepoprawnym polem): `llm_usage` jest, payloadu nie ma.
- Atrapa `client.chat.completions.create` dla `gpt-5.6-terra` i `reasoning_effort="none"`: dostaje `reasoning_effort="none"`. Bez argumentu: klucza nie ma w `kwargs`. Dla modelu, przy którym `_is_reasoning_model` jest fałszywe: klucza nie ma.
- `rg -n "await (log_event|record_llm_usage)" backend/app/core/app_log_middleware.py backend/app/services/llm.py` nie daje wyniku (dziś 7 trafień: middleware 116 i 136, `llm.py` 140, 190, 207, 227, 243).

Po wdrożeniu (odczyt produkcji, po tasku 01):

- Szukanie `prado`: krawędź Railway (`totalDuration`) minus `app_logs.duration_ms` poniżej 60 ms (dziś około 440 ms).
- Produkcja: nowa karta z modelem. W `llm_usage` są wszystkie wywołania, każde z payloadem. Przerwa między `llm_usage.created_at` a `llm_call_payloads.created_at` poniżej 10 ms (jedna transakcja).
- Produkcja: liczba wierszy `app_logs` z `event='http_request'` na godzinę taka jak przed zmianą (żaden log nie ginie). W logu procesu nie ma ostrzeżeń o pominiętych zadaniach.
- Restart serwisu w trakcie ruchu: w logu procesu jest opróżnienie kolejki, bez `Task was destroyed but it is pending`.

## Ryzyka

- Zabity proces (OOM, `SIGKILL`) gubi zapisy w kolejce. Dotyczy tylko logów i metryk, nie danych użytkownika. Przyjęte.
- `llm_usage` przestaje być pod ręką w tym samym żądaniu. Nikt w kodzie aplikacji nie czyta go zaraz po wywołaniu. Sprawdza to `rg "record_llm_usage|LlmUsage" backend/app`.
