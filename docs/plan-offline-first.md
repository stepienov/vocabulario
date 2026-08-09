# Plan implementacji: architektura offline‑first

> Dokument samowystarczalny dla agenta implementującego. Nie wymaga czytania rozmowy,
> z której powstał. Opisuje stan obecny (zweryfikowany w kodzie), stan docelowy,
> kolejność prac, nowe kontrakty, migracje, kryteria akceptacji i scenariusze regresji.
>
> Zakres: Android (Kotlin + Compose + Room) + backend (FastAPI + PostgreSQL).
> Data analizy kodu: 2026‑08‑07. Room `AppDatabase.version = 6`. Brak Alembica
> (migracje = idempotentny raw SQL w `backend/app/db/migrations.py`).

---

## 0. Cel i trzy zasady

Aplikacja ma działać tak, że **telefon użytkownika jest źródłem prawdy dla UX**, a backend
+ PostgreSQL są magazynem trwałym i mechanizmem spójności między urządzeniami. Sieć jest
potrzebna **wyłącznie** do pozyskania *nowej treści* (lookup, import, enrichment AI).

**Z1 — User ma wszystko u siebie.** UI i logika biznesowa czytają i piszą do lokalnej kopii
(Room). Room nie jest „cache do wyświetlenia”, tylko źródłem prawdy. Sync utrzymuje
spójność, nie jest warunkiem działania.

**Z2 — API tylko dla nowej treści.** Dodanie słowa / import / wklejka → wymaga sieci
(lookup PG → ewentualnie AI). Operacje na *już posiadanych* danych (karty, listy,
ustawienia, nauka) → lokalnie, sync w tle.

**Z3 — Offline == online (poza pozyskiwaniem treści).** Te same akcje działają offline i
online: zmiana ustawień, tworzenie/rename/usuwanie list, usuwanie słów, przenoszenie słów
między listami, nauka (practice, oceny SRS, undo), przeglądanie list i kart. Jedyna
różnica: offline **nie da się** zrobić lookupu/importu/enrichmentu nowych słów.

Model danych: **karta jest osobna per para językowa** (`profile_id`). Raz utworzona karta
żyje w PostgreSQL i jest replikowana na telefon. Lookup nowego słowa: najpierw sprawdzamy,
czy karta/wpis już istnieje po stronie serwera (PG), dopiero potem generujemy przez AI.

---

## 1. TL;DR — co trzeba zrobić

1. **Naprawić poison‑pill w `POST /sync/push`** (źródło zgłaszanego 404). Push nigdy nie
   może przerwać całej paczki przez jeden nierozwiązywalny element — przejść na
   per‑item wynik (`applied|skipped|failed`), a „card not found” traktować jako `skip`
   (idempotentnie), nie `raise 404`. **To jest hotfix o najwyższym priorytecie.**
2. **Ujednolicić outbox** w jeden uporządkowany log operacji (`outbox_ops`) obejmujący
   wszystkie mutacje danych użytkownika: `review`, `undo`, `move`, `list_create`,
   `list_rename`, `list_delete`, `card_delete`, `settings_update` (docelowo też
   `self_edit`). Każda operacja ma `client_op_id` (idempotencja) i porządek FIFO.
3. **Przełączyć wszystkie mutacje „posiadanych” danych na wzorzec local‑first**: zapis do
   Room + wpis do outbox → UI reaguje natychmiast → sync w tle. (Dziś tak działa tylko
   `moveCard` i oceny SRS.)
4. **Wprowadzić lokalne ID + remap** dla list tworzonych offline (`local:<uuid>` → server
   UUID) i wszędzie, gdzie operacje odwołują się do jeszcze‑niezsynchronizowanej listy.
5. **Włączyć inkrementalny pull (`since`) + tombstones** (`deleted_card_ids`,
   `deleted_list_ids`) — soft‑delete po stronie PG. `fullReplace` zostaje tylko dla
   pierwszego sync / zmiany pary / resetu.
6. **Uczynić UI agnostycznym względem sieci** dla operacji z Z3 — usunąć rozgałęzienia
   `isOnline` poza lookup/import/enrichment/korekty AI.
7. **Zrobić Room reaktywnym źródłem prawdy** (DAO zwracają `Flow`), a repo/VM czytają z
   Room, nie z ad‑hoc wywołań API na każdym ekranie.

---

## 2. Stan obecny (zweryfikowany w kodzie)

### 2.1 Android — warstwa danych

**Room (`data/local/db/`)**
- `AppDatabase` v6, `exportSchema=false`, budowane w `OfflineStore` z
  `fallbackToDestructiveMigration()` — każda zmiana schematu **kasuje** lokalną bazę
  (w tym niewy­słany outbox).
- Encje (`Entities.kt`): `cached_cards` (`CachedCardEntity`), `cached_lists`
  (`CachedListEntity`), `pending_reviews`, `pending_moves`, `pending_lookups`,
  `pending_undos`, `local_settings`, `sync_meta`, `cached_profile`.
- DAO (`Daos.kt`) — wszystkie metody są `suspend` i zwracają snapshoty (`List<…>`),
  **brak `Flow`** → UI nie jest reaktywne wobec Room; ekrany odświeżają się przez
  ręczne `refreshAll()`/polling w ViewModelach.

**`OfflineStore.kt`** — fasada nad Room. Zawiera całą logikę pending inbox (dedup,
consolidacja, liczniki), mapowanie `Sync*Item ↔ Entity ↔ *Response`, FSRS lokalnie
(`LocalFsrs`), `applyPull(profileId, pull, fullReplace)`.
- `applyPull` przy `fullReplace=true` robi `cardDao.clearProfile` + `listDao.clearProfile`,
  potem wstawia dane z serwera. `deleted_card_ids` obsłużone (`cardDao.deleteIds`), ale
  serwer zawsze zwraca `[]` (patrz 2.3).

**`LearningRepository.kt`** — punkt centralny. Kluczowe fakty:
- `syncNow(fullReplace=true)` (linia ~652): gate `if (!isOnline) return`; kolejno
  `pushOutbox()` → `flushPendingLookups()` → `api.syncPull(profileId, since = null)` →
  `offlineStore.applyPull(..., fullReplace)`. **`since` jest zawsze `null`**, a wywołania
  najczęściej idą z `fullReplace=true`. Efekt: każdy sync to pełne pobranie + pełna
  podmiana Room.
- `pushOutbox()` (linia ~689): buduje `SyncPushRequest` z `pending_moves` + `pending_reviews`,
  woła `api.syncPush(body)`; przy powodzeniu usuwa outbox i aplikuje `result.srs`. Jeśli
  `api.syncPush` rzuci (np. 404) → wyjątek leci w górę, `syncNow` łapie go w `runCatching`,
  **pull się nie wykonuje**, a outbox **nie jest czyszczony** → przy każdym syncu ta sama
  paczka leci znów i znów dostaje 404 (zakleszczenie).
- **Mutacje z outboxem (local‑first):** tylko `moveCard` (lokalny ruch + `pending_move` +
  próba API) oraz oceny (`submitReview` → `applyReviewLocally` + `pending_review`), undo
  (`undoReview` → lokalnie + `pending_undo` przy porażce), offline lookup
  (`enqueueOfflineLookup` → `pending_lookup`).
- **Mutacje online‑only (łamią Z3):**
  - `createWordList` → `api.createWordList` (bez outboxu; offline = wyjątek).
  - `renameWordList` → `api.renameWordList` (bez outboxu).
  - `deleteWordList` → `api.deleteWordList` (bez outboxu; jedynie lokalne inbox‑pending ma
    ścieżkę `clearPendingLookupsForList`).
  - `deleteCard` → `api.deleteCard` (bez outboxu; offline = wyjątek).
  - `updateSettings` → `api.updateSettings` (bez outboxu; offline = wyjątek).
  - `selfEditCard`, `restoreCard`, `createProfile`, `updateProfile`, `activateProfile`,
    korekty, historia → online‑only (część słusznie: AI/korekty; profil — do rozważenia).
- **Odczyty hybrydowe ad‑hoc:** `listCards`, `listWordLists`, `listWords`, `getSettings`,
  `listProfiles`, `getActiveProfile` — każde samo decyduje `if (isOnline) API+cache else
  Room`. Źródło prawdy jest rozmyte między API a Room; `applyPull` to osobna ścieżka.
- `createCard` po sukcesie woła `syncNow(fullReplace = true)` (kosztowny pełny pull po
  dodaniu jednej karty).

**`NetworkMonitor.kt`** — `isCurrentlyOnline()` wymaga `NET_CAPABILITY_INTERNET` +
`NET_CAPABILITY_VALIDATED`; `isOnline: StateFlow<Boolean>`.

**`SyncWorker.kt` / `SyncScheduler.kt`** — WorkManager. Periodic 15 min (KEEP) + one‑time
`requestNow()` (REPLACE) z constraintem `CONNECTED`. `SyncWorker` woła
`syncNow(fullReplace = true)`, retry do 4 prób.

**ViewModele** — rozgałęzienia `isOnline` (do przejrzenia/uproszczenia):
- `HomeViewModel`: pole `isOnline`, reakcja na powrót online (`syncNow`), blokady importu
  offline, `enqueueOfflineLookup`, korekty/historia online‑only.
- `PracticeViewModel`: `isOnline` w stanie, `getDistractors` ma fallback lokalny,
  korekty/related online‑only.
- `SettingsViewModel.save(...)`: optimistic UI, ale `repository.updateSettings` jest
  online‑only → **offline zmiana ustawień cofa się** (łamie Z3).
- `HomeScreen`: warunki UI na `state.isOnline` (banner, ukrycie importu, hint search, mic).

### 2.2 Android — kontrakty API (`data/api/VocabularioApi.kt`, `Models.kt`)
- `syncPull(profileId, since=null)`, `syncPush(SyncPushRequest{reviews, moves})`.
- `SyncPushRequest` niesie **tylko** `reviews` + `moves`. Brak kanału na
  create/delete/rename/settings.
- `SrsQueueResponse` mapuje `@SerialName("new") newCards` (zgodne z backendem `new`).

### 2.3 Backend

**`api/v1/sync.py`**
- `GET /sync/pull`: obsługuje `since` (filtr `LearningCard.updated_at >= since`), zwraca
  `settings`, `cards` (+ `srs`), `lists`, **`deleted_card_ids=[]` na sztywno** (linia 120).
  → inkrementalny pull nie potrafi propagować usunięć.
- `POST /sync/push`:
  - `_apply_moves`: idempotencja przez `AppliedSyncMove.client_id`, LWW przez `moved_at`.
    **`if card is None: raise HTTPException(404)`** i **`if target is None: raise
    HTTPException(404)`** → jeden zły ruch wywala całą paczkę.
  - reviews: idempotencja przez `ReviewLog.client_id`. Zapytanie to **INNER JOIN**
    `LearningCard ⨝ SrsState (scope='main')`; **`if row is None: raise
    HTTPException(404)`**. `row` jest `None` gdy karta nie istnieje **albo** nie ma
    `SrsState` scope=main. Cała funkcja to jedna transakcja — `raise` = rollback całości,
    nic się nie commit‑uje, outbox po stronie klienta nie jest czyszczony.

  **To jest zgłaszany bug „POST /api/v1/sync/push → 404 (karta nie znaleziona)”.**
  Realne wyzwalacze: karta usunięta na innym urządzeniu / przez kasowanie listy (hard
  delete, cascade) przy nadal istniejącej karcie w Room; ocena karty bez `SrsState`
  scope=main; ruch na listę usuniętą serwerowo.

**`api/v1/learning.py`** — CRUD kart/list:
- `POST /cards`, `POST /lists/{id}/words` → tworzą `LearningCard` + `SrsState(scope=main)`
  (dla listy systemowej / cards), enrichment w tle (`enrich_card`). **Wymaga sieci.**
- `DELETE /cards/{id}` → **hard delete** (`db.delete(card)`), brak tombstone.
- `DELETE /lists/{id}` → hard delete listy + **cascade hard delete kart** na niej.
- `PATCH /lists/{id}` rename, `POST /lists` create → walidacja nazw zarezerwowanych,
  unikalność `(profile_id, name)`.
- `move_card` → ustawia `deck_id`; przy ruchu na systemową dokłada brakujący `SrsState`.

**`models/__init__.py`**
- `LearningCard`: ma `updated_at` (`onupdate=func.now()`) → dobre dla `since`. Unikat
  `(user_id, profile_id, lemma_l2, pos, deck_id)`.
- `WordList`: ma tylko `created_at`, **brak `updated_at`**, brak soft‑delete. Unikat
  `(profile_id, name)`.
- Brak jakiegokolwiek `deleted_at` / tombstone w całym schemacie.
- `AppliedSyncMove` (idempotencja + LWW ruchów) i `ReviewLog.client_id` (unikat) już są.

**`services/lexical.py`** — `lookup()` **zawsze** woła `self.llm.lookup(...)` (OpenAI), a
dopiero potem dołącza dopasowania z DB i anotuje `in_learning` z kart użytkownika (PG).
Tzn. „PG‑first” istnieje na poziomie *członkostwa/enrichmentu* (`find_card_anywhere`,
reużycie `LexicalEntry`), ale **nie** na poziomie kandydatów lookupu (te zawsze idą z AI).

**Migracje** — `db/migrations.py`: lista idempotentnych `ALTER/CREATE … IF NOT EXISTS`.
Nowe zmiany schematu dokładamy jako kolejne instrukcje tej krotki.

### 2.4 Podsumowanie luk vs zasady

| Obszar | Dziś | Zasada łamana | Docelowo |
|---|---|---|---|
| Ustawienia offline | `updateSettings` online‑only, offline revert | Z3 | Room‑first + outbox `settings_update` |
| Tworzenie listy offline | `createWordList` online‑only | Z2/Z3 | lokalne ID + outbox `list_create` + remap |
| Rename listy offline | online‑only | Z3 | outbox `list_rename` |
| Usuwanie listy offline | online‑only | Z3 | outbox `list_delete` (+ decyzja o kartach) |
| Usuwanie karty offline | online‑only | Z3 | Room‑first + outbox `card_delete` |
| Move offline | działa (wzorzec OK) | — | ujednolicić w `outbox_ops` |
| Nauka/undo offline | działa | — | ujednolicić w `outbox_ops` |
| Push odporność | 404 wywala paczkę | (stabilność) | per‑item wynik, skip poison |
| Pull inkrementalny | `since` nieużywane, zawsze fullReplace | (koszt/UX) | `since` + tombstones |
| Odczyty | ad‑hoc API+cache per ekran | Z1 | Room jako źródło, `Flow` |
| Usunięcia z serwera | brak tombstone (`deleted_*=[]`) | (spójność) | soft‑delete + tombstones w pull |

---

## 3. Model docelowy

### 3.1 Przepływ danych

```
                    (nowa treść: lookup / import / enrichment / AI)
UI (Compose)  ── akcja ──►  Repozytorium  ──────────────────────────►  Backend + PG
   ▲                           │  │                                        │
   │ Flow (reaktywnie)         │  └── outbox_ops (FIFO, idempotentne) ──►  /sync/push
   └──────── Room (źródło ─────┘                                           │
             prawdy UX)   ◄──── applyPull(since | fullReplace) ◄── /sync/pull (+ tombstones)
```

- **Każda** mutacja „posiadanych” danych: najpierw Room (natychmiastowy efekt w UI przez
  `Flow`), następnie wpis do `outbox_ops`. Sync w tle wypycha outbox i pobiera zmiany.
- **Tylko** pozyskanie nowej treści (lookup, import, commit importu, enrichment, korekty
  AI, self‑edit z walidacją AI) wymaga sieci i idzie bezpośrednio do API (poza outboxem).
- UI nie rozgałęzia się na `isOnline` dla operacji z Z3. `isOnline` steruje wyłącznie:
  bannerem informacyjnym, dostępnością lookup/import/mic/korekt AI.

### 3.2 Room jako źródło prawdy
- DAO zwracają `Flow<…>` dla danych czytanych przez ekrany (listy, karty listy, kolejka
  SRS, ustawienia, profil). ViewModele obserwują `Flow` zamiast robić `refreshAll()`.
- Ekrany nie wołają `api.list*` bezpośrednio ani przez repo; czytają z Room. Sieć tylko
  odświeża Room w tle (pull) i realizuje nową treść.

### 3.3 Ujednolicony outbox (`outbox_ops`)
Jeden log operacji zamiast czterech tabel pending. FIFO po `seq`. Każdy typ ma payload
JSON. `client_op_id` = idempotencja globalna (używana też przez serwer).

Typy operacji (v1 zakresu):
`review`, `undo`, `move`, `list_create`, `list_rename`, `list_delete`, `card_delete`,
`settings_update`. (`self_edit` — opcjonalnie później; dziś online‑only.)

> Uwaga: `pending_lookups` (offline search inbox) **zostaje osobno** — to nie jest mutacja
> posiadanych danych, tylko kolejka *żądań nowej treści* realizowana po powrocie online
> (`flushPendingLookups`). Nie wchodzi do `outbox_ops`.

### 3.4 Lokalne ID i remap
- Listy tworzone offline dostają ID `local:<uuid>` (Room PK). Operacje odwołujące się do
  takiej listy (`move`, `card_delete` w kontekście, `list_rename/delete`) zapisują
  `local:<uuid>` w payloadzie.
- Push wysyła `list_create` z `client_op_id`; serwer zwraca `server_id`. Klient robi
  **remap**: podmienia `local:<uuid>` → `server_id` w `cached_lists`, `cached_cards.deckId`
  oraz w pozostałych, jeszcze niewy­słanych `outbox_ops`.
- Dopóki lista ma ID lokalne, operacje na niej mogą być wysyłane tylko **po** udanym
  `list_create` (zależność kolejności — realizowana przez FIFO + „hold” do czasu remap).

---

## 4. Kontrakty API — zmiany

### 4.1 `POST /sync/push` — odporny, per‑item (priorytet 1)

Rozszerzyć `SyncPushRequest` o `ops` (uporządkowana lista operacji) obok istniejących
`reviews`/`moves` (te zostają dla kompatybilności; docelowo mogą być podzbiorem `ops`).

Zasada nadrzędna: **żaden pojedynczy element nie może przerwać paczki.** Zamiast `raise
404` — zapis wyniku per element i kontynuacja. Zwrot 200 z listą wyników.

Szkic (Pydantic, `backend/app/schemas/__init__.py`):

```python
class SyncOp(BaseModel):
    client_op_id: UUID
    type: str            # list_create|list_rename|list_delete|card_delete|settings_update|...
    payload: dict
    created_at: datetime

class SyncOpResult(BaseModel):
    client_op_id: UUID
    status: str          # applied | skipped | failed
    server_id: UUID | None = None   # np. remap list_create
    error: str | None = None

class SyncPushRequest(BaseModel):
    reviews: list[SyncReviewItem] = Field(default_factory=list)
    moves: list[SyncMoveItem] = Field(default_factory=list)
    ops: list[SyncOp] = Field(default_factory=list)

class SyncPushResponse(BaseModel):
    applied: int
    skipped: int
    srs: list[SyncSrsState] = []
    moves_applied: int = 0
    moves_skipped: int = 0
    moves: list[SyncMoveResult] = []
    op_results: list[SyncOpResult] = []   # nowość
```

Zmiany w `sync.py`:
- `_apply_moves`: „card not found” i „target not found” → **`skipped`** + zapis
  `AppliedSyncMove(client_id)` (żeby retry był idempotentny), zamiast `raise 404`.
- Pętla reviews: `LearningCard ⨝ SrsState` → zamienić INNER JOIN na `outerjoin` albo:
  gdy brak `SrsState` scope=main → dołożyć go (`status='new'`); gdy brak karty →
  `skipped` (idempotentny wpis `ReviewLog(client_id)` z `card_id` NULL‑safe lub osobny
  rejestr zastosowanych client_id). **Nigdy `raise` w pętli.**
- Nowa obsługa `ops`: każdy typ w try/except; wynik → `op_results`. Idempotencja przez
  tabelę `applied_sync_ops(client_op_id PK)`.
- Cała funkcja: `applied`+`skipped`+`failed` liczone; jeden `db.commit()` na końcu (albo
  savepoint per‑op, żeby błąd jednej operacji nie brudził reszty — rekomendacja:
  `begin_nested()` per op).

Semantyka `op_results.status`:
- `applied` / `skipped` → klient **usuwa** operację z outboxu (skip = już zrobione lub
  nieaktualne).
- `failed` → klient zostawia w outboxie do ponowienia **z limitem prób** (park po N prób,
  żeby nie było wiecznej pętli); po parkowaniu operacja jest oznaczana i pomijana, a użytk.
  dostaje ewentualny komunikat przy jawnej akcji.

### 4.2 `GET /sync/pull` — tombstones + `since`

- `SyncPullResponse.deleted_card_ids` — realnie wypełniane z soft‑delete
  (`LearningCard.deleted_at >= since`).
- Dodać `deleted_list_ids: list[UUID]` (z `WordList.deleted_at`).
- `lists` w pull zwraca też `updated_at` (po dodaniu kolumny) — do inkrementalnej podmiany.
- Przy `since=None` → pełny stan (jak dziś). Przy `since=<ts>` → tylko `updated_at >=
  since` + tombstones w oknie.

### 4.3 Soft‑delete w PG
- `LearningCard.deleted_at: datetime | None` + wszystkie zapytania czytające (queue, lists,
  words, stats, lookup annotate) filtrują `deleted_at IS NULL`.
- `WordList.deleted_at` + `updated_at`.
- `DELETE /cards/{id}` i `DELETE /lists/{id}` → ustawiają `deleted_at` (soft), zamiast
  `db.delete`. Kasowanie listy: soft‑delete listy; karty na niej → decyzja produktowa
  (patrz 8). ReviewLog/SrsState zostają (potrzebne do historii/idempotencji).

---

## 5. Encje i migracje

### 5.1 Room (Android)

Nowa encja outbox:

```kotlin
@Entity(tableName = "outbox_ops")
data class OutboxOpEntity(
    @PrimaryKey(autoGenerate = true) val seq: Long = 0,
    val clientOpId: String,      // UUID, idempotencja
    val type: String,            // review|undo|move|list_create|...
    val payloadJson: String,
    val createdAt: Long,
    val attempts: Int = 0,
    val status: String = "pending", // pending|parked
    val lastError: String? = null,
)
```

- Migracja Room: **przejść z `fallbackToDestructiveMigration()` na jawne `Migration`**.
  Destructive kasuje niewy­słany outbox przy update aplikacji — niedopuszczalne dla
  offline‑first. `AppDatabase.version = 7`, `addMigrations(MIGRATION_6_7)`.
- `MIGRATION_6_7`: `CREATE TABLE outbox_ops (...)`; opcjonalnie skopiować istniejące
  `pending_reviews/moves/undos` do `outbox_ops` (albo utrzymać stare tabele równolegle w
  fazie przejściowej i migrować lazy przy starcie — bezpieczniejsze; patrz Faza 2).
- Dodać kolumny do `cached_lists`: `isLocalOnly: Boolean` (ID lokalne, jeszcze niewysłane),
  `pendingDelete: Boolean` (opcjonalnie, dla optimistic hide).
- DAO: dodać warianty `Flow<…>` (`observeLists`, `observeWords`, `observeQueue`,
  `observeSettings`).

### 5.2 PostgreSQL (backend, `db/migrations.py`)

Dopisać do `_STATEMENTS` (idempotentne):

```sql
ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_learning_cards_deleted_at ON learning_cards (deleted_at);
ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE TABLE IF NOT EXISTS applied_sync_ops (
  client_op_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  op_type VARCHAR(32) NOT NULL,
  server_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- `WordList.updated_at` w modelu SQLAlchemy: `onupdate=func.now()`.
- Uwaga na unikat `(profile_id, name)`: po soft‑delete listy o tej samej nazwie muszą móc
  powstać ponownie. Zamienić na **częściowy unikat** `WHERE deleted_at IS NULL`
  (`CREATE UNIQUE INDEX … ON word_lists (profile_id, name) WHERE deleted_at IS NULL`) i
  zdjąć stary `UniqueConstraint`. Analogicznie rozważyć dla `learning_cards`.

---

## 6. Idempotencja, remap, konflikty

- **Idempotencja**: `client_op_id` per operacja. Serwer trzyma `applied_sync_ops`
  (i istniejące `AppliedSyncMove`, `ReviewLog.client_id`). Ponowny push tego samego
  `client_op_id` → `skipped`.
- **Kolejność**: outbox FIFO (`seq`). Operacje na liście lokalnej „czekają” aż
  `list_create` się zremapuje.
- **Remap ID**: po `op_results` z `server_id` dla `list_create` — transakcyjnie podmień
  `local:<uuid>` w `cached_lists`, `cached_cards.deckId`, payloadach pozostałych
  `outbox_ops`. Dopiero potem oznacz `list_create` jako wysłane.
- **Konflikty (multi‑device)**: LWW.
  - Move: już zaimplementowane przez `moved_at` (LWW) — zachować.
  - Rename: LWW po `updated_at`/`created_at` operacji.
  - Delete vs edit: delete wygrywa (soft‑delete). Jeśli lokalna zmiana dotyczy karty
    z tombstone z serwera → lokalna zmiana odrzucona przy pull (karta znika).
  - Settings: `settings_update` to całościowy patch pól; LWW po `created_at` operacji.
  - Brak UI rozwiązywania konfliktów (świadomie, zgodne z „Znane ograniczenia” w QA).
- **Poison pill**: `attempts` + parkowanie po N (np. 5) próbach z `failed`. Parkowana
  operacja nie blokuje reszty (FIFO pomija parked). Log do diagnostyki.

---

## 7. Fazy implementacji (kolejność + uzasadnienie)

> Zasada: najpierw odblokować stabilność (poison‑pill), potem fundament (outbox + Room
> reaktywny), potem migracja poszczególnych mutacji, na końcu inkrementalny pull i
> sprzątanie UI. Każda faza zostawia aplikację w stanie działającym.

### Faza 0 — Hotfix push 404 (backend, bez zmian klienta)
**Dlaczego pierwsze:** to jedyny bug, który *dziś* trwale zakleszcza sync użytkowników.
Można wdrożyć niezależnie od reszty.
- `sync.py`: `_apply_moves` i pętla reviews — zamienić `raise HTTPException(404)` na
  `skip` z zapisem idempotentnym; INNER JOIN reviews → `outerjoin` + dokładanie
  brakującego `SrsState`. Jeden przegląd tranzakcyjności (savepoint per element).
- **Kryteria akceptacji:**
  - Push z ocenami dla nieistniejącej/soft‑usuniętej karty → **200**, ta pozycja
    `skipped`, pozostałe `applied`.
  - Ocena karty bez `SrsState` scope=main → `SrsState` powstaje, ocena `applied`.
  - Test: `backend/tests/test_sync.py` — przypadki „missing card”, „missing srs”, „stale
    move”. Brak jakiegokolwiek 404 z `/sync/push` przy poprawnym tokenie.

### Faza 1 — Fundament outbox + Room reaktywny (Android, bez zmiany zachowania)
- Dodać `outbox_ops` + `OutboxOpEntity` + DAO; `AppDatabase v7` z jawną migracją
  (koniec z `fallbackToDestructiveMigration`).
- Warstwa `Outbox` w repo: `enqueue(type, payload)`, `drain()`, remap, attempts/park.
- `pushOutbox()` czyta z `outbox_ops` (na start mapując istniejące review/move/undo na
  operacje — albo utrzymując stare tabele i dopisując nowe równolegle w fazie przejściowej).
- Dodać `Flow` do DAO i przełączyć **odczyty** (listy/karty/queue/settings) na Room `Flow`
  w repo; pull tylko aktualizuje Room.
- **Kryteria akceptacji:**
  - Aktualizacja aplikacji (v6→v7) **nie kasuje** danych ani outboxu.
  - Oceny/moves/undo nadal działają (regres 0) i idą przez `outbox_ops`.
  - Ekrany listy/kart odświeżają się reaktywnie po zmianie Room (bez ręcznego refresh).

### Faza 2 — Migracja mutacji „posiadanych” danych na local‑first
Kolejno (każde: Room‑first + `outbox_ops` + wynik push):
1. `settings_update` (najprostsze, największy zysk dla Z3): `updateSettings` zapisuje Room,
   enqueue op; `SettingsViewModel` przestaje cofać zmianę offline. Backend: `PUT
   /me/settings` obsługiwane też przez `ops` (albo push woła istniejący serwis).
2. `card_delete`: Room‑first (usuń/oznacz), enqueue; serwer soft‑delete.
3. `list_rename`: Room‑first, enqueue.
4. `list_create` + remap ID lokalnych.
5. `list_delete` (+ decyzja o kartach — patrz 8).
- **Kryteria akceptacji (per operacja):** akcja w trybie samolotowym daje natychmiastowy
  efekt w UI i utrzymuje się po restarcie; po powrocie online stan na serwerze zgodny;
  brak duplikatów; brak 404; idempotencja przy podwójnym pushu.

### Faza 3 — Soft‑delete + tombstones + inkrementalny pull (backend + Android)
- Backend: kolumny `deleted_at`/`updated_at`, filtry `deleted_at IS NULL` we wszystkich
  odczytach, `/sync/pull` wypełnia `deleted_card_ids` + `deleted_list_ids`, częściowy
  unikat nazw list.
- Android: `syncNow` używa `since = lastPulledAt` dla zwykłego sync; `fullReplace` tylko
  dla: pierwszy sync profilu, zmiana pary językowej, jawny reset. `applyPull` stosuje
  tombstones (usuwa lokalnie), zamiast czyścić profil.
- `createCard`/`selfEdit`/`restore` przestają wołać `syncNow(fullReplace=true)` —
  wystarczy `requestNow()` (inkrementalny pull dociągnie enrichment).
- **Kryteria akceptacji:**
  - Usunięcie karty/listy na urządzeniu A → po sync znika na urządzeniu B (tombstone).
  - Zwykły sync pobiera tylko zmienione rekordy (weryfikacja rozmiaru odpowiedzi/logów).
  - Pełny pull tylko w wymienionych 3 przypadkach.

### Faza 4 — Sprzątanie UI (agnostyczność sieci dla Z3)
- Usunąć rozgałęzienia `isOnline` z operacji Z3 w `HomeViewModel`, `PracticeViewModel`,
  `SettingsViewModel`, `HomeScreen`. `isOnline` zostaje tylko dla: banner, lookup/import,
  mic, korekty/related/historia (AI).
- Ujednolicić: brak osobnych ścieżek „offline vs online” w repo dla odczytów i mutacji Z3.
- **Kryteria akceptacji:** manualny przegląd — te same akcje i te same ekrany offline i
  online (poza pozyskiwaniem treści). Testy UI/instrumentalne dla trybu samolotowego.

---

## 8. Decyzje produktowe do potwierdzenia (nie blokują startu)

1. **Kasowanie listy a karty na niej.** Dziś backend hard‑kasuje karty razem z listą.
   Opcje docelowe: (a) karty wracają do „Uczę się” (`deck_id=NULL`), (b) soft‑delete kart
   razem z listą. Rekomendacja: **(a)** — mniej utraty danych, spójne z „telefon = źródło
   prawdy”. Wymaga potwierdzenia.
2. **PG‑first dla kandydatów lookupu.** Dziś lookup zawsze woła OpenAI. Jeśli celem jest
   oszczędność kosztów/latencji: dodać wcześniejszy krok „szukaj w `LexicalEntry` /
   kartach; jeśli pewny match → zwróć bez AI”. To optymalizacja *ortogonalna* do
   offline‑first (nie blokuje planu), ale jest wymieniona w modelu produktowym.
3. **Profile językowe offline.** Tworzenie/aktywacja profilu offline — poza zakresem v1
   (wymaga remapu podobnego do list). Domyślnie **online‑only** na start.

---

## 9. Scenariusze regresji (must‑pass)

Bazują na `docs/qa-manual-2026-08-04.md` (sekcja 1 „Full offline”) + nowe przypadki.

**Airplane mode — mutacje Z3:**
- R‑A1 Zmiana ustawień (tryb/kierunek/limit/motyw) offline → utrzymuje się po restarcie →
  po online zgodne z serwerem. (dziś: **regres — cofa się**).
- R‑A2 Utworzenie listy offline → widoczna, można dodać do niej ruchem karty → po online
  dostaje server ID, karty poprawnie przypięte (remap).
- R‑A3 Rename listy offline → po online nazwa na serwerze zgodna.
- R‑A4 Usunięcie listy offline → znika lokalnie; po online znika na serwerze; karty wg
  decyzji z §8.1.
- R‑A5 Usunięcie karty offline → znika lokalnie i po online na serwerze; nie „wraca” przy
  następnym pull.
- R‑A6 Move między listami offline (w tym na „Uczę się”) → bez duplikatów; po online
  zgodne.
- R‑A7 Practice offline: oceny + Undo → po online SRS zgodny z ostatnią oceną, bez
  podwójnych review (idempotencja).

**Powrót online / pending inbox:**
- R‑B1 Offline search → „Oczekujące”/Pending stub → po online flush do prawdziwej karty
  (`pending→ready`), licznik inbox zgodny, brak duplikatów (istniejący dedup zachowany).
- R‑B2 Wiele operacji w outboxie różnych typów → wysłane w kolejności FIFO; częściowe
  `skipped` nie blokują reszty.

**Push 404 / poison pill:**
- R‑C1 Ocena karty usuniętej na innym urządzeniu → push 200, pozycja `skipped`, reszta
  `applied`, outbox się czyści (brak zakleszczenia).
- R‑C2 Ruch na listę usuniętą serwerowo → `skipped`, brak 404.
- R‑C3 Operacja trwale nieakceptowalna → po N próbach `parked`, nie blokuje kolejnych.

**Multi‑device / tombstones:**
- R‑D1 Usunięcie na A → znika na B po sync.
- R‑D2 Konflikt rename/move A vs B → LWW, stan deterministyczny.

**Migracja / update aplikacji:**
- R‑E1 Update v6→v7 z niewy­słanym outboxem i danymi → nic nie ginie (koniec z
  destructive migration).

**Smoke (z QA §7):** R1–R7 nadal zielone. Szczególnie R3 (rename/delete listy; „Uczę się”
nieusuwalne) i R7 (dane wracają po syncu).

---

## 10. Poza zakresem (świadomie)

- **Offline lookup / import / enrichment AI** — z definicji wymagają sieci (Z2). Offline
  jedynie kolejkujemy żądanie (istniejące „Oczekujące”).
- **Korekty kart, self‑edit z walidacją AI, historia/restore** — pozostają online‑only w
  v1 (zależą od backendu/LLM). Ewentualny lokalny self‑edit → osobna iteracja.
- **Tworzenie/aktywacja profili językowych offline** — poza v1 (§8.3).
- **UI rozwiązywania konfliktów multi‑device** — utrzymujemy LWW bez interakcji użytk.
- **PG‑first kandydatów lookupu** — optymalizacja kosztowa, nie część refaktoru
  offline‑first (§8.2).
- **Zmiana modelu SRS/FSRS** — bez zmian; sync przenosi istniejące pola `SyncSrsState`.

---

## 11. Mapa plików (gdzie co zmieniać)

**Backend**
- `app/api/v1/sync.py` — Faza 0 (push per‑item), Faza 3 (pull tombstones/since, obsługa `ops`).
- `app/schemas/__init__.py` — `SyncOp`, `SyncOpResult`, `SyncPushRequest.ops`,
  `SyncPushResponse.op_results`, `deleted_list_ids`, `WordList*` z `updated_at`.
- `app/models/__init__.py` — `deleted_at` (card/list), `updated_at` (list, onupdate),
  model `applied_sync_ops`.
- `app/db/migrations.py` — nowe idempotentne instrukcje (§5.2), częściowe unikaty.
- `app/api/v1/learning.py` — `DELETE` → soft‑delete; filtry `deleted_at IS NULL` w:
  `list_cards`, `list_words`, `srs_queue`, `dashboard_stats`, `word_lists.list_word_lists`,
  `lexical._annotate_candidates`.
- `app/services/word_lists.py` — filtry `deleted_at IS NULL`, logika unikatu nazw.
- `backend/tests/` — `test_sync.py` (jest w repo, rozbudować), nowe testy push/pull.

**Android**
- `data/local/db/Entities.kt`, `Daos.kt`, `AppDatabase.kt` — `outbox_ops`, `Flow` w DAO,
  wersja 7 + `Migration`, kolumny `cached_lists`.
- `data/local/OfflineStore.kt` — enqueue/drain/remap outbox; `applyPull` z tombstones i
  bez `clearProfile` w trybie inkrementalnym.
- `data/LearningRepository.kt` — mutacje Z3 na Room‑first + outbox; odczyty na Room `Flow`;
  `syncNow` z `since`; `pushOutbox` per‑item; usunięcie `syncNow(fullReplace=true)` z
  `createCard`/`selfEditCard`/`restoreCard`.
- `data/api/VocabularioApi.kt`, `data/api/Models.kt` — `ops`/`op_results`,
  `deleted_list_ids`.
- `ui/home/HomeViewModel.kt`, `ui/practice/PracticeViewModel.kt`,
  `ui/settings/SettingsViewModel.kt`, `ui/home/HomeScreen.kt` — usunięcie rozgałęzień
  `isOnline` dla Z3.
- `data/sync/SyncWorker.kt` — `syncNow()` bez wymuszania `fullReplace`.

---

## Prompt dla agenta implementującego

> Skopiuj poniższy blok jako jedyną instrukcję startową.

```
Jesteś agentem implementującym w repozytorium Vocabulario
(Android: Kotlin + Compose + Room; backend: FastAPI + PostgreSQL, migracje = idempotentny
raw SQL w backend/app/db/migrations.py, brak Alembica).

Twoim jedynym źródłem prawdy jest dokument docs/plan-offline-first.md — przeczytaj go w
całości przed startem i trzymaj się jego faz, kontraktów i kryteriów akceptacji.

Cel: architektura offline-first, w której telefon (Room) jest źródłem prawdy dla UX, a
backend + PostgreSQL są magazynem trwałym i mechanizmem spójności. Sieć jest potrzebna
WYŁĄCZNIE do pozyskania nowej treści (lookup, import, enrichment/AI, korekty AI).

Twarde zasady (nie łam):
- Z1: UI i logika czytają/piszą do Room; sync to spójność, nie warunek działania.
- Z2: API tylko dla nowej treści (lookup/import/enrichment). Reszta lokalnie + sync w tle.
- Z3: offline == online dla: ustawień, tworzenia/rename/usuwania list, usuwania słów,
  move między listami, nauki (oceny SRS, undo), przeglądania. Jedyna różnica offline:
  brak lookupu/importu/enrichmentu nowych słów.
- Karta jest osobna per para językowa (profile_id).
- Idempotencja przez client_op_id / client_id; kolejność outbox FIFO; remap ID lokalnych
  list (local:<uuid> → server UUID) po list_create.
- Konflikty multi-device: LWW, bez UI rozwiązywania.

Kolejność prac (rób fazami, każda faza zostawia apkę działającą, dopisuj/aktualizuj testy):
0) HOTFIX backend: POST /sync/push nie może przerywać całej paczki jednym elementem.
   „card not found” / brak SrsState / „stale move” → skip (idempotentnie), NIGDY raise 404.
   To źródło produkcyjnego buga „POST /api/v1/sync/push → 404”. Wdrażalne osobno.
1) Android: encja outbox_ops + jawna migracja Room v6→v7 (KONIEC z
   fallbackToDestructiveMigration — nie wolno kasować niewysłanego outboxu przy update),
   DAO z Flow, odczyty ekranów z Room (reaktywnie).
2) Android: migracja mutacji Z3 na Room-first + outbox_ops, w kolejności:
   settings_update, card_delete, list_rename, list_create (+remap), list_delete.
3) Backend + Android: soft-delete (deleted_at) + tombstones w /sync/pull
   (deleted_card_ids, deleted_list_ids) + inkrementalny pull (since); fullReplace tylko
   dla pierwszego sync / zmiany pary / resetu; częściowy unikat nazw list WHERE
   deleted_at IS NULL.
4) Android: usuń rozgałęzienia isOnline dla operacji Z3 (Home/Practice/Settings VM +
   HomeScreen). isOnline zostaje tylko dla bannera, lookup/import, mic, korekt/AI.

Ograniczenia zakresu (NIE implementuj w tej iteracji): offline lookup/import/enrichment AI,
korekty/self-edit/historia offline, tworzenie profili językowych offline, UI konfliktów,
PG-first kandydatów lookupu (to osobna optymalizacja kosztowa).

Wymagania jakościowe:
- Po każdej fazie: spełnione kryteria akceptacji z dokumentu i scenariusze regresji z §9
  (szczególnie tryb samolotowy: R-A1..R-A7, powrót online: R-B1/B2, push: R-C1..C3,
  tombstones: R-D1/D2, update apki: R-E1). Utrzymaj smoke R1–R7 z docs/qa-manual-2026-08-04.md.
- Zweryfikuj założenia w kodzie; nie zgaduj. Pliki do zmiany: patrz §11 dokumentu.
- NIE commituj bez wyraźnej prośby użytkownika.
- Decyzje produktowe z §8 (los kart przy kasowaniu listy; profile offline) potwierdź z
  użytkownikiem, zanim je zaimplementujesz; do tego czasu przyjmij rekomendacje z dokumentu.
```
```

---

## 12. Status implementacji (2026‑08‑07)

Wykonane fazy 0–4 (kompiluje się: backend `py_compile` + import mapperów; Android
`:app:compileDebugKotlin` BUILD SUCCESSFUL). Kluczowe decyzje/odstępstwa względem planu:

- **Faza 0** — `backend/app/api/v1/sync.py`: `_apply_moves` i pętla reviews już nie rzucają
  404. Brak karty → `skipped`; brak `SrsState(scope=main)` przy istniejącej karcie →
  tworzony przed `apply_review`. Batch commit’uje raz, bez poison‑pill.
- **Faza 1** — Room v6→v7 z jawną `MIGRATION_6_7` (nowa tabela `outbox_ops` + kolumny
  `cached_lists.isLocalOnly/pendingDelete`). Zamiast `fallbackToDestructiveMigration()` jest
  `fallbackToDestructiveMigrationFrom(1..5)` → dane (w tym niewysłany outbox) przeżywają
  aktualizację z v6.
- **Faza 2** — mutacje Z3 są Room‑first + wpis do `outbox_ops`. **Odstępstwo od planu:**
  outbox drenuje przez **istniejące, idempotentne endpointy REST** (POST/PATCH/DELETE
  `lists`, DELETE `cards`, PUT `settings`), a nie przez rozszerzenie `/sync/push` o kanał
  `ops`. Powód: mniejsze ryzyko, endpointy już istnieją. Drenaż FIFO z parkowaniem po
  `MAX_OP_ATTEMPTS=5`; listy offline dostają ID `local:<uuid>` i remap po stworzeniu na
  serwerze (remap obejmuje cache, karty, `pending_moves.targetListId` i payloady operacji).
- **Faza 3** — `LearningCard.deleted_at`, `WordList.deleted_at/updated_at`; pełne unikaty
  zamienione na **częściowe unikaty** (`WHERE deleted_at IS NULL`) — DDL z `create_all`
  i z `migrations.py` są identyczne. DELETE karty/listy = soft‑delete; **usunięcie listy NIE
  kasuje kart — wracają do „Uczę się” (deck_id=NULL)** (spójne z zachowaniem offline na
  kliencie). `/sync/pull` wypełnia `deleted_card_ids` + `deleted_list_ids` gdy podano `since`.
  Android: `syncNow()` domyślnie inkrementalny (`since = lastPulledAt`), pełny replace tylko
  gdy `fullReplace=true` lub pierwszy sync profilu.
- **Faza 4** — `syncNow(fullReplace=true)` usunięte z `createCard`/`syncPendingReviews`/
  powrotu‑online (teraz inkrementalne); `SyncWorker` inkrementalny. Rozgałęzienia `isOnline`
  pozostałe w UI dotyczą wyłącznie operacji Z2 (import/lookup/voice/korekty/historia) — to
  poprawne (wymagają sieci).

**Nie zrobione / świadomie pominięte:** pełny refactor odczytów na Room `Flow` (UI nadal
odświeża przez `refreshAll()` po mutacji — działa, bo repo jest Room‑first); PG‑first lookup
w `lexical.py` (osobna optymalizacja kosztowa); testy integracyjne sync (brak fixture DB/auth
w repo).

**Do weryfikacji ręcznej (device‑level):** migracja v6→v7 na realnym urządzeniu, scenariusze
regresji §9 (tryb samolotowy, powrót online, tombstones na drugim urządzeniu).

---

*Autor analizy: agent analityczny. Podstawa: przegląd kodu Android (LearningRepository,
OfflineStore, Daos, Entities, AppDatabase, NetworkMonitor, SyncWorker, SyncScheduler,
Home/Practice/Settings VM, VocabularioApi) i backendu (sync.py, learning.py, word_lists.py,
lexical.py, models, schemas, migrations) na dzień 2026‑08‑07.*
