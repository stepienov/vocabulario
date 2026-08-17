# Plan naprawczy: ustawienia, zegar, sync, import

Dla agenta: idź **punkt po punkcie** (P0 → P1 → P2). Po każdym punkcie testy jednostkowe tam, gdzie są. Nie rób nowego APK, dopóki user nie poprosi.

Źródło faktów: produkcyjny PG 16–17.08.2026 + kod w workspace. Audyt UI: canvas `sync-settings-import-audit.canvas.tsx`.

---

## P0-A — Koło godziny powiadomienia nie reaguje na palec

### Bug
Ustawienia → Powiadomienia → kolo godziny/minuty. Palec nic nie robi, albo kolo skacze z powrotem na starą godzinę.

### Co było nie tak (dwie warstwy)

**1. Nested scroll zjada gest zanim kolo go zobaczy.**

`WheelTimePicker` siedzi w `Column(Modifier.verticalScroll)`. Kola to `LazyColumn`. Żeby rodzic nie kradł gestu, dodano:

```kotlin
// WheelTimePicker.kt — ŹLE
override fun onPreScroll(available, source) = Offset(0f, available.y)
```

`onPreScroll` idzie **od dziecka w górę, zanim LazyColumn się przewinie**. Box zjada cały delta Y → LazyColumn dostaje 0 → kolo jest martwe.

W Compose kolejność jest:

1. `dispatchPreScroll` do przodków
2. dziecko (`LazyColumn`) przewija resztę
3. `dispatchPostScroll` — resztki dla rodzica

Żeby rodzic (`verticalScroll`) nie brał gestu, a kolo tak: **`onPreScroll = Zero`**, **`onPostScroll` zjada leftover Y**.

**2. Pull / Room resetuje godzinę w trakcie kręcenia.**

`setReminderTime` pisze UI od razu, a PATCH `reminder_hour` dopiero po 450 ms. `SettingsViewModel.init` zbiera `observeSettings()` z Room. Każdy `applyPull → saveSettings(stare z PG)` wkleja stare `reminder_hour`. `WheelColumn` ma `LaunchedEffect(value) { scrollToItem(...) }` — kolo fizycznie wraca na 19:00. Objaw: „nie reaguje”, bo każdy gest jest cofany.

Minuty są tylko lokalnie (`NotificationScheduler` SharedPreferences), na PG nie ma `reminder_minute`.

### Objawy
- Palec na kole: brak ruchu.
- Albo kręci się i wraca.
- Po wyjściu z ustawień godzina znowu 19.

### Logi / jak złapać
- Kod: `android/.../ui/components/WheelTimePicker.kt` (`nestedScroll`), `SettingsViewModel.setReminderTime`, `SettingsViewModel.init` `observeSettings`.
- Rodzic: `SettingsScreen.kt` `Modifier.verticalScroll`.
- PG: `user_settings.reminder_hour` (nowy4 i bartolome = 19).
- `app_logs`: `PUT /api/v1/me/settings` 200 (nowy4, 17.08 04:28 PL, 5 requestów z rzędu) — PATCH czasem dochodzi, UI i tak się cofa.

### Implementacja
1. `NestedScrollConnection`: `onPreScroll` → `Offset.Zero`; `onPostScroll` → `Offset(0f, available.y)`.
2. Nie kopiować `reminderHour` / `reminderMinute` z `observeSettings`, gdy `reminderSaveJob` jest aktywny.
3. Zależne od P0-B (pull nie nadpisuje ustawień).

---

## P0-B — Ustawienia wracają po wyjściu (tryb, kierunek, układ karty, powiadomienia)

### Bug
Zaznaczasz tryb nauki / kierunek / bloki na karcie / powiadomienia. Wychodzisz, wracasz — znowu stare.

### Co było nie tak
Local-first jest tylko w połowie:

1. `LearningRepository.updateSettings` → Room + outbox `settings_update` + drain.
2. `syncNow` → `pushOutbox()` **potem** `GET /sync/pull` → `OfflineStore.applyPull` **zawsze** `saveSettings(pull.settings)`.
3. `SettingsViewModel` nasłuchuje Room i wkleja to w UI.

Pull jest snapshotem z chwili startu requestu. Wyścig:

- drain PATCH nowy kierunek na PG
- pull, który wyleciał **przed** PATCH, wraca ze starym
- `applyPull` nadpisuje Room
- UI wraca

Albo: PATCH 401 (token), `markOpFailed`, po 5 próbach status `parked` (`MAX_OP_ATTEMPTS = 5`). Pull wkleja PG. Parked nigdy więcej nie wychodzi.

Backend: `GET /sync/pull` zawsze dokleja pełne `UserSettings`. `UserSettings` **nie ma** `updated_at` — nie da się last-write-wins po czasie.

Ustawienia są per user, nie per profil. `syncNow(fullReplace = true)` przy zmianie profilu (`ProfileViewModel`) też by je nadpisał — nie wolno.

### Objawy
- Zero kontroli nad trybem / kierunkiem / checkboxami karty.
- Czasem widać zaznaczenie, po nawigacji znika.
- Na PG bywa default (nowy4: flashcard, l2→l1) mimo tapania.

### Logi / jak złapać
- `OfflineStore.applyPullLocked` pierwsza linia: `saveSettings(pull.settings)`.
- `LearningRepository.syncNow` kolejność: drain, potem pull.
- `app_logs` 16–17.08: 25× `GET /sync/pull` 401, 19× `GET /me/settings` 401 (workery, `user_id` null). PUT settings 200 istnieje — serwer umie zapisać.
- Outbox: `outbox_ops.status = parked` po 5 błędach.

### Implementacja
1. `applyPull`: `saveSettings(pull.settings)` **tylko gdy lokalne ustawienia są puste** (pierwszy login / reinstall). Inkrementalny pull i `fullReplace` **nie** ruszają ustawień, jeśli Room już je ma.
2. Drain: 401/408/5xx = `break` **bez** `markOpFailed` (jak `IOException`).
3. Na starcie drain: odparkować opy, których `lastError` zawiera `401`.
4. `observeSettings` nie jest problemem, jeśli Room nie dostaje starych settings z pulla.

Architektura (zgodnie z userem): telefon = źródło prawdy dla ustawień; PG = kopia z outboxu; PG→telefon tylko gdy Room nie ma wiersza.

---

## P0-C — Import urywa się i gubi dziesiątki słów

### Bug
Wklejka 333 słów, analiza 325+8. Overlay 75/325, lista „Uczę się” 19. Po restarcie ~261. Brakuje ~65.

### Co było nie tak
Job produkcyjny `fddd7a0c-7933-4065-a55d-ae6b43deb754` (nowy4, paste, 16.08 23:09–23:30 PL):

| Pole | Wartość |
|---|---|
| total / ready / failed_analyze | 325 / 325 / 8 |
| processed / created | 260 / 260 |
| status | `failed` / `worker_crash` |
| leftover ready bez karty | **65** (ordinal 267–332, od `objetivo`) |

Crash w `app_logs.event = import_worker_crash`:

- `UniqueViolationError` na `uq_learning_cards_live_lemma_pos`
- klucz `(objetivo, adj)` przy **UPDATE** `learning_cards` (hydrate z cache), nie INSERT
- potem `PendingRollbackError` — sesja zatruta

Pętla `_run_commit` łapie `Exception`, ustawia `item.last_error`, woła **`await db.commit()` bez `rollback()`**. Commit na zatrutej sesji → `PendingRollbackError` → `_run_guarded` oznacza **cały job** `failed`. Watchdog nie wznawia `failed`. 65 ready nigdy nie zapisane.

Ten sam tekst na bartolome (`cac74b44`): crash na pierwszej karcie (`despertarse`, verb), created=0.

Karty systemowej listy mają `deck_id IS NULL` (`_create_card_for_item`: `deck_id=None if wl.is_system`). 260 kart z joba **żyje** na PG. 262 live na profilu nowy4 (260 + 2 wcześniejsze). „19” to stary Room, nie PG.

Hydrate: import tworzy `objetivo` z `pos=NULL`, cache ma `objetivo/adj`, UPDATE ustawia adj, unique zderza się z już istniejącym `objetivo/adj`.

### Objawy
- Overlay jedzie, lista stoi.
- Po restarcie część słów jest, reszty nie ma i nie wiadomo których.
- Job w UI może wyglądać jak „skończony”, na PG `failed`.

### Logi / jak złapać
```sql
SELECT id, status, processed, total, created_count, error_code
FROM import_jobs ORDER BY created_at DESC;

SELECT lemma, ordinal FROM import_job_items
WHERE job_id = :id AND verdict = 'ready' AND created_card_id IS NULL
ORDER BY ordinal;

SELECT event, error_type, error_message FROM app_logs
WHERE event = 'import_worker_crash' ORDER BY created_at DESC;
```

Constraint: `uq_learning_cards_live_lemma_pos`.
Kod: `backend/app/services/import_jobs.py` `_run_commit` / `_run_guarded`; `card_jobs.py` `hydrate_from_lexical_cache` / `_apply_entry_to_card`.

65 brakujących (ordinal 267–332): objetivo, optimista, perjudicial, permanente, preocupante, probable, profundo, razonable, relevante, responsable, satisfecho, significativo, temporal, tradicional, urgente, variado, vulnerable, competitivo, controvertido, alcanzar, analizar, apoyar, asumir, aumentar, comprobar, contribuir, convencer, cuestionar, destacar, desarrollar, disminuir, enfrentarse, establecer, evaluar, fomentar, gestionar, influir, lograr, mantener, mejorar, prevenir, proponer, reconocer, resolver, superar, el artículo, el comienzo, el negocio, la alfombra, la oportunidad, la elección, el sueño, el empleado, la energía, la fábrica, el vuelo, la máquina, el pasajero, el proyecto, la razón, el resultado, la carretera, el servicio, la habilidad, la asignatura.

### Implementacja
1. W `_run_commit`: na `IntegrityError` / `PendingRollbackError` → **`await db.rollback()`**, odśwież item, oznacz `duplicate` (jeśli `find_card_anywhere`) albo `failed` **tej pozycji**, jedź dalej. Nigdy `commit` na zatrutej sesji.
2. `hydrate_from_lexical_cache`: `begin_nested` + `flush`; przy unique → savepoint rollback, return False (karta zostaje pending, enrich później).
3. Nie oznaczać całego joba failed przez jedną kolizję unique.

---

## P1-A — Analiza oznacza prawdziwe zwroty jako błędy (`tener prisa`)

### Bug
8 „błędów” przy 333 słowach. Lookup „tener prisa” znajduje czasownik i da się dodać.

### Co było nie tak
To **nie** jest halucynacja LLM. Job items 1:1:

| Hasło | reason_code | reason_detail |
|---|---|---|
| pedir perdón | no_lemma | phrase without base_lemma |
| tener prisa | no_lemma | phrase without base_lemma |
| tener sueño | no_lemma | phrase without base_lemma |
| quedarse dormido | no_lemma | phrase without base_lemma |
| (com)portarse | llm_invalid | not recognized |
| el casco antiguo | no_lemma | phrase without base_lemma |
| pedir prestado | no_lemma | phrase without base_lemma |
| el medio ambiente | no_lemma | phrase without base_lemma |

Prompt klasyfikacji **sam** podaje `pedir perdón` jako przykład `phrase`. Potem `_vocabulario_lemma()` zwraca `None` gdy `entry_kind != lemma` i brak `base_lemma` (zgaduje lemma tylko dla article+noun **2** tokeny — `el casco antiguo` ma 3). `_apply_vocab_item` ustawia `no_lemma`.

Lookup idzie inną ścieżką (cache leksykalny całego hasła).

`(com)portarse`: `_token_looks_like_word` liczy `(` i `)` jako junk; `junk >= 2` → odrzut, nawet gdy LLM da `valid=false` fallback nie przejdzie.

### Objawy
- Analiza: 8 błędów, w tym oczywiste zwroty.
- Dodaj → szukaj: to samo hasło działa.

### Logi / jak złapać
`import_job_items.reason_detail = 'phrase without base_lemma'`.
Kod: `import_classify.py` `_vocabulario_lemma`; `import_jobs.py` `_apply_vocab_item` ok. ~913; prompt `IMPORT_CLASSIFY` w `ai/prompts/v1.py`.
Test do zmiany: `test_apply_vocab_item_no_lemma_phrase`, `test_vocabulario_lemma_uses_base`.

### Implementacja
1. `_vocabulario_lemma`: `phrase` / `construction` / `other` → **headword jest lematem karty** (jak lookup). `sentence` bez lematu → nadal fail. `base_lemma` tylko gdy head nie przechodzi filtra śmieci.
2. `_token_looks_like_word`: dopuść `()` w tokenie (prefixy typu `(com)portarse`).
3. Testy: `tener prisa` → pending; `el medio ambiente` → pending; śmieci (`ppppppppp`, `123`) nadal fail.

---

## P1-B — Czasy (wszystkie / wybrane) się nie trzymają

### Bug
Edycja czasów, wyjście, powrót — znowu stare (np. tylko presente, albo znowu wszystkie).

### Co było nie tak
Czasy są na **profilu**, nie w `UserSettings`. `persistTenses` → `updateProfile` = sam `PUT /profiles/{id}`, bez outboxu, bez optimistic UI. `SettingsViewModel.load()` zawsze woła `refreshProfilesFromNetwork()` → `applyRemoteProfiles` nadpisuje cache, w tym `selected_tenses`.

Jeśli PUT nie zdążył / 401 / zły profile id, GET wkleja stare.

`persistTenses` aktualizuje `_state.selectedTenses` dopiero w `onSuccess` — radio może nie drgnąć, a po `load()` i tak wraca serwer.

### Objawy
- „Wszystkie” / „Wybrane” / modal czasów: po powrocie to samo.
- PG bartolome: `selected_tenses = ["presente"]` — serwer czasem ma custom, telefon i tak pokazuje to, co ostatni GET wcisnął w Room.

### Logi / jak złapać
- `language_profiles.selected_tenses`
- `PUT /api/v1/profiles/{id}` vs `GET /api/v1/profiles` w `app_logs`
- `SettingsViewModel.persistTenses` / `load` / `LearningRepository.applyRemoteProfiles`

### Implementacja
1. `updateProfile`: najpierw `cacheProfile(optimistic)`, potem PUT; sukces → cache z serwera; błąd → zostaw optimistic (nie cofaj, chyba że 404 ghost — reconcile).
2. `persistTenses`: od razu `_state.selectedTenses` (optimistic).
3. `applyRemoteProfiles`: dla **tego samego** active profile id nie nadpisuj `selected_tenses` / `cefr_level` / `tense_label_lang` z GET — lokal jest nowszy. Inny profil (zmiana pary języków) bierze remote.

---

## P1-C — Licznik listy 19 vs overlay 75 vs 261 po restarcie

### Bug
W trakcie importu lista „Uczę się” nie rośnie. Overlay pokazuje postęp. Po zabiciu apki nagle ~261.

### Co było nie tak
- Import pisze tylko PG. Room dostaje karty przy `refreshLocalAfterImport` albo `syncNow` pull.
- `refreshLocalAfterImport` jest wołane przy statusie **Done**. Job padł jako **failed** → brak refresh w trakcie i na crashu.
- Home `loadLists` przy zmianie statusu na Done, nie przy `createdCount`.
- `listWordLists` liczy z Room (`systemListCards` = `deckId IS NULL`). Dopóki nie ma pulla, licznik = ostatni pull (19).
- System list na serwerze = `deck_id NULL`, więc po pullu nagle wszystkie 260 wjeżdżają naraz.

### Objawy
- Nakładanie liczb.
- Wrażenie, że import „nie dodaje”, a potem lawina.

### Logi / jak złapać
`ImportController.startPoll` — refresh tylko `becameDone`.
`HomeViewModel` collect import status.
PG: `created_count` vs `COUNT(*) FROM learning_cards WHERE deck_id IS NULL`.

### Implementacja
1. Poll: przy wzroście `createdCount` (np. co 20) `syncNow()`; przy `Done` **i** `Failed` z `createdCount > 0` → `refreshLocalAfterImport`.
2. Home: `loadLists` też gdy rośnie `createdCount`, nie tylko Done.

---

## P2 — 401 na workerach parkuje outbox ustawień

### Bug
Nocne GET-y bez usera; po 5 padach `settings_update` = `parked`; zmiana nigdy nie wylatuje.

### Co było nie tak
`drainOutboxOps`: każdy `Exception` (w tym `HttpException 401`) → `markOpFailed`. Authenticator czasem czyści pamięć tokena; workery dalej biją w API. GET `/sync/pull` i `/me/settings` 401 co 30–40 min.

### Objawy
Ustawienia „zapisane” lokalnie, po czasie wracają; outbox stoi.

### Logi / jak złapać
```sql
SELECT http_status, http_path, COUNT(*) FROM app_logs
WHERE created_at > now() - interval '48 hours'
  AND http_status >= 400 GROUP BY 1,2;
```
Android: `OutboxOpDao`, `markOpFailed`, `TokenAuthenticator`.

### Implementacja
Zawarte w P0-B pkt 2–3: nie parkować 401; odparkować stare 401.

---

## Kolejność wdrożenia

1. P0-A zegar (gest + nie resetować godziny w observe)
2. P0-B pull/outbox ustawień
3. P0-C import unique + rollback
4. P1-A phrase = lemma
5. P1-B czasy profilu
6. P1-C licznik / sync w trakcie importu
7. Testy BE (`test_import_jobs.py`) + drobne testy Androida jeśli są haki bez Room

Nie wznawiać starych jobów `failed` z produkcji — user może ponownie wkleić 65 braków. Nie składać APK.
