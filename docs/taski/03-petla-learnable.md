# Task 03. Koniec pętli `learnable`

Dokument źródłowy: `docs/optymalizacja-requestow.md`, rozdział 0, „Pętla `learnable`”. Schemat stanów: `docs/wzbogacanie-karty-schemat.md`, „Gdy coś nie dojdzie”.

## Zakres

Serwer:

1. Jeden warunek „odmiana jest / nie jest potrzebna” w `finish_side_jobs` i w `content_is_complete`.
2. Wynik „odmiana nie dotyczy” dla zwrotów, gdy model poprawnie odpowiedział bez form.
3. Limit automatycznych ponowień karty `learnable`.
4. Ponowienie, które nic nie zmieniło, nie loguje `enrich_ready`, nie woła `notify_cards_ready` i nie przesuwa `updated_at`.
5. Pole `enrichment_active` w `CardResponse`.

Telefon:

6. `HomeViewModel` i `LearningViewModel` przestają odpytywać kartę, gdy serwer mówi, że nic przy niej nie pracuje, i mają twardy limit czasu.

Poza zakresem: zmiana progów `MIN_SIMILAR_FOR_QUIZ` i `MIN_SIMILAR_WORDS`, zmiana promptu odmiany, powiadomienia FCM.

## Zależności

- Task 01. `enrichment_active` liczy się z `_claimed` w pamięci procesu. Przy dwóch replikach odpowiedź zależałaby od tego, która replika obsłuży `GET`.
- Task 02 nie jest wymagany.
- Musi wejść przed 07, 09 i 10, które dokładają odpytywanie statusów.

## Pliki

Serwer:

- `backend/app/lsp/enrichment.py`: `finish_side_jobs`, `_await_task`, nowa funkcja warunku odmiany,
- `backend/app/services/card_jobs.py`: `_has_verb_inflection`, `_has_required_inflection`, `content_is_complete`, `_apply_enrich_retry`, `_clear_enrich_retry`, `_persist_enrichment_result`, `_enrich_lemma_staged`, `_resume_pending_enrichment`,
- `backend/app/models/__init__.py`: kolumna `enrichment_side_retries`,
- `backend/app/db/migrations.py`: `ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS enrichment_side_retries INTEGER NOT NULL DEFAULT 0`,
- `backend/app/schemas/__init__.py`: `CardResponse.enrichment_active`,
- `backend/app/api/v1/learning.py`: `_card_response`,
- testy: `backend/tests/test_enrichment_retry.py`, `test_enrichment_pipeline.py`.

Telefon:

- `android/app/src/main/java/com/vocabulario/app/data/api/Models.kt`: `CardResponse.enrichment_active`,
- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt`: `startPollingIfNeeded`, `enrichmentPollCardIds`,
- `android/app/src/main/java/com/vocabulario/app/ui/learning/LearningViewModel.kt`: `startPollingIfNeeded`,
- nowy test `android/app/src/test/.../EnrichmentPollPolicyTest.kt`.

## Zachowanie serwera

### Jeden warunek odmiany

`_has_verb_inflection` i `_has_required_inflection` przechodzą z `card_jobs.py` do `backend/app/lsp/enrichment.py` jako `has_required_inflection(content, *, pos, lemma, learning_lang) -> bool`. Tam jest już `inflect_pos_key`, a `card_jobs.py` importuje z `lsp/enrichment.py`, więc odwrotny import nie powstaje.

Reguła:

- `inflect_pos_key(...) is None`: `True`,
- `content.get("inflection_status") == "not_applicable"`: `True`,
- `noun`: niepuste `inflection.nouns`,
- `adj`: niepuste `inflection.adjectives`,
- `verb`: `inflection.verbs.tenses` albo `inflection.verbs.non_finite` niepuste, albo niepuste `conjugation`.

`content_is_complete` woła tę funkcję. `finish_side_jobs` liczy:

```python
need_inflection = not has_required_inflection(
    content, pos=pos, lemma=lemma, learning_lang=profile.learning_lang
)
```

zamiast `has_infl = bool(content.get("inflection") or content.get("conjugation"))`. Odmiana z kluczami i samymi `null` jest teraz brakiem i model zostaje zapytany.

### „Odmiana nie dotyczy”

Dotyczy tylko kart, których `pos` daje kubełek `phrase` albo `construction` i dla których `inflect_pos_key` zwraca `verb`. Zwykły czasownik, rzeczownik i przymiotnik tego wyniku nie dostają.

W `finish_side_jobs` zadanie odmiany ma rozróżniać błąd i pustą odpowiedź. `_await_task` zwraca dziś domyślną wartość w obu przypadkach. Nowa wersja dla odmiany:

- wyjątek albo anulowanie: `None` (nie wiemy nic, karta zostaje do ponowienia),
- poprawna odpowiedź: wynik `validate_inflection`, także pusty.

Gdy wynik jest poprawny, kubełek to `phrase` albo `construction`, a wynik nie spełnia `has_required_inflection`, `finish_side_jobs` ustawia w treści `inflection_status = "not_applicable"` i zostawia `inflection` i `conjugation` jako `None`. To samo w `run_lemma_enrichment` po zadaniu odmiany.

Pole jest nowe, ale jest na najwyższym poziomie `content`. Telefon czyta `content` jako `JsonObject` i nieznanych kluczy nie rusza.

### Limit ponowień

Nowa kolumna `enrichment_side_retries` (domyślnie 0). Stała `_MAX_SIDE_RETRIES = 3`.

- Każdy przebieg, który kończy się zapisem `learnable` z karty, która już była `learnable`, zwiększa licznik o 1.
- Gdy licznik dochodzi do `_MAX_SIDE_RETRIES`, `enrichment_retry_at = None` i karta zostaje `learnable` na stałe. Ostatni błąd zostaje w `enrichment_error`.
- `_apply_enrich_retry` w gałęzi `learnable` robi to samo (dziś za każdym razem ustawia teraz plus 15 minut).
- `_resume_pending_enrichment`: `learnable_due` dostaje warunek `enrichment_side_retries < _MAX_SIDE_RETRIES`. Dzięki temu karta z `retry_at = None` po wyczerpaniu limitu nie wraca przez gałąź `retry_at IS NULL`. Ta gałąź zostaje dla kart, które upadły między `on_core` a zapisem `retry_at`.
- `_enrich_card_unlocked`: karta `learnable` z wyczerpanym limitem kończy się od razu. Dotyczy wejść spoza wznowień (`get_card` dla `pending`, import).
- `_clear_enrich_retry` (przejście do `ready`) zeruje licznik.

Z limitem 3 i odstępem 15 minut karta, której czegoś brakuje, robi najwyżej 3 dodatkowe przebiegi w ciągu godziny, a nie 96 na dobę.

### Ponowienie bez zmian

W `_persist_enrichment_result`, gałąź `learnable`:

- gdy karta była `learnable` przed przebiegiem, a nowa treść po `_guard_enrichment_lemma` i `sync_word_family` jest równa `card.content`, treści nie zapisujemy,
- `retry_at`, `enrichment_side_retries` i `enrichment_error` zapisuje wtedy jedno `update(LearningCard)` z jawnym `updated_at=LearningCard.updated_at`. Jawna wartość wyłącza `onupdate=func.now()`, więc `sync/pull` nie odsyła karty jeszcze raz,
- zamiast `enrich_ready` idzie `_log_enrich_pipeline(card, "enrich_side_retry", ...)` z licznikiem,
- `notify_cards_ready` nie jest wołane.

`_enrich_lemma_staged` dla karty, która była `learnable` (ścieżka `finish_side_jobs`), przekazuje `notified=True`. Powiadomienie idzie tylko przy pierwszym `learnable` (`on_core`) i przy przejściu do `ready`.

### `enrichment_active`

`CardResponse.enrichment_active: bool = False`. `_card_response` ustawia `card.id in card_jobs._claimed`. W `get_card` liczyć to po ewentualnym `spawn_enrich`, który dodaje kartę do `_claimed` synchronicznie.

`_claimed` obejmuje też czas czekania na semafor. Karta w kolejce do wzbogacenia jest więc aktywna, co jest prawdą z punktu widzenia użytkownika.

`/sync/pull` i listy też budują `CardResponse`. Tam pole może zostać `False`. Telefon używa go tylko przy odpytywaniu `GET /cards/{id}`.

## Zachowanie telefonu

`CardResponse.enrichment_active: Boolean? = null` w `Models.kt`. `null` znaczy „stary serwer”.

Reguła odpytywania jednej karty, wspólna dla `HomeViewModel` i `LearningViewModel` (wydzielona do czystej funkcji, żeby dała się przetestować):

- karta wchodzi do odpytywania, gdy `EnrichmentStatus.needsPoll(status)` albo ma `card_activity_status` (bez zmian),
- dla każdej karty telefon pamięta chwilę pierwszego odpytania w tej sesji ekranu,
- `learnable` wypada, gdy ostatnie `GET /cards/{id}` oddało `enrichment_active == false` albo minęły 3 minuty od pierwszego odpytania,
- `preparing` wypada, gdy `enrichment_active == false` (serwer czeka na `retry_at`, 15 minut) albo minęło 5 minut,
- `pending` wypada po 5 minutach,
- `enrichment_active == null`: działa tylko limit czasu,
- karta z `card_activity_status` zostaje do zmiany tego pola, jak dziś.

Karta, która wypadła, zostaje z dotychczasowym wyglądem: sekcje bez treści pokazują pusty stan bez kółka. Wraca do odpytywania przy następnym wejściu na ekran, po `sync/pull`, który przyniesie zmianę, albo po ręcznym odświeżeniu. Zbiór wyłączonych kart żyje w ViewModelu, nie w Room.

`LearningViewModel` zostawia limit 20 iteracji i dodaje tę samą regułę.

## Kroki

1. Migracja i kolumna. Wdrożyć sam serwer z kolumną nieużywaną, jeśli deploy ma iść w dwóch krokach.
2. `has_required_inflection` w `lsp/enrichment.py`, przepięcie `content_is_complete` i `finish_side_jobs`, testy.
3. „Odmiana nie dotyczy” w `finish_side_jobs` i `run_lemma_enrichment`, testy.
4. Limit ponowień i ponowienie bez zmian, testy.
5. `enrichment_active`.
6. Telefon: model, reguła odpytywania, test.

## Sprawdzenie

Testy serwera (`pytest`):

- `has_required_inflection`: zwrot bez rodzajnika z `inflection = {"verbs": {"tenses": null, "non_finite": null}}` daje `False`. Z `inflection_status = "not_applicable"` daje `True`. `la red social` daje `True` bez odmiany. Czasownik bez form daje `False`.
- `finish_side_jobs` dla `de repente` z odmianą z samymi `null`: model odmiany jest wołany. Atrapa zwraca pustą odmianę, więc treść dostaje `inflection_status = "not_applicable"`. Atrapa rzuca wyjątek, więc pola nie ma.
- Czasownik `enviar` z pustą odpowiedzią odmiany nie dostaje `not_applicable`.
- Karta `learnable` z `enrichment_side_retries = 2` i błędem: po przebiegu licznik 3, `retry_at = None`. `_resume_pending_enrichment` jej nie wybiera.
- Ponowienie bez zmian: `updated_at` karty się nie zmienia, `notify_cards_ready` (atrapa) nie jest wołane, w logu jest `enrich_side_retry`.
- `GET /cards/{id}` w trakcie wzbogacania oddaje `enrichment_active = true`, po zakończeniu `false`.

Testy telefonu (`./gradlew testDebugUnitTest`):

- reguła odpytywania: `learnable` z `enrichment_active=false` wypada od razu, z `true` zostaje do 3 minut, z `null` zostaje do 3 minut, `pending` zostaje do 5 minut, karta z `card_activity_status` zostaje.

Produkcja (tylko odczyt, po deployu i jednym obrocie watchdoga):

- siedem kart z rozdziału 0 (`de repente`, `bola de helado`, `por casualidad`, `a ver`, `a la vez`, `como si no fuera poco`, `at the same time`) ma `enrichment_status = 'ready'` i `content->>'inflection_status' = 'not_applicable'`, albo zostają `learnable` z `enrichment_side_retries = 3` i `enrichment_retry_at is null`, jeśli brakuje im czegoś innego (sprawdzić, czego),
- `select count(*) from app_logs where event = 'enrich_ready' and created_at > now() - interval '1 day'` spada z około 2000 do liczby nowych kart z dnia (rząd kilkudziesięciu),
- `select count(*) from learning_cards where deleted_at is null and enrichment_status = 'learnable' and enrichment_retry_at is not null` maleje do kart w trakcie,
- `updated_at` kart z wyczerpanym limitem przestaje rosnąć,
- log HTTP Railway z 15 minut na ekranie głównym nowej wersji telefonu: żadna karta `learnable` nie jest pytana dłużej niż 3 minuty, a karta z `enrichment_active=false` najwyżej raz.

## Ryzyka

- Fałszywe „nie dotyczy” dla zwrotu czasownikowego, gdy model raz odda puste formy. Taka karta trafia do cache jako kompletna. Ograniczenie: tylko `phrase` i `construction` i tylko poprawna odpowiedź modelu. Dla `pagar a plazos` i podobnych model oddaje formy, co sprawdza test z prawdziwym zapisem odpowiedzi w `tests/fixtures`, jeśli taki jest, albo ręczny przebieg przed deployem.
- Karta z wyczerpanym limitem nie dojdzie do `ready` sama. To jest zamierzone. Ponowne przetworzenie po zmianie kodu: wyzerować `enrichment_side_retries` jednym `UPDATE` na produkcji (osobna, świadoma decyzja, poza tym taskiem).
