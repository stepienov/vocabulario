# Import i analiza jako zadania backendowe — analiza przyczyn i plan naprawy

Data: 2026‑08‑16  
Status: **analiza + kontrakt implementacyjny** (bez zmian w kodzie).  
Powiązane: `docs/plan-import-refaktor-2026-08-11.md`, `docs/spec-import-implementacja-v1.md`.

Ten dokument zastępuje decyzję z specu v1, że „trwałość zadania = singleton Hilt + DataStore na telefonie”.  
Nowe źródło prawdy: **PostgreSQL + worker na backendzie**. Telefon tylko startuje zadanie, odpytuje status i pokazuje go w zakładce **Dodaj**.

---

## 0. Co użytkownik wymaga (źródło prawdy)

1. **Analiza** (plik albo wklejka) oraz **import słówek** wolno przerwać **wyłącznie** przyciskiem **Przerwij**.
2. **Przerwij** cofa **całą** akcję: żadne słowo z tego przebiegu nie może zostać u użytkownika (także te już zapisane w trakcie importu).
3. Zwykłe użycie telefonu **nie może** przerywać procesu: wygaszenie ekranu, inna aplikacja, przeglądanie Vocabulario, ustawienia, nauka, zminimalizowanie, a nawet **twarde zamknięcie aplikacji**.
4. Status ma być zawsze widoczny w zakładce **Dodaj**. Dopóki akcja trwa: brak importu, wklejki i szukania słów. Postęp: analiza = **etap** (bez udawanego `x/total` w trakcie LLM); import = **etap + `x/total` + aktualne słowo**. Odpytywane po `job_id` (patrz §5.3a / §7.3).
5. Po analizie użytkownik ma zobaczyć trzy **zwijane** listy (wejdzie / duplikat / błąd) — §7.3.
6. Import dostaje już przygotowane przez analizę pozycje. Błędy zapisu **ponawiamy do 3 razy**.
7. Każda akcja i każde niepowodzenie ma wylądować w **tabelach PostgreSQL**, żeby administrator widział *co* padło i *dlaczego*.
8. UI akcji = zakładka Dodaj (nie modal „wiszący” nad resztą aplikacji). Po ponownym otwarciu aplikacji: albo „analiza/import dalej trwa”, albo wyniki analizy i przejście do importu, albo podsumowanie.

Wniosek architektoniczny (twardy): **ani analiza, ani import nie mogą zależeć od żywego procesu Androida ani od jednego długiego HTTP request/response.**

### 0.1. Zablokowane decyzje (2026‑08‑16, user)

| # | Decyzja | Skutek w implementacji |
|---|---|---|
| 1 | **Brak limitu liczby pozycji** (unieważnia spec v1 „max 50”). Uzasadnienie: koszt tokenów i tak zostawia ślad w PG (lexical / karty), więc nie ucinamy talii sztucznym sufitem. | Żadnego `400 import_limit_50` na jobie. Zostają tylko limity **techniczne** już w kodzie: plik **80 MB**, wklejka **500_000** znaków (ochrona RAM, nie „max kart”). |
| 2 | **Jedna paczka LLM na całą analizę** (taniej). Analiza i tak jest krótsza niż import. | `_BATCH` = cała talia, jeden `analyze_import_classify` / jeden layout. W analizie **nie** ma płynnego `x/total` podczas LLM — tylko etap (`format` / `classify` / `layout`), potem szybki `dedup` z licznikiem. `x/total` per słowo jest w **imporcie**. |
| 3 | **Poll**, nie SSE. | `GET /imports/jobs/{id}/progress` co 1 s (5 s w tle). |
| 4 | **Jedna akcja na profil.** Drugi import: czeka albo Przerwij. | `409 import_job_active` + UI zablokowane. |
| 5 | Po analizie: **3 listy-akordeon**, domyślnie zwinięte: wejdzie / duplikat / błąd. Nagłówki **zawsze widoczne** (sticky). Tylko jedna rozwinięta naraz (rozwinięcie jednej zwija resztę). Da się zwijać/rozwijać także będąc na dole listy. Import = wszystkie z „wejdzie” (bez odhaczania pojedynczych w MVP). Przy nagłówku **Błędy**: ikona kopiowania → schowek `lemat1; lemat2; lemat3` (patrz §7.3a). | UI w zakładce Dodaj, nie modal. |

---

## 1. Mapowanie zgłoszeń na konkretny kod (dlaczego to się dzieje)

Poniższe objawy nie są „losowym bugiem UI”. Wynikają z modelu, w którym **praca żyje na telefonie**, a backend odpowiada tylko synchronicznie na pojedyncze strzały.

### 1.1. Symptom: analiza / import przerywa się po wygaszeniu ekranu albo zejściu z aplikacji

**Co jest dziś źródłem pracy**

| Faza | Gdzie leci | Plik | Co to znaczy |
|---|---|---|---|
| Analiza pliku | 1 długie `POST /imports/file` z telefonu | `ImportController.startFromFile` → `LearningRepository.ingestImportFile*` | Telefon **musi utrzymać TCP** aż LLM skończy |
| Analiza wklejki | 1 długie `POST /imports/ingest` | `ImportController.startFromPaste` | j.w. |
| Import vocabulario | pętla N × `POST /lists/{id}/words` **na kliencie** | `ImportController.commitVocabulario` | każde słowo = osobne żądanie z telefonu |
| Import preserve | 1 × `POST /imports/commit-display` z telefonu | `ImportController.commitPreserve` | zapis czeka na odpowiedź klienta |

Coroutine analizy/importu startuje w `ImportController` (`CoroutineScope(SupervisorJob() + Dispatchers.Default)`). To przeżywa zmianę zakładki, **ale nie przeżywa**:

- śmierci procesu (OEM, mało RAM, powrót z systemowego file pickera),
- Doze / ograniczenia sieci w tle po wygaszeniu ekranu,
- `callTimeout` OkHttp = **200 s** (`AppModule.provideOkHttpClient`),
- zerwania TCP (Wi‑Fi sleep, przełączenie sieci, OEM „battery saver”).

Backend **nie zapisuje** wyniku analizy nigdzie. Endpointy `ingest` / `file` robią całą pracę *w handlerze żądania* i oddają JSON. Jeśli klient się rozłączy, uvicorn/Starlette **anuluje task ASGI** → padają wywołania LLM w połowie, a po stronie PG nie ma śladu zadania.

**Dodatkowy, świadomy strzał w stopę** — przywracanie po restarcie aplikacji:

```56:66:android/app/src/main/java/com/vocabulario/app/data/imports/ImportController.kt
                ImportStatus.Processing -> {
                    publish(
                        ImportJobState(
                            status = ImportStatus.Error,
                            ...
                            error = strings.get(R.string.import_interrupted),
                        ),
                    )
                }
```

Spec v1 §2.4 **nakazał**: „Processing po restarcie → Error(Import przerwany)”.  
To jest dokładnie scenariusz „wyszedłem z aplikacji, nie wyłączałem jej, a po powrocie analiza nie żyje”. Android często zabija proces w tle *bez* gestu „force stop”. DataStore pamięta `Processing`, kontroler **celowo** zamienia to w błąd i **nie pyta backendu**, czy analiza czasem nie dobiegła.

### 1.2. Symptom: importuje się część, reszta to „błędy”

`commitVocabulario` idzie słowo po słowie. Przy błędzie sieci / timeout / 5xx:

```377:382:android/app/src/main/java/com/vocabulario/app/data/imports/ImportController.kt
            }.onFailure { e ->
                if (e is HttpException && e.code() == 409) {
                    duplicates++
                } else {
                    failed++
                }
            }
```

Nie ma retry. Słowa już zapisane **zostają**. Reszta, która nie zdążyła wylecieć z telefonu (ekran zgasł, proces umarł, sieć w tle ucięta), ląduje w `failed`. Użytkownik widzi „reszta to błędy”, choć to nie błędy językowe — to **zerwane HTTP z klienta**.

Po restarcie w trakcie `Committing` kontroler woła `resumeCommit()` od zera. Już utworzone karty wracają jako `409` → `duplicates`. Te, które znowu nie dolecą, znowu są `failed`. Raport kłamie w obie strony.

### 1.3. Symptom: po przerwanej analizie „Import fiszek” z błędem i wyszarzonym OK

Dwa ekrany mają ten sam tytuł PL **„Import fiszek”** (`import_start_title`):

1. **`ImportStartDialog`** — OK jest szare, gdy `canStart == false` (brak pliku / pusta wklejka / brak listy). Typowy przebieg: systemowy `OpenDocument` → śmierć procesu → `remember { pendingFileBytes }` ginie → dialog wraca bez pliku → OK szare. Użytkownik odczytuje to jako „analiza się wywaliła”.
2. **`ImportReviewDialog`** — OK jest szare, gdy `selectedCount == 0`. Jeśli analiza zwróci **same `invalid`** (albo `valid` puste), przycisk jest nieaktywny, a sekcja „nierozpoznane” wygląda jak lista błędów.

Dokładnie ten drugi przypadek produkuje `_vocabulario_lemma`: zwroty/konstrukcje **bez** `base_lemma` idą do `invalid`, a duplikaty wewnątrz pliku są **po cichu pomijane** (`if key in seen: continue`) — nie trafiają ani do valid, ani do raportu duplikatów.

Po restarcie w `Processing` użytkownik dostaje modal błędu (`ImportErrorDialog`, tytuł „Import zakończony”) z tekstem **„Import przerwany — spróbuj ponownie”**. To jest ten sam kod co §1.1.

### 1.4. Symptom: znika ślad wykonania

Stan importu żyje w:

- pamięci `ImportController` (ginie ze śmiercią procesu),
- DataStore `import_job_prefs` (przywraca `Processing` jako Error — ślad zamienia się w „przerwany”),
- **nigdzie na backendzie**.

Jeśli analiza na BE zdążyła się skończyć, a klient już nie słuchał — wynik jest stracony. Nie ma job_id, nie ma wiersza, nie ma jak wrócić i zobaczyć rezultat.

### 1.5. Symptom: modal / dialog zamiast zakładki Dodaj

Dziś:

| Stan | Gdzie UI |
|---|---|
| Processing / Committing | panel w zakładce Dodaj (`ImportStatusPanel`) — OK |
| Review | **modal** `ImportReviewDialog` nad całym Home |
| Done / Error | **modal** w `VocabularioAppRoot` nad *każdą* trasą |

To jest zgodne ze specem v1 i **niezgodne** z nowym wymaganiem: cała procedura ma się dziać w zakładce Dodaj aż do końca. Po zamknięciu aplikacji i powrocie użytkownik ma zobaczyć ten sam panel, nie „wiszący” dialog z wyszarzonym OK.

### 1.6. Czego analiza dziś w ogóle nie umie pokazać

- **Duplikat vs błąd.** Analiza (`resolve_import_vocabulario_entries`) nie woła `find_card_anywhere`. Duplikat względem kart użytkownika wychodzi dopiero przy zapisie jako HTTP 409. Wewnątrzpliku duplikaty są dropowane bez raportu.
- **Powód `invalid`.** Backend liczy `invalid_reason` w klasyfikatorze, ale API zwraca `invalid: list[str]` — same etykiety, bez przyczyny.
- **Diagnostyka admina.** Brak tabeli jobów. Enrichment ma `enrichment_error` na karcie; import nie ma nic. Nie da się po fakcie powiedzieć, czy padło LLM, timeout klienta, 409, czy klasyfikacja.

---

## 2. Architektura as-is (skrót, stan po M1)

```
[Dodaj] → dialog startu (plik/wklejka + tryb + lista)
       → ImportController.beginProcessing()
       → 1× HTTP ingest/file  (LLM w handlerze FastAPI, 10–180+ s)
       → Review (modal)
       → confirmCommit()
       → pętla addWordToList na telefonie  ALBO  1× commit-display
       → Done/Error (modal)
```

Backend:

- `POST /api/v1/imports/ingest` — wklejka, synchronicznie.
- `POST /api/v1/imports/file` — plik, synchronicznie.
- `POST /api/v1/imports/commit-display` — zapis preserve, synchronicznie, jedna transakcja.
- `POST /api/v1/lists/{id}/words` — jedno słowo + `BackgroundTasks(enrich_card)`.
- Brak tabeli `import_jobs`. Brak kolejki. Brak cancel. Brak retry importu.
- Limit wejścia: wklejka max 500_000 znaków; plik max 80 MB; `validate`/`commit-display` max 50 pozycji. **Twardy limit 50 nie jest egzekwowany w `ingest`/`file`** (spec v1 tego chciał, kod tego nie robi).
- Wzorzec tła, który już istnieje i działa: `enrich_card()` w `card_jobs.py` — `BackgroundTasks` + własne `async_session_factory`. **To jest enrichment karty, nie import.** Ginie przy restarcie workera, nie ma job row, nie ma cancel/rollback.

Android:

- `ImportController` @Singleton — przeżywa nawigację w *żywym* procesie.
- DataStore snapshot — przywraca Review/Done; Processing → Error; Committing → retry z telefonu.
- OkHttp: connect 15 s, read/write 180 s, **call 200 s**.
- Brak WorkManager / foreground service dla importu (i nawet gdyby był — nie spełni „zamknięta aplikacja”, bo praca i tak czeka na HTTP).

Dlatego poprzedni plan (M1: singleton + DataStore) **nie mógł** spełnić wymagań z §0. Naprawił tylko „zmieniłem zakładkę i zniknął pasek”. Nie naprawił wygaszenia, Doze, śmierci procesu, force-close.

Dalsze potwierdzenia z pełnego przeglądu kodu (nie zmieniają planu, zamykają wątpliwości „może już jest kolejka”):

- W konfiguracji jest `redis_url` i `llm_max_retries: 2` — **żadne nie jest podpięte**. `_chat_json` woła model raz; Redis nie jest używany. Nie dokładamy Celery/Redis w tym etapie — job row w PG wystarcza.
- `import_ai.resolve_import_words` jest importowane w `learning.py`, ale **nigdy nie wołane**. `LearningRepository.validateImport()` też nie jest na ścieżce `ImportController`. Jedna ścieżka usera = nowe `/imports/jobs`.
- `.xlsx/.xls` backend odrzuca z prośbą o CSV/TXT (`import_package.py`). Limit 50 jest w schemacie `validate` / `commit-display` i w stringach UI, **nie** w `ingest`/`file`.
- WorkManager jest tylko do sync / enrichment check / przypomnień o nauce — nie do importu. Foreground service nie istnieje.

---

## 3. Docelowy model: zadanie żyje w PostgreSQL

### 3.1. Zasada

```
Telefon                         Backend                         PG
──────                          ───────                         ──
POST start (plik/tekst)  →  zapis job + surowe notatki  →  import_jobs / items
                         ←  202 { job_id, status }      ←
                         →  (koniec HTTP w < 2 s)

                            worker (asyncio, niezależny
                            od gniazda klienta)
                              analiza AI, potem (po
                              potwierdzeniu) zapis kart
                              retry ×3, heartbeat
                                                              status, items,
                                                              events, card_ids

GET /imports/jobs/active ←  aktualny stan               ←
POST .../cancel          →  flaga cancel + rollback kart
```

Telefon **nigdy** nie trzyma otwartego requestu przez czas LLM.  
Telefon **nigdy** nie zapisuje kart w pętli.  
Zamknięcie aplikacji = utrata pollera, nie utrata pracy.

### 3.2. Dwie fazy, jeden job

Jeden wiersz `import_jobs` obsługuje całą procedurę:

```
queued
  → analyzing          (AI; brak kart)
  → review             (wynik analizy gotowy; user widzi ready / duplicate / failed)
  → committing         (zapis kart; retry ×3)
  → done
  → cancelling → cancelled   (rollback wszystkich kart tego joba)
  → failed             (twardy błąd fazy, nie pojedynczej pozycji)
```

Przejście `review → committing` wymaga jawnego `POST .../commit` z aplikacji (user widział duplikaty/błędy i potwierdził).  
Cancel dozwolony w `analyzing | review | committing`. W `done` / `failed` / `cancelled` — no-op.

**Jedno aktywne zadanie na (user, profile).** Unikalny indeks częściowy. Start drugiego, dopóki pierwsze jest w `queued|analyzing|review|committing|cancelling` → `409 import_job_active`.

### 3.3. Semantyka „Przerwij” (nowa, twarda)

Stary spec: „w Committing już utworzone zostają, wynik częściowy”.  
**To odrzucamy.**

Nowa semantyka:

- Cancel w `analyzing` / `review`: nic nie zapisano → status `cancelled`, items zostają do diagnostyki.
- Cancel w `committing`: worker przestaje tworzyć kolejne karty, **soft-delete wszystkich** `learning_cards` z `import_job_id = ten job` (wraz z `srs_state` przez CASCADE / istniejący soft-delete). Użytkownik nie widzi żadnego słowa z tego przebiegu.
- Enrichment w locie dla tych kart: worker enrichmentu widzi `deleted_at` / brak karty i wychodzi (już tak robi `enrich_card` gdy `card is None`).

To jest jedyny sposób, w którym „Przerwij” = brak skutków ubocznych.

---

## 4. Model danych PostgreSQL

Tworzymy trzy tabele. `Base.metadata.create_all` + wpisy w `backend/app/db/migrations.py` (jak reszta projektu, bez Alembica).

### 4.1. `import_jobs`

| Kolumna | Typ | Sens |
|---|---|---|
| `id` | UUID PK | identyfikator zadania |
| `user_id` | UUID FK users | właściciel |
| `profile_id` | UUID FK language_profiles | para językowa |
| `list_id` | UUID FK word_lists | lista wybrana **przed** startem |
| `phase` | TEXT | `analyze` \| `commit` — która faza aktualnie / ostatnia |
| `status` | TEXT | maszyna z §3.2 |
| `stage` | TEXT | drobniejszy krok w fazie — patrz §5.3a (`queued`, `format`, `classify`, `layout`, `dedup`, `write`, `rollback`, …) |
| `current_ordinal` | INT NULL | 0-based index pozycji, nad którą worker teraz siedzi |
| `current_label` | TEXT NULL | etykieta tej pozycji („casa \| dom”) — do UI |
| `current_attempt` | INT | 1..3 przy zapisie; 0 poza commitem |
| `source_kind` | TEXT | `file` \| `paste` \| `url` |
| `source_name` | TEXT | nazwa pliku albo etykieta „Wklejka” |
| `mode` | TEXT | `vocabulario` \| `preserve` |
| `cancel_requested` | BOOL | ustawiane natychmiast przez POST cancel |
| `processed` | INT | ile pozycji skończonych w bieżącej fazie |
| `total` | INT | ile pozycji w fazie |
| `ready_count` | INT | po analizie: do importu |
| `duplicate_count` | INT | po analizie: już są u usera albo w pliku |
| `failed_count` | INT | po analizie / po commicie: nie weszło |
| `created_count` | INT | po commicie: faktycznie utworzone (przed ewentualnym rollbackiem = 0) |
| `error_code` | TEXT | stabilny kod (`llm_timeout`, `import_empty`, `worker_crash`, …) |
| `error_message` | TEXT | komunikat dla usera (i18n key albo krótki tekst) |
| `started_at` | timestamptz | start fazy |
| `heartbeat_at` | timestamptz | worker żyje (co ~5 s) |
| `finished_at` | timestamptz | terminal |
| `created_at` / `updated_at` | timestamptz | audyt |
| `input_sha256` | TEXT | idempotencja / diagnostyka |
| `input_meta` | JSONB | `{filename, bytes, notes, lang_pair}` — **bez** pełnego pliku 80 MB |

Indeksy:

- `ix_import_jobs_user_created (user_id, created_at DESC)`
- `ix_import_jobs_status (status)`
- **UNIQUE** `uq_import_jobs_one_active (user_id, profile_id) WHERE status IN ('queued','analyzing','review','committing','cancelling')`

Surowy plik: parsujemy **w krótkim POST** (`load_raw_import` / `load_text_import` jest tani) i zapisujemy już **notatki** w `import_job_items.raw_note`. Nie trzymamy `.apkg` w PG.

### 4.2. `import_job_items`

Jedna pozycja = jedna notatka / jedno słowo.

| Kolumna | Typ | Sens |
|---|---|---|
| `id` | UUID PK | |
| `job_id` | UUID FK import_jobs ON DELETE CASCADE | |
| `ordinal` | INT | kolejność w źródle |
| `raw_note` | JSONB | pola źródłowe `["front","back",…]` |
| `input_label` | TEXT | to, co user widzi („casa \| dom”) |
| `verdict` | TEXT | `pending` \| `ready` \| `duplicate` \| `failed` |
| `verdict_phase` | TEXT | `analyze` \| `commit` — która faza ustaliła werdykt |
| `reason_code` | TEXT | `already_on_list`, `in_file_duplicate`, `no_lemma`, `llm_invalid`, `http_5xx`, `timeout`, … |
| `reason_detail` | TEXT | dokładny komunikat / traceback skrócony (dla admina) |
| `lemma` | TEXT | po analizie |
| `pos` | TEXT | |
| `gloss` | TEXT | |
| `entry_kind` | TEXT | |
| `lexical_entry_id` | UUID NULL | |
| `display` | JSONB NULL | tryb preserve |
| `existing_card_id` | UUID NULL | gdy duplicate |
| `created_card_id` | UUID NULL | gdy commit utworzył kartę (do rollbacku) |
| `attempt` | INT | 0..3 przy commicie |
| `last_error` | TEXT | ostatni wyjątek zapisu |

Unikalność: `(job_id, ordinal)`.

### 4.3. `import_job_events` — dziennik diagnostyczny (to jest tabela „żebym wiedział dlaczego”)

Append-only. Każdy istotny moment.

| Kolumna | Typ | Sens |
|---|---|---|
| `id` | bigserial / UUID | |
| `job_id` | UUID FK | |
| `item_id` | UUID NULL | null = event całego joba |
| `at` | timestamptz | |
| `level` | TEXT | `info` \| `warn` \| `error` |
| `event` | TEXT | `job_created`, `analyze_started`, `llm_call`, `llm_ok`, `llm_fail`, `item_verdict`, `commit_started`, `item_retry`, `item_created`, `cancel_requested`, `rollback_started`, `rollback_done`, `worker_heartbeat_stale`, `worker_resumed`, … |
| `payload` | JSONB | dowolny kontekst: model, latency_ms, http_status, exception_type, exception_message, tokens, batch_index, attempt |

Admin (na start: SQL / przyszły panel):

```sql
SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT 50;
SELECT * FROM import_job_items WHERE job_id = :id ORDER BY ordinal;
SELECT * FROM import_job_events WHERE job_id = :id ORDER BY at;
```

Po tym widać: user X, plik Y, analiza 40 s, item 17 `no_lemma`, commit item 4 padł `TimeoutError` dwa razy i za trzecim wszedł, cancel w 00:41, rollback 12 kart.

### 4.4. Znacznik na karcie (rollback)

Dodać kolumnę:

```
learning_cards.import_job_id UUID NULL REFERENCES import_jobs(id) ON DELETE SET NULL
```

+ indeks. Każda karta z commitu dostaje ten id. Cancel = `UPDATE learning_cards SET deleted_at = now() WHERE import_job_id = :id AND deleted_at IS NULL` (spójnie z istniejącym soft-delete / sync).

Nie polegamy wyłącznie na `import_job_items.created_card_id` — to backup; źródłem rollbacku jest kolumna na karcie.

---

## 5. Kontrakt API

Wszystko pod `/api/v1`. Auth jak dziś. Stare `POST /imports/ingest|file|commit-display` zostają na czas migracji (e2e/skrypty), aplikacja Android **przestaje ich używać** do ścieżki użytkownika.

### 5.1. `POST /imports/jobs`

Body (JSON wklejka / URL):

```json
{
  "profile_id": "…",
  "list_id": "…",
  "mode": "vocabulario",
  "text": "casa\tdom\nperro\tpies"
}
```

Albo multipart: `profile_id`, `list_id`, `mode`, `file`.

Zachowanie (musi wrócić w **< 2 s**, bez LLM):

1. Walidacja profilu, listy, online-only zostaje po stronie klienta (BE i tak sprawdzi).
2. Parsowanie `load_text_import` / `load_raw_import` / URL → notatki.
3. Pusty deck → `400 import_empty`.
4. **Brak limitu liczby notatek** (§0.1). Pusty deck → `400 import_empty`. Plik > 80 MB / wklejka poza schematem — jak dziś, błąd formatu/rozmiaru, nie „za dużo kart”.
5. INSERT `import_jobs` status=`queued` + INSERT items `verdict=pending`.
6. `asyncio.create_task(run_import_job(job_id))` **po commicie transakcji** (nie `BackgroundTasks` FastAPI — te giną razem z requestem i nie wracają po restarcie).
7. Odpowiedź `202`:

```json
{ "job_id": "…", "status": "queued", "phase": "analyze", "processed": 0, "total": 42 }
```

Konflikt aktywnego joba → `409 import_job_active` + body z `job_id` istniejącego (klient przełącza się na niego zamiast błądzić).

### 5.2. `GET /imports/jobs/active?profile_id=`

Zwraca aktywny job albo `404` / `{ "job": null }`.  
Używane przy starcie aplikacji i przy wejściu w Dodaj.

### 5.3. `GET /imports/jobs/{id}`

Pełny stan do UI:

```json
{
  "job_id": "…",
  "status": "review",
  "phase": "analyze",
  "source_name": "quizlet1.txt",
  "mode": "vocabulario",
  "list_id": "…",
  "list_name": "Oczekujące",
  "processed": 42,
  "total": 42,
  "ready_count": 30,
  "duplicate_count": 8,
  "failed_count": 4,
  "created_count": 0,
  "error_code": null,
  "error_message": null,
  "items": [
    {
      "id": "…",
      "ordinal": 0,
      "input_label": "casa | dom",
      "verdict": "ready",
      "reason_code": null,
      "lemma": "la casa",
      "gloss": "dom",
      "pos": "noun"
    },
    {
      "id": "…",
      "ordinal": 1,
      "input_label": "perro | pies",
      "verdict": "duplicate",
      "reason_code": "already_on_list",
      "lemma": "el perro",
      "existing_card_id": "…"
    },
    {
      "id": "…",
      "ordinal": 2,
      "input_label": "volver a hacer algo | …",
      "verdict": "failed",
      "reason_code": "no_lemma",
      "reason_detail": "phrase without base_lemma"
    }
  ]
}
```

W `analyzing` / `committing` lista `items` w tym endpoincie jest **opcjonalna** (`?include_items=0` domyślnie gdy status busy). Pełna lista obowiązkowa w `review` / `done` / `failed` / `cancelled`. Do pętli postępu telefon **nie** woła tego fat response — woła smukły §5.3a.

### 5.3a. Postęp na żywo — `GET /imports/jobs/{id}/progress`

**Tak, da się — i to jest właściwy kontrakt.** Jeden endpoint, ten sam kształt dla analizy i dla importu. Telefon odpytuje go w kółko po `job_id` (oraz `GET /imports/jobs/active` przy starcie, żeby odzyskać `job_id` po force-close).

To **nie** jest WebSocket ani SSE w MVP. Powody:

- po zabiciu aplikacji poll sam wraca,
- proxy/timeouty nie trzymają długiego gniazda,
- worker i tak zapisuje stan w PG — odczyt jest tani.

SSE można dołożyć później jako optymalizację; źródłem prawdy zostaje wiersz joba.

Odpowiedź (zawsze < 1 KB, bez listy itemów):

```json
{
  "job_id": "…",
  "status": "analyzing",
  "phase": "analyze",
  "stage": "classify",
  "source_name": "quizlet1.txt",
  "mode": "vocabulario",
  "processed": 16,
  "total": 42,
  "current_ordinal": 16,
  "current_label": "volver a hacer algo | robić coś znowu",
  "current_attempt": 0,
  "ready_count": 12,
  "duplicate_count": 3,
  "failed_count": 1,
  "created_count": 0,
  "cancel_requested": false,
  "heartbeat_at": "2026-08-16T08:41:02Z"
}
```

`status` + `stage` czytamy tak:

| `status` | `stage` | Co user widzi (i18n) |
|---|---|---|
| `queued` | `queued` | „W kolejce…” |
| `analyzing` | `format` | „Rozpoznaję układ pliku…” — **bez** `x/total` (1 wywołanie LLM na całość, nie da się per słowo) |
| `analyzing` | `classify` | „Analizuję słowa…” — spinner, **bez** x/total (jeden LLM na całość) |
| `analyzing` | `layout` | „Układam fiszki…” — preserve, 1–2 LLM na talię; potem materializacja per karta z licznikiem |
| `analyzing` | `dedup` | „Sprawdzam duplikaty” + `x / total` + etykieta |
| `review` | `review` | panel trzech sekcji (to już nie jest progress) |
| `committing` | `write` | „Zapisuję na listę” + `7 / 30` + „la casa” + gdy retry: „próba 2/3” |
| `cancelling` | `rollback` | „Anulowanie i cofanie zmian…” + opcjonalnie `x / created` |
| `done` / `failed` / `cancelled` | — | panel końcowy |

`processed` / `total` / `current_*` worker **zapisuje w PG przed** długim krokiem i **po** nim. Poll widzi prawdę z bazy, nie z pamięci procesu.

#### Co da się pokazać co słowo, a czego nie (granice fizyczne)

Dziś analiza to synchroniczne LLM w handlerze. Po przeniesieniu na workera:

1. **`ensure_deck_segmented` / `analyze_import_format`** — **jedno** wywołanie na cały plik (`import_format.py`). Nie ma „słowa 3/40”. UI: spinner + etap `format`, `total` może być jeszcze 0 albo szacunek z surowych linii. Nie udajemy `x/total`.
2. **`analyze_import_classify`** — **jedna paczka = cała talia** (§0.1). Etap `classify`, spinner, bez `x/total` aż LLM wróci. Potem `dedup` z licznikiem. Jeśli kontekst modelu nie uniesie ogromnej talii — te pozycje / job dostają `failed` z `reason_code=llm_fail` (widać w PG), **nie** ucinamy z góry do 50.
3. **`analyze_import_layout` (preserve)** — 1–2 wywołania na **całą** talię (szablon). Etap `layout` bez licznika. Potem materializacja + `dedup` z `x/total`.
4. **Dedup `find_card_anywhere`** — per pozycja, milisekundy. Po classify/layout worker przechodzi item po itemie, ustawia werdykt, bump `processed`. Tu licznik jest płynny.
5. **Commit / zapis** — naturalnie per karta. `processed` rośnie po każdej zamkniętej pozycji. `current_attempt` = która z 3 prób. To jest główny żywy licznik, którego user oczekuje.

Nie da się (i nie będziemy udawać): procent *wewnątrz* jednego wywołania LLM. W `classify`/`format`/`layout` UI pokazuje etap + spinner.

#### Poll po stronie klienta

| Kiedy | Co woła | Interwał |
|---|---|---|
| `queued` / `analyzing` / `committing` / `cancelling` i apka na wierzchu | `GET …/progress` | **1 s** |
| to samo, apka w tle | `GET …/progress` | 5 s (oszczędność; job i tak leci) |
| start apki / wejście w Dodaj | `GET …/active` → jeśli jest `job_id`, dalej `progress` | raz, potem pętla |
| przejście do `review` / `done` / `failed` | `GET …/{id}?include_items=1` | raz (pełna lista) |

Zerwany poll (ekran zgasł, brak sieci) **nic nie psuje**. Kolejny cykl czyta ten sam wiersz.

`GET /imports/jobs/active` zwraca ten sam kształt co `progress` (plus `job_id`), żeby nie dublować kontraktów.

### 5.4. `POST /imports/jobs/{id}/commit`

Dozwolone tylko w `review`. Body opcjonalne:

```json
{ "item_ids": ["…"] }
```

Brak `item_ids` = importuj wszystkie `verdict=ready`.  
Duplikaty i failed **nie idą** do commitu (user je widzi, ale nie zapisujemy ich jako kart).

Status → `committing`, start workera fazy commit (albo ten sam task, jeśli jeszcze żyje; zwykle nowy `create_task`).

### 5.5. `POST /imports/jobs/{id}/cancel`

Idempotentne. Ustawia `cancel_requested=true` natychmiast (osobny krótki commit), status `cancelling`. Worker w najbliższym checkpointcie:

1. przestaje analizować / zapisywać,
2. rollback kart,
3. status `cancelled`, event `rollback_done`.

Jeśli worker nie żyje (crash) — endpoint cancel **sam** robi rollback (karty i tak mają `import_job_id`).

### 5.6. `GET /imports/jobs` (admin)

`role == admin` (kolumna `users.role` już jest). Filtry: `user_id`, `status`, `from`, `to`.  
`GET /imports/jobs/{id}/events` — pełny dziennik.

Na MVP wystarczy ten endpoint + SQL. Panel UI admina **poza** tym dokumentem.

---

## 6. Worker backendowy

### 6.1. Uruchamianie

Nowy moduł `backend/app/services/import_jobs.py`:

- `async def run_import_job(job_id: UUID) -> None` — własna sesja (`async_session_factory`), jak `enrich_card`.
- Checkpoint co pozycję / co batch: `if job.cancel_requested: return await finalize_cancel(job)`.
- **Progress write** (ten sam UPDATE): `stage`, `processed`, `total`, `current_ordinal`, `current_label`, `current_attempt`, `heartbeat_at` — **zanim** poleci LLM/zapis i **zaraz po**. Bez tego poll pokazuje stare dane przez cały batch.
- Heartbeat: `heartbeat_at = now()` przy każdym progress write (nie rzadziej niż co ~5 s, nawet gdy LLM jeszcze leci — osobny tick w tasku jest OK).
- Każdy wyjątek nieobsłużony: status `failed`, `error_code=worker_crash`, event z tracebackiem. **Nie zostawiać** statusu `analyzing` bez serca.

Nie używamy Celery/Redis w tym etapie. Jeden proces uvicorn + PG + jedno zadanie na profil. Jeśli kiedyś będzie wielu workerów — job row + `SELECT … FOR UPDATE SKIP LOCKED` da się dołożyć bez zmiany API.

### 6.2. Wznowienie po restarcie serwera (to jest „nawet po zabiciu aplikacji **i** deploju”)

W `lifespan` (`backend/app/main.py`), po `create_all` / migracjach:

```
SELECT id FROM import_jobs
WHERE status IN ('queued','analyzing','committing','cancelling')
```

Dla każdego: `asyncio.create_task(run_import_job(id))` + event `worker_resumed`.

Dodatkowo watchdog (co 30 s, ten sam lifespan):

- jeśli `status IN (analyzing, committing)` AND `heartbeat_at < now() - 90s` → uznaj worker za martwy, wznów (albo `failed` po N wznowieniach, event `worker_heartbeat_stale`).

Dzięki temu:

- zabicie aplikacji na telefonie → **zero efektu** na job,
- restart uvicorn → job wraca,
- kill -9 workera → watchdog wznawia po starcie.

### 6.3. Faza analizy

Reuse istniejącego kodu, **nie** przepisywać parserów:

1. Złóż `RawImportDeck` z `import_job_items.raw_note`.
2. `ensure_deck_segmented` + `resolve_import_vocabulario_entries` **albo** `resolve_import_display_cards`.
3. Postęp w `GET …/progress` (§5.3a), zgodnie z §0.1:
   - klasyfikacja vocabulario: **jeden** call na całą talię; `stage=classify`, `processed` bez zmian aż wróci LLM; cancel check przed i po;
   - na starcie fazy: `stage=format|classify|layout|dedup`; przy `dedup` / `write` ustaw `total=len(items)` i `current_*`;
   - preserve: `stage=layout` bez licznika podczas 1–2 LLM, potem `stage=dedup` z `x/total` przy materializacji.
4. **Nowe**, wymagane przez usera — klasyfikacja końcowa każdej pozycji:

| Werdykt | Kiedy |
|---|---|
| `ready` | jest lemma (vocab) / karta display (preserve) **i** `find_card_anywhere` = None **i** lemma nie powtórzyła się wcześniej w tym jobie |
| `duplicate` | `find_card_anywhere` trafił **albo** to samo lemma już było w tym jobie (`reason_code=already_on_list` / `in_file_duplicate`) |
| `failed` | puste, `no_lemma`, `llm_invalid`, błąd formatu tej notatki; `reason_code` + `reason_detail` **obowiązkowe** |

Dziś intra-file duplikat jest dropowany. Teraz **musi** być widoczny jako duplicate.

5. Koniec: `status=review`, zliczenia, event `analyze_finished`.  
   Jeśli `ready_count==0` i są tylko duplicate/failed: **nadal `review`**, nie Error. User ma zobaczyć *dlaczego* nic nie wejdzie. OK/Import nieaktywny, Przerwij/Zamknij aktywne. To naprawia „wyszarzony OK bez wyjaśnienia” — wyjaśnienie jest listą.

LLM fail całego batcha: retry batch 1× (jak layout już robi), potem te pozycje `failed/llm_fail`, reszta jedzie dalej. Fail całego joba tylko gdy nie da się nawet posegmentować decku.

### 6.4. Faza commitu

Wejście: items `verdict=ready` (ew. podzbiór z body).

Dla każdego itemu, **do 3 prób**:

1. Utwórz kartę **tą samą ścieżką** co dziś `add_word_to_list` / `commit-display` (pending + `enrich_card` w tle). Ustaw `import_job_id`, `created_card_id`.
2. Sukces → `verdict` zostaje `ready`, `verdict_phase=commit`, `attempt=n`.
3. `find_card_anywhere` w międzyczasie (user dodał ręcznie) → zmień na `duplicate/already_on_list`, nie retry.
4. Inny wyjątek → `attempt++`, event `item_retry` z exception, backoff 0.5 / 1 / 2 s, max 3. Po 3 → `verdict=failed`, `reason_code` z typu wyjątku.
5. Cancel checkpoint **przed** kolejnym itemem. Przed każdą próbą: `stage=write`, `current_ordinal`, `current_label`, `current_attempt`, `processed` = ile już zamkniętych. Poll musi pokazać „la casa · próba 2/3”, nie tylko suchy licznik.

Na końcu bez cancel: `status=done`, `created_count`, event `commit_finished`.  
Karty widać od razu (pending), enrichment leci jak dziś — **to nie jest część joba importu**. „Koniec importu” ≠ „wszystko wzbogacone”.

Preserve: zamiast jednego wielkiego `commit-display` — ta sama pętla per karta, żeby cancel/rollback i retry były identyczne. Jedna wielka transakcja na całą talię uniemożliwia rollback przy cancel w środku.

### 6.5. Idempotencja commitu (wznowienie workera)

Przed utworzeniem karty: jeśli `created_card_id` już wskazuje żywą kartę → skip (sukces).  
Jeśli karta jest soft-deleted (poprzedni cancel) i job został *wznawiany jako commit a nie cancel* — nie powinno się zdarzyć; cancel jest terminalny.

---

## 7. Android — telefon jako terminal statusu

### 7.1. Co zostaje, co znika

Zostaje:

- dialog **startu** (wybór pliku/wklejki, trybu, listy) — to nie jest „akcja”, to konfiguracja,
- `ImportStatusPanel` w zakładce Dodaj,
- przycisk **Przerwij** + potwierdzenie (jedyne miejsce, które wolno przerwać),
- spinner przy zakładce Dodaj gdy job aktywny,
- guard `search()` gdy busy.

Znika / nie używamy do ścieżki usera:

- długie `ingestImport*` / pętla `addWordToList` w `ImportController`,
- DataStore jako źródło prawdy o fazie (może zostać tylko cache `job_id`),
- reguła `Processing → Error` przy starcie,
- `ImportReviewDialog` jako modal,
- `ImportResultDialog` / `ImportErrorDialog` nad całym `NavHost`.

### 7.2. Nowy `ImportController`

Nadal `@Singleton`, ale **cienki**:

```
startFromFile/Paste → POST /imports/jobs → zapamiętaj job_id → startPoll()
confirmCommit()     → POST /imports/jobs/{id}/commit
confirmCancel()     → POST /imports/jobs/{id}/cancel
onAppStart()        → GET /imports/jobs/active → jeśli jest, poll
```

Poll: `GET /imports/jobs/{id}/progress` co **1 s** na wierzchu, co **5 s** w tle (lifecycle).  
Request: krótki, timeout 8–12 s (`API_FAST_TIMEOUT_MS`). **Zerwany poll nic nie psuje** — następny cykl czyta ten sam wiersz z PG. Gdy `status` wejdzie w `review|done|failed|cancelled`, jeden `GET /imports/jobs/{id}?include_items=1` i stop pętli progress.

`busy` = status ∈ `{queued, analyzing, committing, cancelling}`.  
W `review` i `done` zakładka Dodaj nadal pokazuje **wynik w miejscu** (nie search/import), aż user zamknie podsumowanie (`dismiss` → DELETE-semantyka lokalna; job w PG zostaje dla admina). To realizuje „brak szukania / wklejki / pliku dopóki procedura nie skończona”.

`review` **jest** częścią procedury: search/paste/file wyłączone, widać trzy sekcje + `[Importuj N]` + `[Przerwij]`.

### 7.3. UI zakładki Dodaj (jedyny ekran akcji)

```
[busy: analyzing/committing/cancelling]
  spinner
  tytuł z stage (i18n): „Analizuję słowa” / „Zapisuję na listę” / …
  podtytuł: {source_name}
  gdy stage ma licznik:  „16 / 42”
  pasek postępu (processed/total; przy format/layout — indeterminate)
  aktualne słowo: {current_label}     (ellipsis gdy null)
  gdy committing i current_attempt>1: „próba 2/3”
  mini-podsumowanie rosnące: „OK 12 · duplikat 3 · błąd 1”
  [Przerwij]

[review]  — akordeon, 3 sticky nagłówki zawsze na wierzchu (także przy scrollu)
  ▸ Wejdzie (N)      — ready; domyślnie zwinięte
  ▸ Duplikaty (N)    — already_on_list / in_file_duplicate
  ▸ Błędy (N)  [⧉ kopiuj]  — failed + reason (i18n); ikona na nagłówku (widać też gdy zwinięte)
  reguła: tylko jedna sekcja rozwinięta; tap na inną zwija poprzednią
  [Przerwij]  [Importuj N]  — N = wszystkie ready; Importuj nieaktywne gdy N=0

### 7.3a. Kopiowanie błędnych lematów

Cel: user nie tylko *widzi* błędy — może je zabrać i sprawdzić (wklejka, arkusz, kolejne szukanie).

- Ikona kopiowania **tylko** przy sekcji Błędy (analiza: `verdict=failed`; po imporcie: te, które nie weszły po 3 retry). Nie przy „wejdzie” ani „duplikat”.
- Widoczna na sticky nagłówku, także gdy lista zwinięta. Ukryta / nieaktywna gdy `N=0`.
- Klik → schowek systemowy, jeden string, separator **`; `** (średnik + spacja):

  `lemat1; lemat2; lemat3`

- Źródło etykiety, w tej kolejności: `lemma` jeśli niepuste, inaczej `input_label` (to, co przyszło z pliku/wklejki). Kolejność = `ordinal` z joba (jak w pliku).
- Duplikaty w tej liście nie sklejamy — każdy failed item raz.
- Po skopiowaniu: krótki notice w zakładce Dodaj (`import_errors_copied`: „Skopiowano %d haseł”), nie modal.
- Ta sama ikona w panelu **done**, jeśli `failed_count > 0` (błędy zapisu po imporcie) — ten sam format, żeby dało się je odtworzyć.

Nie wysyłamy tego na BE (to czysty klient + dane już ściągnięte w `GET …/{id}`).

[done]
  Dodano X
  Duplikaty Y (nie ruszane)
  Błędy Z (po 3 retry)
  [OK]  — odblokowuje Dodaj
  opcjonalnie [Pokaż listę]

[failed / cancelled]
  komunikat
  [OK]
```

`ImportStatusPanel` mapuje `stage` → string; **nie** hardkoduje „Analizuję…” na cały `status=analyzing`. Ten sam panel obsługuje analizę i import — różni się tylko `phase`/`stage` z BE.

Żadnego modala recenzji. Żadnego modala wyniku nad Settings/Practice.  
Jeśli user jest na innej zakładce / w nauce: mały spinner przy „Dodaj”; po powrocie widzi aktualny stan (ten sam `progress`). Opcjonalnie (nie w MVP) lokalne powiadomienie „Analiza skończona” — **nie** zastępuje panelu.

Potwierdzenie Przerwij: krótki dialog tak (destrukcja), ale po potwierdzeniu znowu panel w Dodaj („Anulowanie…”) aż BE zwróci `cancelled`.

### 7.4. File picker a śmierć procesu

Dziś `pendingFileBytes` siedzi w `remember` — ginie.  
Naprawa przy okazji: po wyborze URI **od razu** czytać bytes i albo startować job (jeśli lista/tryb już wybrane), albo trzymać bytes w `ImportController` / pliku cache aplikacji (nie w Compose state). Jeśli proces umrze *przed* POST — nie ma joba, user wybiera plik jeszcze raz. Jeśli umrze *po* POST — job żyje na BE, po starcie `GET active` go wróci.

### 7.5. Czego świadomie nie robimy na Androidzie

- WorkManager jako executor analizy/importu — i tak musiałby trzymać HTTP; OEM i tak to zabije; nie działa po force-close tak, jak BE.
- Foreground service „Import trwa” — zbędny, gdy praca jest na serwerze; można dodać później jako powiadomienie statusu, nie jako silnik.
- Retry pętli `addWordToList` na telefonie — to leczy objaw, nie chorobę.

---

## 8. i18n (nowe / zmiana sensu)

Reuse: `import_status_analyzing`, `import_status_importing`, `import_progress_count`, `action_abort`, `import_abort_*`, `import_review_flagged`, `import_invalid_title`.

Dodać / zmienić:

| Klucz | Sens |
|---|---|
| `import_section_ready` | „Do zaimportowania (%d)” |
| `import_section_duplicates` | „Duplikaty (%d)” |
| `import_section_failed` | „Błędy (%d)” |
| `import_copy_errors` | contentDescription / tooltip: „Kopiuj błędne hasła” |
| `import_errors_copied` | „Skopiowano %d haseł” |
| `import_reason_already_on_list` | „Już jest na Twoich listach” |
| `import_reason_in_file_duplicate` | „Powtórzenie w tym pliku” |
| `import_reason_no_lemma` | „Nie udało się wyciągnąć słowa” |
| `import_reason_llm_invalid` | „Nie rozpoznano” |
| `import_reason_write_failed` | „Zapis nie powiódł się (po 3 próbach)” |
| `import_cancelling` | „Anulowanie i cofanie zmian…” |
| `import_cancelled` | „Przerwano. Nic nie zostało dodane.” |
| `import_still_running` | (opcjonalnie) „Trwa w tle” |
| `import_stage_queued` | „W kolejce…” |
| `import_stage_format` | „Rozpoznaję układ pliku…” |
| `import_stage_classify` | „Analizuję słowa” |
| `import_stage_layout` | „Układam fiszki…” |
| `import_stage_dedup` | „Sprawdzam duplikaty” |
| `import_stage_write` | „Zapisuję na listę” |
| `import_stage_rollback` | „Anulowanie i cofanie zmian…” |
| `import_progress_word` | „%1$d / %2$d” (reuse `import_progress_count` jeśli 1:1) |
| `import_progress_current` | aktualne słowo — sam `current_label` |
| `import_progress_attempt` | „próba %1$d/3” |
| `import_progress_tally` | „OK %1$d · duplikat %2$d · błąd %3$d” |

`import_interrupted` **wypada z happy-path**. Zostaje najwyżej jako fallback, gdy `GET active` nie działa (brak sieci przy starcie) — wtedy UI: „Analiza/import trwa na serwerze. Wróć, gdy będziesz online.” **Nie** kasujemy joba.

---

## 9. Pliki do zmiany

Backend (nowe):

- `app/models/__init__.py` — `ImportJob`, `ImportJobItem`, `ImportJobEvent` + `LearningCard.import_job_id`
- `app/services/import_jobs.py` — worker, cancel, rollback, resume
- `app/schemas/__init__.py` — request/response jobów
- `app/api/v1/imports.py` **albo** nowe endpointy w `learning.py` (lepiej osobny router, `learning.py` jest już ogromny)
- `app/db/migrations.py` — CREATE TABLE / kolumna
- `app/main.py` — resume + watchdog w lifespan

Backend (zmiana, reuse):

- `services/import_classify.py` — zwracać `reason`; nie dropować intra-file duplikatów; hook na `find_card_anywhere` (albo warstwa wyżej w workerze — **lepiej wyżej**, classify zostaje czysty)
- `services/import_ai.py` — nie podłączać; martwa ścieżka, nie mieszać z nowym jobem
- `services/import_display.py` — analogiczny werdykt per karta
- `api/v1/learning.py` — `add_word_to_list` przyjmuje opcjonalne `import_job_id` **albo** worker tworzy kartę sam (preferowane: logika utworzenia wyciągnięta do funkcji, wołana i z endpointu ręcznego, i z workera)

Android (zmiana):

- `data/imports/ImportController.kt` — poll + krótkie POST
- `data/imports/ImportModels.kt` — statusy 1:1 z BE
- `data/api/VocabularioApi.kt` + `LearningRepository.kt` — `getImportJobProgress(jobId)`, `getActiveImportJob`, `createImportJob`, `commitImportJob`, `cancelImportJob`
- `ui/home/ImportUi.kt` — panel review/done w tabie, bez modalu recenzji/wyniku
- `ui/home/HomeScreen.kt` / `VocabularioAppRoot.kt` — usunąć root-modale Done/Error
- `data/imports/ImportStatePersistence.kt` — tylko `job_id` (albo usunąć)

Testy:

- `backend/tests/test_import_jobs.py` — maszyna stanów, cancel+rollback, retry ×3, resume po „crashu”, duplikaty w analizie, 409 gdy job aktywny, **`GET …/progress`**: w `classify` zmienia się `stage` (nie udawany x/total), w `write` rośnie `processed` po karcie
- `android/.../ImportJobStateTest.kt` — busy/blokada dla nowych statusów
- e2e: start paste → zabij aplikację (albo po prostu nie czekaj na HTTP) → otwórz → Dodaj nadal pokazuje analizę/review

---

## 10. Etapy wdrożenia

Kolejność celowo taka, żeby najpierw zniknął ból z telefonu, potem diagnostyka i UI recenzji.

### Etap 1 — szkielet joba analizy (naprawa „ekran zgasł = po analizie”)

- Tabele + migracje.
- `POST /imports/jobs` + `GET active` + `GET {id}` + **`GET {id}/progress`** + worker analizy + resume w lifespan.
- Klasyfikacja: jeden call na talię; zapis `stage`/`processed`/`current_*` przy zmianie etapu i w `dedup`/`write`.
- Android: start + poll `progress` 1 s + panel z etapem, `x/total` i aktualnym słowem; **nie** wołać już `ingest*`.
- Po analizie tymczasowo: od razu `review` w tabie (lista ready; duplikaty/failed choćby surowe).
- DoD: wygaszenie / Home / inna apka / force-stop **nie** zmieniają wyniku; po otwarciu widać ten sam job **i aktualny licznik**, nie spinner bez liczb.

### Etap 2 — commit na BE + retry ×3 + Przerwij = rollback

- `POST commit` / `POST cancel`.
- Worker zapisu, `import_job_id` na kartach, rollback.
- Android: `[Importuj]` i `[Przerwij]` wołają BE; zero pętli `addWordToList`.
- DoD: force-stop w połowie importu → po otwarciu widać „Zapisuję 10/30 · la casa”; licznik rośnie dalej; Przerwij → 0 nowych kart u usera.

### Etap 3 — raport analizy (akordeon) + i18n

- Werdykty `ready|duplicate|failed` z `reason_code`.
- Trzy sticky listy-akordeon w zakładce Dodaj (§0.1 pkt 5, §7.3) + kopiowanie błędów (§7.3a).
- `invalid_reason` nie ginie w `list[str]`.

### Etap 4 — diagnostyka admina

- `import_job_events` wypełniane w każdym kroku §4.3.
- `GET` admin + krótka notatka w README jak czytać tabele.
- DoD: da się z SQL odtworzyć każdy fail z ostatnich importów.

### Etap 5 — sprzątanie

- Aplikacja nie używa starych ingest/commit-display (zostawić endpointy na skrypty albo oznaczyć deprecated).
- Usunąć DataStore snapshot całego `ImportJobState`, root-modale, `import_interrupted` z happy-path.
- Testy e2e F-04 (cancel paste) przepisać na nowy kontrakt.

Etapy 1–2 są **minimalnym** zestawem, bez którego zgłoszenia z telefonu nie znikną. 3–4 to wymagania „widzę duplikaty / admin wie dlaczego”.

---

## 11. Testy akceptacyjne (scenariusze z zgłoszenia)

Te scenariusze muszą przejść, inaczej nie zamykamy tematu.

| # | Scenariusz | Oczekiwanie |
|---|---|---|
| A | Start analizy → wygaszenie ekranu 5 min → odblokowanie | W Dodaj: analiza trwa albo review; **nie** „Import przerwany”; jeśli trwa — widać etap i `x/total` |
| B | Start analizy → inna aplikacja → powrót | j.w. |
| C | Start analizy → Recents → swipe away (force-close) → otwarcie apki | GET active wraca ten sam job; brak utraty śladu |
| D | Start importu 30 słów → force-close przy ~10 | Po otwarciu „Zapisuję 10/30” + aktualne słowo, potem 30/30; nie „20 błędów” |
| D2 | Analiza dużej wklejki, obserwacja panelu | `format` / `classify` = etap + spinner (bez udawanego x/total) → `dedup` z licznikiem → akordeon 3 list |
| E | Przerwij w analizie | Brak kart; status cancelled; Dodaj odblokowane |
| F | Przerwij w imporcie po 7 kartach | Te 7 znikają (soft-delete); user nie widzi ich na liście |
| G | Analiza: 20 ready, 5 already_on_list, 3 no_lemma | Akordeon 3 sticky nagłówków; jedna sekcja naraz; Importuj 20; ikona kopiuj na Błędy → `a; b; c` |
| H | Commit: sztuczny 500 na 1. i 2. próbie 1 itemu | 3. próba zapisuje; event `item_retry` ×2; nie ma `failed` |
| I | Commit: 3× fail | item `failed/write_failed`; reszta leci; job `done` z `failed_count=1` |
| J | Drugi import gdy pierwszy analyzing | 409 / UI nie pozwala (przyciski ukryte) |
| K | Admin: job z H/I | W `import_job_events` widać exception_type i attempt |

Nie testujemy „czy OkHttp przeżyje 200 s” — to celowo przestaje być ścieżką.

---

## 12. Ryzyka i świadome decyzje

1. **Worker w procesie uvicorn.** Restart deploju przerywa task, ale resume z PG to podnosi. Przy wielu replikach trzeba będzie `FOR UPDATE SKIP LOCKED`. Na obecną skalę (1 API) — OK.
2. **Enrichment nadal jest BackgroundTasks.** Cancel rollback usuwa kartę; `enrich_card` wychodzi. To już działa. Nie mieszamy enrichmentu z jobem importu.
3. **Brak limitu kart** (§0.1). Ryzyko: bardzo duża talia = długi jeden call LLM / dużo zapisów. Mitigacja: cancel, eventy w PG, limity pliku/wklejki. Nie wprowadzać z powrotem „max 50” bez decyzji usera.
4. **Jedno zadanie na profil.** Świadomie. Drugi import: czeka albo Przerwij.
5. **Review = akordeon 3 list**, bez odhaczania. Przy Błędy: kopiuj `lemat1; lemat2; lemat3` (§7.3a). `item_ids` w `POST commit` zostaje w API na później, UI MVP go nie używa.
6. **Preserve** idzie tą samą maszyną. Nie zostawiamy `commit-display` jako jedynego strzału z telefonu — inaczej ten tryb znowu padnie przy wygaszeniu.
7. **Brak sieci przy starcie apki.** Job leci na BE; UI pokazuje „trwa na serwerze, wróć online”. Nie wolno tego zamieniać na Error + kasowanie.
8. **Stary spec v1 §2.4 i §A5 (częściowy commit zostaje)** — **unieważnione** tym dokumentem. Nie implementować ich „dla zgodności”.

---

## 13. Definicja ukończenia

- Ani analiza, ani import nie są przywiązane do żywego Activity/ViewModel/OkHttp call.
- Jedyny sposób przerwania = Przerwij → zero kart z tego joba u usera.
- Po force-close i ponownym otwarciu zakładka Dodaj pokazuje prawdę z PG: trwa / review / done.
- Po analizie widać duplikaty i to, co nie weszło, z powodem.
- Import ponawia zapis pozycji do 3 razy; po 3. fail jest w item + events, nie „reszta to błędy bo telefon zasnął”.
- Admin z trzech tabel PG odtwarza każdy przebieg i każdy fail.

Dopóki którykolwiek punkt z §11 A–K pada, temat nie jest zamknięty — niezależnie od tego, czy singleton na Androidzie „wygląda stabilniej” przy przełączaniu zakładek.
