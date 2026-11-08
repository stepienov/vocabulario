# Task 11. Import listy słów

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 7.

## Zakres

Serwer:

1. Limit 25 pozycji na zadanie (wklejka, plik, adres URL, ponowne sprawdzenie po `import_format`) i limit 25 kart importu na profil i dobę UTC.
2. Analiza: `import_classify` z `reasoning_effort="none"` i limitem 2500, bez `import_verify`, duplikaty jednym odczytem kart.
3. Zatwierdzenie: lekki zapis z taska 09 w jednej transakcji, `SAVEPOINT` na pozycję, bez hydracji i bez `spawn_enrich` w pętli.
4. Kolejka profilu: bramka w zadaniu wzbogacania, kolejność pozycji, następna karta po `learnable` (hasło) albo po zapisie wyniku (karta adaptacyjna).

Telefon:

5. Zakładki „Szukaj” i „Import” w Dodaj, kafelki z checkboxami, „Porzuć” i „Zatwierdź”, licznik dnia, napisy.

Poza zakresem: format pliku, parser wklejki, `import_format` (bez zmian), stary `POST /imports/validate`.

## Zależności

- Task 03: limit ponowień i wspólny warunek odmiany (karty importu przechodzą tę samą ścieżkę).
- Task 09: lekki zapis karty, `find_card_key_anywhere`, hydracja przed semaforem.
- Task 10: cztery wywołania i `learnable` po nauce, na które czeka kolejka.

## Pliki

Serwer:

- `backend/app/services/import_jobs.py`: `_insert_job`, `_run_analyze`, `_verify_ready_lemmas` (do usunięcia z przebiegu), `_run_commit`, `_create_card_for_item`, nowe `daily_import_used`, `spawn_next_import_card`,
- `backend/app/services/llm.py`: `analyze_import_classify`,
- `backend/app/services/card_jobs.py`: bramka kolejki w `_run_claimed_enrich`, wywołanie `spawn_next_import_card` po `learnable` i po wyniku adaptacyjnym,
- `backend/app/api/v1/imports.py`: błędy `import_too_many`, `import_daily_limit`, pola `daily_used`, `daily_limit` w `_progress`,
- `backend/app/schemas/__init__.py`: `ImportJobProgressResponse.daily_used`, `daily_limit`, `ImportJobItemResponse.list_name`,
- testy: `backend/tests/test_import_jobs.py`, `test_import_fixtures.py`.

Telefon:

- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeScreen.kt` (`AddTab`), `ImportUi.kt`,
- `android/app/src/main/java/com/vocabulario/app/data/imports/ImportController.kt`,
- `android/app/src/main/java/com/vocabulario/app/data/api/Models.kt` (pola postępu),
- `android/app/src/main/res/values*/strings.xml` i `scripts/i18n_pack.json`.

## Zachowanie serwera

### Limity

`MAX_IMPORT_ITEMS = 25`, `DAILY_IMPORT_LIMIT = 25`.

W `_insert_job`, przed wstawieniem zadania:

- liczba pozycji: `len(notes)`, a przy `kind == "raw_text"` (układ do `import_format`) liczba niepustych linii `raw_text`. Adres URL ma `notes` z `fetch_words_from_url`, więc liczy się tak samo. Ponad 25: `ImportTooManyError` → 400 `import_too_many`,
- `daily_import_used(db, profile_id) >= 25`: `ImportDailyLimitError` → 400 `import_daily_limit`.

`daily_import_used`:

```sql
SELECT count(*) FROM learning_cards c
JOIN import_jobs j ON j.id = c.import_job_id
WHERE j.profile_id = :profile_id
  AND j.status <> 'cancelled'
  AND c.created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
```

Bez warunku na `deleted_at`: karta usunięta później dalej zajmuje limit. Karty anulowanego zadania (tombstony z `finalize_cancel`) nie zajmują.

Po `import_format` w `_run_analyze`: liczba notatek ponad 25 kończy zadanie błędem `import_too_many`, bez klasyfikacji.

Zatwierdzenie: `len(item_ids zaznaczonych) > 25 - daily_import_used` daje 400 `import_daily_limit` i zadanie zostaje na ekranie zatwierdzenia.

`_progress` i `GET /imports/jobs/active` niosą `daily_used` i `daily_limit = 25`. Telefon potrzebuje licznika także bez aktywnego zadania, więc `GET /imports/jobs/active` przy braku zadania oddaje obiekt z samym licznikiem albo dochodzi `GET /imports/daily?profile_id=…`. Wybór należy do implementującego, telefon musi mieć jedno z nich przed otwarciem okna importu.

### Analiza

- `analyze_import_classify`: `reasoning_effort="none"`, `max_tokens=2500` (dziś 6000), bez temperatury. Prompt bez zmian.
- `_verify_ready_lemmas` nie jest wołane. Funkcja i `analyze_import_verify_lemmas` do usunięcia, jeśli `rg` nie pokaże innego użycia.
- Duplikaty: jeden odczyt `select(LearningCard.id, LearningCard.lemma_l2, LearningCard.pos, LearningCard.deck_id)` żywych kart profilu i jeden odczyt list profilu. Dla każdej pozycji `select_live_card_for_lemma` w pamięci. Pozycja duplikatu dostaje `existing_card_id` i nazwę listy (`deck_id` puste: lista systemowa). `ImportJobItemResponse.list_name`.
- Commit co 10 pozycji zostaje tylko dla postępu. Bez odczytu kart w pętli.

### Zatwierdzenie

`_run_commit`:

- jeden odczyt kart profilu (jak przy analizie) na początek, zbiór uzupełniany o każdą wstawioną kartę,
- jedna transakcja, każda pozycja w `async with db.begin_nested()`:
  - `select_live_card_for_lemma` na zbiorze: trafienie, to pozycja `duplicate` z `already_on_list`,
  - `LearningCard` z `build_pending_content`, `pending`, `import_job_id`, `deck_id`, `srs_state` na liście systemowej, `item.created_card_id`,
  - `IntegrityError` w savepoincie (równoczesne ręczne dodanie): pozycja `duplicate`, reszta idzie dalej,
- bez `hydrate_from_lexical_cache` i bez `spawn_enrich` w pętli,
- anulowanie sprawdzane przed transakcją. W trakcie jednej transakcji anulowanie czeka na jej koniec, więc „albo karty są, albo ich nie ma”,
- zadanie `done` w tej samej transakcji,
- po commicie jedno `spawn_next_import_card(profile_id)`.

Pętla prób (`COMMIT_MAX_ATTEMPTS`, `COMMIT_BACKOFF_S`) przestaje być potrzebna na poziomie pozycji. Błąd całej transakcji (połączenie) zostawia zadanie w `commit`, a `resume_unfinished_jobs` je powtarza, bo żadna karta nie powstała.

### Kolejka profilu

Kolejka to karty `pending` z `import_job_id` danego profilu, nieusunięte, w kolejności `(import_jobs.created_at, import_job_items.ordinal)` przez `import_job_items.created_card_id`.

```python
async def import_queue_head(db, profile_id) -> UUID | None
async def spawn_next_import_card(profile_id) -> None   # spawn_enrich(head), gdy head nie jest w _claimed
```

Bramka w `_run_claimed_enrich`, po `_hydrate_before_queue` (task 09), przed semaforem:

- karta bez `import_job_id`: bez zmian,
- karta importu, która nie jest głową kolejki swojego profilu: zadanie kończy się bez zmian w bazie.

Hydracja jest przed bramką, więc karta ze słowem z `lexical_entries` dostaje treść od razu po dojściu do głowy, bez modelu, a kolejka idzie dalej.

Bramka jest w zadaniu, nie w miejscu wywołania, bo `get_card` (karta `pending`), `resume_pending_enrichment` i watchdog (`pending` starsze niż 45 s) wołają `spawn_enrich` same. Stan kolejki jest w bazie, więc przeżywa restart.

Punkt 7 umieszcza bramkę w `_enrich_card_unlocked`. Po tasku 09 wejściem zadania jest `_run_claimed_enrich` i tam bramka stoi przed `_enrich_semaphore()`, żeby karta czekająca w kolejce nie zajmowała jednego z trzech miejsc semafora.

Kiedy następna karta:

- karta hasła zapisała `learnable` (`on_study` w tasku 10), po commicie: `spawn_next_import_card(profile_id)`. Powiązane tej karty liczą się dalej, a kolejka już idzie,
- w `finally` `_run_claimed_enrich` dla karty importu, która przeszła bramkę: świeży odczyt statusu i `spawn_next_import_card`, gdy karta nie jest już `pending`. To łapie wynik adaptacyjny (`_persist_enrichment_result`), błąd z `_apply_enrich_retry` (`preparing`), timeout i `_mark_enrich_failed`, bo wszystkie commitują przed `finally`. Warunek „nie `pending`” chroni przed pętlą, w której karta puszcza samą siebie,
- usunięcie karty importu (`deleted_at`): `spawn_next_import_card` po commicie usunięcia.

`spawn_next_import_card` nie puszcza głowy, która jest w `_claimed`. Karta głowy, która jest właśnie wzbogacana, ma status `pending` do zapisu `learnable`, więc zostaje głową i nikt jej nie wyprzedza.

## Zachowanie telefonu

Według punktu 7, „Co użytkownik robi” i tabeli napisów:

- `AddTab`: dwie zakładki, domyślnie „Szukaj”, także po powrocie na ekran. Import nie chowa szukania,
- „Import”: przycisk „Importuj” otwiera dotychczasowe okno (wklejka albo plik, lista docelowa, nowa lista). Wyłączony przy aktywnym zadaniu albo `daily_used >= 25` (napis `import_daily_used`). Przy wolnych miejscach napis `import_daily_remaining`,
- w trakcie analizy: przycisk wyłączony, pod nim kółko i `import_analyzing`, bez etapów,
- ekran zatwierdzenia: sekcje „Błędy” (słowo i powód) i „Duplikaty” (słowo i nazwa listy) otwarte, kafelki poprawnych z checkboxem zaznaczonym na starcie, „Porzuć” (dotychczasowe anulowanie) i „Zatwierdź” (commit z `item_ids` zaznaczonych). „Zatwierdź” wyłączone, gdy zaznaczonych jest więcej niż `25 - daily_used`,
- akordeon „Wejdzie / Duplikaty / Błędy” znika,
- błąd `import_too_many` przy zakładaniu: `import_too_many_lines`,
- po zatwierdzeniu zakładka wraca do przycisku. Karty są na liście docelowej z kółkami i odpytywaniem z limitem z taska 03,
- `import_limit_exceeded` przestaje być używane (klucz można zostawić w plikach),
- `ImportController` odpytuje postęp co 1 s tylko w trakcie analizy i zapisu, jak dziś.

Napisy z tabeli punktu 7 trybem z README (paczka `scripts/i18n_pack.json` i `i18n_apply.py`).

## Kroki

1. Serwer: limity i licznik dnia, testy.
2. Serwer: analiza bez `import_verify`, duplikaty jednym odczytem, `list_name`.
3. Serwer: zatwierdzenie w jednej transakcji.
4. Serwer: kolejka i bramka, testy z atrapą modelu.
5. Wdrożenie serwera. Stary telefon działa: dostaje szybszy ekran zatwierdzenia, a jego akordeon czyta te same pola.
6. Telefon.

## Sprawdzenie

Testy serwera (`pytest`):

- 26 linii słowo w linii: 400 `import_too_many`, zadanie nie powstaje. 26 linii w układzie do `import_format`: zadanie powstaje, po formacie kończy się `import_too_many` bez klasyfikacji (atrapa `import_classify` nie wołana),
- 25 kart importu dziś, w tym 3 usunięte: 400 `import_daily_limit`. 25 kart, z czego 10 z anulowanego zadania: zadanie powstaje,
- zatwierdzenie 5 pozycji, z których jedna koliduje z równoczesnym ręcznym dodaniem (wstawionym przed transakcją): 4 karty, 1 duplikat, zadanie `done`,
- po zatwierdzeniu 3 haseł z atrapą modelu: `llm_usage` (atrapa) pokazuje `enrich_study` drugiej karty dopiero po `learnable` pierwszej. `GET /cards/{id}` trzeciej karty w tym czasie nie tworzy wywołania modelu,
- restart (wywołanie `resume_pending_enrichment`) w trakcie kolejki: rusza tylko głowa,
- karta importu ze słowem z `lexical_entries` w środku kolejki: dostaje `ready` od razu po dojściu do głowy, bez modelu.

Produkcja i telefon: lista „Jak sprawdzimy” z punktu 7, w całości. Dodatkowo:

- 25 linii polski → hiszpański: ekran zatwierdzenia po około 10 s od założenia zadania (dziś przy 30 słowach 51–62 s według `import_job_events`), jedno `import_classify` z `reasoning_tokens=0`, brak `import_verify`,
- zatwierdzenie 20 pozycji: zadanie `done` w ciągu 2 s (dziś przy 30 słowach 147–224 s).

## Ryzyka

- Kolejka po jednej karcie wydłuża czas do `ready` ostatniej karty importu: około 25 × 5 s do `learnable` przy typowym haśle. Karty i tak są od razu na liście i każda wchodzi do ćwiczenia po swojej nauce. Przyjęte w punkcie 7.
- Karta, która utknie w `pending` bez zadania (proces padł), blokuje kolejkę profilu do najbliższego wznowienia albo watchdoga (45 s). Watchdog podejmuje ją jako głowę.
