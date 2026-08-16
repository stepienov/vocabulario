# Raport i plan: dlaczego apka jest wolna i jak odciąć UI od BE

> Analiza kodu Android + backend z 2026‑08‑16.
> Zakres: start, dashboard, listy, nauka, SRS, sync, Room, Compose.
> Poprzedni dokument: [`plan-offline-first.md`](plan-offline-first.md) (2026‑08‑07) — mutacje local‑first są w dużej mierze zrobione. **Odczyty nadal są network‑first.** To jest główna przyczyna wolnego telefonu.

---

## 0. Werdykt

Aplikacja **nie jest wolna dlatego, że karty są ciężkie**. Karta to tekst. 10 tysięcy kart to wciąż mały zbiór na telefonie (szacunek: 20–80 MB JSON w Room — Android to łyka bez mrugnięcia).

Aplikacja jest wolna, bo **gdy telefon ma internet (czyli zawsze), prawie każdy ekran najpierw pyta backend, a dopiero potem pokazuje to, co i tak leży w Room**. Room jest cache’em awaryjnym na tryb samolotowy, nie źródłem prawdy dla UX.

Mięso tej apki (SRS, dashboard, listy, słówka, ustawienia) **już jest zapisane lokalnie**. Kod tego nie wykorzystuje, dopóki `NetworkMonitor` mówi „online”.

Backend jest potrzebny tylko do:

| Operacja | BE potrzebny? | Dziś |
|---|---|---|
| Import pliku / wklejki / analiza tekstu | tak | OK — job + poll |
| Szukanie nowego słowa (lookup) | tak | OK |
| Enrichment / korekta AI / self‑edit z walidacją | tak | OK |
| Dashboard, listy, karty, kolejka SRS | **nie** | **czeka na BE** |
| Ocena karty, undo, move, CRUD list | **nie** | mutacje już local‑first; odczyt po nich często znów bije w API |
| Sprawdzenie odpowiedzi (type) | **nie** | najpierw BE, lokalnie tylko przy błędzie |
| Dystraktory (choice) | **nie** | najpierw BE |
| Ustawienia, profil, locale | **nie** (po pierwszym syncu) | najpierw BE |

---

## 1. Co już jest (i czemu to nie ratuje telefonu)

Od sierpnia jest solidny fundament offline:

- Room `vocabulario.db` v8: karty, listy, profil, ustawienia, outbox, pending reviews/moves/lookups.
- Lokalny FSRS (`LocalFsrs`) — ocena karty nie czeka na serwer.
- Outbox FIFO (`outbox_ops`) + `pending_reviews` / `pending_moves`.
- `GET /sync/pull?since=` + tombstones (`deleted_card_ids`, `deleted_list_ids`).
- WorkManager: sync co 15 min + `requestNow()`.
- Tworzenie / rename / delete listy, delete karty, ustawienia — zapis do Room, push w tle.
- Home ma obserwatory Room (`listsChanges` / `cardsChanges`) — ale **równolegle** `refreshAll()` i tak woła API.

Problem: warstwa odczytu w `LearningRepository` jest napisana jako **„jeśli online → API, jak padnie → Room”**. Telefon testowy jest online. Więc każda nawigacja = RTT do komputera w LAN albo do Railway + zapytania SQL + serializacja pełnego `content` każdej karty.

`plan-offline-first.md` §12 wprost to zostawił:

> *„Nie zrobione: pełny refactor odczytów na Room Flow (UI nadal odświeża przez refreshAll()).”*

To „nie zrobione” jest tym, co czujesz na telefonie.

---

## 2. Ścieżka, którą widzisz po odpaleniu apki

Poniżej realna sekwencja przy starcie na fizycznym telefonie (online). Każdy wiersz to **blokada UX** albo równoległy ruch sieciowy, który i tak obciąża ten sam BE / ten sam Wi‑Fi.

### 2.1 Splash (do 8 s spinnera)

`AppViewModel.bootstrap()`:

1. `tokenStore.awaitReady()` — do 1,5 s.
2. W timeoutcie 8 s, **sekwencyjnie**:
   - `AuthRepository.ensureActiveProfile()` → `GET /profiles` (**bez cache, bez timeoutu `apiTry`**).
   - `applyAppLocaleFromActiveProfile()` → znowu `getActiveProfile()` → znowu `GET /profiles`.
   - `syncThemeFromSettings()` → `getSettings()` → `GET /me/settings`.
   - `hasProfile()` → **trzeci** `GET /profiles`.

Dopiero potem znika spinner. Jeśli LAN/Railway nie odpowie w 8 s — i tak idzie na Home, ale pierwsze 1–8 s to czekanie na rzeczy, które Room już ma (`cached_profile`, `local_settings`).

Potem w tle: `syncNow()` = flush lookupów (LLM!) + push + pull + znowu `GET /profiles`.

### 2.2 Home — `refreshAll()` w `init`

Sekwencyjnie:

1. `getActiveProfile()` → `GET /profiles` (kolejny).
2. `dashboardStats(7)` → `GET /stats?days=7` — **~15 zapytań SQL** (due, new, learning, mastered, first‑review‑today, reviews‑today, total, **7 osobnych forecastów dzień po dniu**, last added, last reviewed). Timeout 8 s. Lokalny fallback jest kaleki (brak forecastu, `reviews_done_today = 0`, `srs_mastered = 0`).
3. `listWordLists()` → `GET /lists` — backend liczy `COUNT(*)` **osobno dla każdej listy** (N+1).
4. `listWords(selectedId)` → `GET /lists/{id}/words` — **pełny `content` każdej karty**, bez timeoutu `apiTry` (może wisieć do **200 s** `callTimeout` OkHttp).

Dopóki (4) nie wróci, zakładka Listy pokazuje pełnoekranowy spinner (`loading = true` gdy `listWords` puste).

Dashboard nie ma lokalnego „pokaż od razu” — `stats` zostaje `null` aż wróci `/stats`.

### 2.3 Co jeszcze bije w BE, gdy nic nie robisz

| Trigger | Co woła | Jak często |
|---|---|---|
| `ON_RESUME` Home | `GET /stats` | każde wejście na Home / powrót z Ćwicz |
| Dashboard otwarty | `GET /stats` | co 30 s |
| Enrichment `pending` na liście | `GET /lists/{id}/words` (cała lista!) | co 2,5 s, max 40 razy |
| `card_activity_status` (korekta) | to samo | co 2,5 s, bez limitu |
| Learning screen, karty pending | `GET /cards` (wszystkie karty profilu) | co 3 s |
| `EnrichmentCheckWorker` | `getSettings` + **`listCards()` dwa razy** + `syncNow` | w tle |
| Sync okresowy | pull + push + flush lookupów | 15 min + po każdej ocenie |

Polling enrichmentu to jeden z najgorszych wzorców w tej apce: żeby sprawdzić, czy **jedna** karta dostała `ready`, ściągasz **całą listę z pełnym JSON‑em contentu**.

---

## 3. Mapa: ekran → czy czeka na BE

Legenda: **blokuje UI** = spinner / pusta lista / brak przycisków, aż wróci sieć.

### Home / Dashboard

| Dane | Źródło dziś (online) | Powinno być |
|---|---|---|
| due / new / mastered / forecast | `GET /stats` **blokuje** | Room: `cached_cards` + lokalny review log |
| profil (język, CEFR) | `GET /profiles` **blokuje start** | `cached_profile` |
| przycisk „Ucz się” | nie czeka, ale liczby na tile’ach tak | lokalne liczniki |

### Home / Listy

| Dane | Źródło dziś (online) | Powinno być |
|---|---|---|
| lista list + liczniki | `GET /lists` **blokuje** | `cached_lists` + `COUNT` w Room |
| słowa na liście | `GET /lists/{id}/words` **blokuje** (spinner) | `cached_cards` WHERE deckId |
| zmiana listy | czyści `listWords` → znowu spinner + API | natychmiast z Room |
| create/rename/delete listy | Room‑first (OK) | OK; nie wołać potem `GET /lists` |
| delete/move karty | Room‑first (OK) | OK; nie wołać potem `GET /lists/{id}/words` |

`selectList()` **zeruje karty** przy zmianie listy, więc nawet jeśli Room ma dane, użytkownik widzi puste + spinner, aż wróci sieć.

### Home / Szukaj

Lookup **musi** iść na BE — to jest OK. Offline kolejkuje stub. Tu nie ma błędu produktowego.

### Ćwicz (Practice)

`loadQueue()` sekwencyjnie:

1. `getSettings()` → `GET /me/settings` (8 s timeout).
2. `getActiveProfile()` → `GET /profiles`.
3. `getQueue()`:
   - jeśli Room ma kolejkę → zwraca lokalnie (OK) i w tle `requestNow()`.
   - jeśli Room puste → **`syncNow(fullReplace = true)` do 12 s**, potem `GET /srs/queue`.
4. Jeśli tryb choice: `getDistractors()` → `POST /srs/distractors` (BE ładuje **wszystkie karty profilu** z PG, żeby złożyć 8 opcji). UI: `loadingChoices = true`.
5. Type: `checkAnswer()` → najpierw `POST /srs/check-answer`, lokalnie tylko gdy API padnie.

Ocena (`submitReview`) jest local‑first — to jedyny szybki kawałek tego ekranu. Potem i tak `pushOutbox()` synchronicznie w `runCatching` + `requestNow()`.

### Uczę się (Learning)

`listCards()` online → `GET /cards` (wszystkie karty, pełny content). Spinner do powrotu. Potem poll co 3 s tym samym endpointem.

### Ustawienia / Profil

`getSettings` + `getActiveProfile` + `listProfiles` — wszystko API‑first. Zmiana ustawień jest już Room‑first.

### Dodawanie słowa z lookupu

`createCard` / `addWordToList` **muszą** iść na BE (enrichment). To OK. Ale po sukcesie `createCard` woła `syncNow()` — zbędny pull, który może przyciąć UI jeśli ktoś czeka na odświeżenie list.

---

## 4. Co konkretnie obciąża apkę (nie tylko „sieć”)

### 4.1 Network‑first odczyty — waga: krytyczna

Plik: `LearningRepository.kt`.

Funkcje, które **online ignorują Room i czekają na API**:

```
listWordLists()     → GET /lists
listWords()         → GET /lists/{id}/words   (BRAK apiTry — do 200 s)
listCards()         → GET /cards
dashboardStats()    → GET /stats
getSettings()       → GET /me/settings
listProfiles()      → GET /profiles
getActiveProfile()  → GET /profiles
getDistractors()    → POST /srs/distractors
checkAnswer()       → POST /srs/check-answer
AuthRepository.ensureActiveProfile() / hasProfile() → GET /profiles (bez cache)
```

`cachedWordLists()` / `cachedListWords()` **istnieją** i są używane tylko w `scheduleRoomRefresh` (reakcja na zmianę Room). Ekran startowy ich nie używa.

### 4.2 Timeouty OkHttp vs timeouty repo

`AppModule.kt`:

- `connectTimeout` 15 s
- `readTimeout` **180 s**
- `writeTimeout` **180 s**
- `callTimeout` **200 s**

`apiTry` tnie część odczytów do 8 s. **`listWords` nie używa `apiTry`.** Na chwiejnym Wi‑Fi / śpiącym BE na PC użytkownik może patrzeć w spinner minuty.

180 s read timeout ma sens dla importu/LLM. Nie ma sensu dla `GET /lists`.

### 4.3 Backend: ciężkie endpointy wołane jakby były tanie

**`GET /stats`** (`learning.py` `dashboard_stats`): ~15 round‑tripów SQL, w tym pętla 7 dni forecastu. Każde wejście na Home + co 30 s.

**`GET /lists`**: N+1 `COUNT(*)` per lista (`word_lists.py`).

**`GET /lists/{id}/words` i `GET /cards`**: zwracają pełny `content` (koniugacje, przykłady, similar_words, synonimy…). Przy 2–8 KB na kartę:

| Karty | Rozmiar odpowiedzi (szacunek) |
|---|---|
| 200 | 0,4–1,6 MB |
| 2 000 | 4–16 MB |
| 10 000 | 20–80 MB |

To leci **przy każdym otwarciu listy** i **co 2,5 s przy pollingu**.

**`POST /srs/distractors`**: `SELECT * FROM learning_cards` całego profilu, potem sitko w Pythonie. Przy 10k kart to nie jest „szybki endpoint”.

**`GET /sync/pull`**: przy `since=None` / `fullReplace` — wszystkie karty + content. OK na pierwszy sync. `getQueue()` przy pustym Room wymusza właśnie `fullReplace`.

### 4.4 Room: cache jest, ale źle czytany

Brak indeksów na `cached_cards(profileId)`, `(profileId, deckId)`, `(profileId, status, nextReviewAt)`. Przy 10k kart każdy `learningCards` / `cardsForDeck` to full scan. Na telefonie to wciąż milisekundy — nie to boli dziś — ale trzeba dodać zanim listy urosną.

`observeForProfile` zwraca **całe wiersze** (w tym `contentJson`) tylko po to, by złożyć sygnaturę `id|deckId`. Przy syncu 10k kart Flow wyrzuca 10k obiektów do RAMu, ViewModel i tak idzie do `cachedWordLists()`.

`withComputedWordCounts` / `countWordsOnList` dla inboxa robi merge stubów + kart przy **każdej** liście. `applyPendingInboxCounts` **zapisuje** `wordCount` z powrotem do Room → może budzić obserwator → `scheduleRoomRefresh` → kolejny odczyt.

`localDistractors` ładuje `allCards(profileId)` i parsuje JSON — OK offline, ale nie powinno być na ścieżce krytycznej UI (precompute / cache 8 opcji przy syncu albo przy otwarciu karty).

### 4.5 Compose / ViewModele

- Jeden gigantyczny `HomeUiState` (listy + słowa + lookup + import + self‑edit + historia + filtry). Każdy `copy()` przebudowuje cały Home, w tym zakładki, których nie widać.
- `visibleListWords` to computed property: **sort + filter całej listy przy każdej rekompozycji** (np. ticker, poll, notice).
- `selectList` czyści `listWords` → flash pustki + spinner, nawet gdy Room ma dane.
- Wspólna flaga `loading` dla search i listy.
- `ListWordTile` parsuje `content` (glossy, import display) — `remember` to łagodzi, ale poll wymienia całą listę referencji → cache pada.
- `CardDetailContent` jest ciężki (koniugacje, siatki) — OK na overlay jednej karty, nie na liście. Lista tego nie renderuje, dopóki nie otworzysz overlay — tu jest dobrze.

### 4.6 Test na fizycznym telefonie vs emulator

`ApiBaseUrl`: telefon → `api.device.host` z `local.properties` (LAN, np. `192.168.1.54:8000`) albo Railway.

Na telefonie dokładają się:

- Wi‑Fi / 5 GHz / sen CPU na PC z uvicorn,
- `NET_CAPABILITY_VALIDATED` — chwilowy „offline” przy przełączaniu sieci → `refreshAll` / `syncNow` przy powrocie,
- cold start Room + Hilt + Compose,
- sekwencja z §2 (5–10 requestów zanim cokolwiek widać).

Emulator na `10.0.2.2` tego nie pokazuje w tej skali. Stąd „na kompie jakoś idzie, na telefonie zapaść”.

### 4.7 Rzeczy, które NIE są głównym winowajcą

- Algorytm FSRS na urządzeniu — tani.
- Import job — ma prawo być wolny (LLM); UI już polluje postęp.
- Lookup — ma prawo czekać.
- Motyw / stringi / i18n — nie blokują.
- Sam fakt 10k kart w SQLite — nie blokuje, **dopóki nie ściągasz ich z sieci przy każdym tapnięciu**.

---

## 5. Architektura docelowa

Jedna zasada, bez wyjątków dla odczytów „posiadanych” danych:

```
UI  ──czyta──►  Room (Flow / snapshot)     ── natychmiast
UI  ──pisze──►  Room + outbox              ── natychmiast
Sync (tło) ──►  push outbox, pull delta, enrichment status
BE  ◄────────   TYLKO: lookup, import, enrichment, AI, auth, pierwszy sync
```

Kontrakt ekranu:

1. **Pierwsza klatka** pochodzi z Room (albo pusto, jeśli naprawdę nie ma danych).
2. Spinner tylko gdy Room jest puste **i** trwa pierwszy sync profilu.
3. Sieć nigdy nie czyści już pokazanego UI (żadnego `listWords = emptyList()` przed API).
4. Polling enrichmentu = `SELECT id, enrichmentStatus FROM cached_cards WHERE status='pending'` albo inkrementalny pull `since`, nie `GET` całej listy.
5. Dashboard = czysta funkcja na `cached_cards` + lokalny log ocen z dzisiaj.

Co zostaje online‑only (zgodnie z Twoim planem):

- auth / onboarding / tworzenie profilu,
- lookup i voice search,
- import pliku / wklejki / commit joba,
- enrichment (tworzenie karty z nowym lematem),
- korekta AI, walidacja self‑edit, historia/restore (v1).

---

## 6. Plan implementacji

Cel: po tej pracy apka na telefonie ma otwierać dashboard i listy **w tej samej klatce** co tapnięcie, przy 0 i przy 10k kart. BE w tle. Tryb samolotowy = ten sam UX.

Fazy są ułożone tak, żeby każda zostawiała apkę działającą. Faza A sama w sobie powinna zabić 80% „zalamania na telefonie”.

### Faza A — Local‑first odczyty (Android, 2–4 dni) — **rób to pierwsze**

Nie ruszamy kontraktu BE. Zmieniamy tylko kto czeka.

**A1. Repo: Room najpierw, sieć w tle**

W `LearningRepository` rozdzielić:

```kotlin
suspend fun wordLists(): List<WordListResponse> = offlineWordLists(activeProfileId())
suspend fun listWords(listId: String): List<CardResponse> = cachedListWords(listId)
suspend fun dashboardStats(): DashboardStatsResponse = buildLocalDashboardStats()
suspend fun getSettings(): UserSettingsResponse = offlineStore.localUserSettings() ?: defaultSettings()
suspend fun getActiveProfile(): LanguageProfileResponse? = offlineStore.cachedActiveProfile()
suspend fun getQueue(): SrsQueueResponse = /* tylko localQueue */
suspend fun getDistractors(...): DistractorsResponse = localDistractors(...)
suspend fun checkAnswer(...): CheckAnswerResponse = LocalAnswerCheck...
```

Osobno, **nigdy z ViewModeli ekranów**:

```kotlin
fun refreshFromNetwork() { /* listProfiles, getSettings, syncNow — w SyncWorker / AppViewModel */ }
```

Usunąć `if (isOnline) api else room` z odczytów. `apiTry` zostaje tylko w sync / lookup / import / createCard.

**A2. ViewModele: pokaż cache, nie ustawiaj `loading` na odczyt**

- `HomeViewModel.refreshAll()`: najpierw `cachedWordLists` + `cachedListWords` + `buildLocalDashboardStats` + cached profile. Potem `syncScheduler.requestNow()`.
- `selectList`: **nie czyść** `listWords`. Podmień natychmiast z Room.
- `PracticeViewModel.loadQueue()`: settings/profile/queue z Room; `loading = queue.isEmpty() && !hasEverSynced`.
- `LearningViewModel.load()`: karty z Room.
- `SettingsViewModel` / `ProfileViewModel`: cache first.
- `AppViewModel.bootstrap()`: jeśli jest token + `cached_profile` → `HOME` od razu (0 requestów). `ensureActiveProfile` / locale / theme w tle. Spinner tylko przy braku jakiegokolwiek lokalnego profilu.

**A3. Lokalny dashboard na pełnym kontrakcie**

`buildLocalDashboardStats()` dziś jest stubem. Policzyć z Room:

- `due_count`, `srs_new`, `srs_learning`, `srs_mastered` (interval ≥ 21),
- `new_remaining` / `new_done_today` / `reviews_done_today` — dodać lekką tabelę `local_review_log(cardId, reviewedAt, grade)` albo czytać `pending_reviews` + `lastReviewedAt` z kart (przybliżenie; po syncu dokładamy z pulla),
- `forecast[7]` — `nextReviewAt` w oknach dni,
- `cards_total`, `last_added_at` / `last_reviewed_at`.

`GET /stats` przestaje być na ścieżce UI. Można zostawić jako diagnostykę / porównanie w debug.

**A4. Zabić głupi polling**

- Enrichment: obserwować Room (`enrichmentStatus` per karta). Sync w tle dociąga `ready`.
- Usunąć `startPollingIfNeeded` wołające `listWords` / `lookup` / `listCards` w pętli.
- Usunąć `LaunchedEffect` 30 s `loadStats` na dashboardzie — liczby i tak skoczą po lokalnej ocenie / pullu.
- `EnrichmentCheckWorker`: `SELECT COUNT(*) WHERE enrichmentStatus='pending'` w Room, nie `GET /cards` × 2.

**A5. Dwa klienty OkHttp**

- `apiFast`: connect 5 s, read 8 s, call 10 s — listy, stats, settings, profiles, distractors, check‑answer (zanim je wytniemy).
- `apiLong`: 180 s — import, lookup, enrichment, job progress.

Albo po prostu: odczyty z A1 nie używają sieci, więc timeout 180 s przestaje boleć UX.

**Kryteria A:**

- Airplane mode od zimnego startu (po wcześniejszym syncu): dashboard, listy, 10k kafelków, practice, ocena — bez jednego requestu.
- Online, Wi‑Fi do PC / Railway: pierwsze piksele Home < 200 ms od końca splash. Splash < 300 ms gdy Room ma profil.
- Przełączenie listy: karty natychmiast, zero spinnera.
- Log OkHttp przy zwykłym tapaniu Home/Listy/Ćwicz: **0** GET `/lists`, `/words`, `/stats`, `/cards`, `/srs/queue`, `/me/settings`, `/profiles`.

### Faza B — Room i 10k kart (Android, 1–2 dni)

Żeby „natychmiast” zostało natychmiast przy dużym zbiorze.

**B1. Indeksy**

```sql
CREATE INDEX ix_cards_profile ON cached_cards(profileId);
CREATE INDEX ix_cards_profile_deck ON cached_cards(profileId, deckId);
CREATE INDEX ix_cards_queue ON cached_cards(profileId, enrichmentStatus, status, nextReviewAt);
CREATE INDEX ix_lists_profile ON cached_lists(profileId);
```

**B2. Lekkie zapytania zamiast pełnych encji**

- Sygnatura zmian: `SELECT id, deckId FROM cached_cards WHERE profileId=?` — nie cały `contentJson`.
- Lista kafelków: nowy `CardListItem` (id, lemma, pos, gloss, enrichment, srs_status, interval, createdAt). `content` dopiero przy otwarciu karty / practice.
- `COUNT(*)` per deck w SQL, nie `list.size` po załadowaniu wszystkich kart.
- Kolejka SRS: `WHERE status!='new' AND nextReviewAt<=now` + `WHERE status='new' LIMIT :n` w SQL, nie filtr w Kotlinie na całym decku.

**B3. Compose**

- `remember(listWords, filter, sort) { applyListFilterSort(...) }` albo sort w SQL.
- Rozbić `HomeUiState` (dashboard / lists / add) albo przynajmniej nie trzymać `listWords` w stanie, gdy tab ≠ LISTS.
- `LazyColumn` zostaje; nie renderować `CardDetailContent` w kafelku (już tak jest).

**Kryteria B:** otwarcie listy 10k kafelków < 100 ms na mid‑range (pomiar `SystemClock` wokół DAO + first frame). Scroll 60 fps.

### Faza C — Sync w tle, nie na ścieżce UI (Android + drobny BE)

**C1.** `createCard` / `selfEdit` / `restore` — tylko `requestNow()`, nigdy `syncNow()` z ekranu.

**C2.** `createWordList` online: nie `drainOutboxOps()` synchronicznie przed return. Room ID `local:` jest OK; remap w workerze. UI już tak robi offline — zrównać online.

**C3.** `getQueue()`: nigdy `syncNow(fullReplace=true)` na tapnięcie „Ucz się”. Pusta kolejka = pusta kolejka. Pełny pull tylko: pierwszy login, zmiana pary, ręczny reset.

**C4.** Bootstrap / `AuthRepository`: czytać `cached_profile`. `GET /profiles` tylko w syncu.

**C5.** Po pullu: nie wołać `GET /lists` + `GET /words` „żeby się upewnić”. Pull **jest** źródłem. Obserwator Room odświeży UI.

**C6.** (BE, opcjonalnie w tej fazie) `GET /sync/pull` może zwracać `enrichment_status` bez pełnego `content`, gdy content się nie zmienił (`content_hash` / `updated_at` per pole). To tnie polling i delta‑sync przy 10k. Nie blokuje A/B.

### Faza D — Lokalne dystraktory i odpowiedź (Android)

Masz już `localDistractors` i `LocalAnswerCheck`. Przełączyć na nie **zawsze**.

- Choice: złożyć 8 opcji z Room (inne karty + `similar_words` w content). Precompute przy `prepareCard` z cache’a, nie z sieci.
- Type: tylko `LocalAnswerCheck`.
- `POST /srs/distractors` i `POST /srs/check-answer` — wyłączyć z klienta albo zostawić jako debug. BE może zostać dla innych klientów.

Przy 10k kart nie ładuj `allCards` do RAMu przy każdej karcie: `SELECT lemmaL2, glossPrimary, pos FROM cached_cards WHERE profileId=? AND id!=? LIMIT 64` + similar z bieżącego contentu.

### Faza E — BE: odchudzić to, co jeszcze wołamy (1–2 dni, niższy priorytet)

Po A–D te endpointy spadają z hot path. Warto je i tak poprawić (inne urządzenie / web później):

- `list_word_lists`: jeden `GROUP BY deck_id` zamiast N+1.
- `dashboard_stats`: jeden SQL z conditional aggregates + jeden forecast (`date_trunc`), nie 7 pętli.
- `list_words` / `list_cards`: parametr `fields=list|full` — lista bez `content`.
- `srs/distractors`: nie `SELECT *` całego profilu.
- Lookup: PG‑first (LexicalEntry / istniejąca karta) zanim LLM — to już było w planie offline jako optymalizacja kosztu; tu dodatkowo latencja search.

### Faza F — Pomiary, żeby nie wrócić do network‑first

- Debug overlay / log: licznik requestów per ekran, czas `Room→first pixel`, czas sync w tle.
- Test instrumentacyjny: airplane mode, asercja 0 wywołań Retrofit na Home/Listy/Practice.
- Test jednostkowy: `buildLocalDashboardStats` vs złoty zestaw kart.
- Zakaz w review: nowy odczyt ekranu nie może wołać `api.*` poza lookup/import/AI.

---

## 7. Kolejność i szacunek

| Faza | Efekt na telefonie | Ryzyko | Szacunek |
|---|---|---|---|
| **A** | Apka przestaje „myśleć” przy każdym tapnięciu | średnie (trzeba nie zepsuć pending inbox / remap ID) | 2–4 dni |
| **B** | 10k kart zostaje płynne | niskie | 1–2 dni |
| **C** | mniej kolizji sync vs UI, mniej full pulli | średnie | 1–2 dni |
| **D** | Ćwicz bez spinnera na choice/type | niskie | 0,5–1 dzień |
| **E** | tańszy BE, gdy ktoś jednak uderzy w API | niskie | 1–2 dni |
| **F** | nie wracamy do status quo | — | w tle przy A |

**Nie zaczynać od E.** Optymalizacja `/stats` przy wciąż wołanym `/stats` z UI to leczenie objawu.

---

## 8. Pliki do zmiany (Faza A — mięso)

**Android — odczyty**

- `data/LearningRepository.kt` — odciąć API od `listWordLists`, `listWords`, `listCards`, `dashboardStats`, `getSettings`, `getActiveProfile`, `listProfiles`, `getQueue`, `getDistractors`, `checkAnswer`.
- `data/AuthRepository.kt` — `ensureActiveProfile` / `hasProfile` z Room.
- `ui/AppViewModel.kt` — splash z cache.
- `ui/home/HomeViewModel.kt` — `refreshAll` / `loadLists` / `loadListWords` / `loadStats` / `selectList` / usunąć polling API.
- `ui/home/HomeScreen.kt` — usunąć 30 s `loadStats`; nie spinnerować gdy są dane.
- `ui/practice/PracticeViewModel.kt` — queue/settings/profile/distractors/check z Room.
- `ui/learning/LearningViewModel.kt` — `listCards` lokalnie, bez poll API.
- `ui/settings/SettingsViewModel.kt`, `ui/profile/ProfileViewModel.kt` — cache first.
- `notifications/EnrichmentCheckWorker.kt` — Room count.

**Android — dashboard lokalny + Room**

- `data/local/OfflineStore.kt` — pełne `buildLocalDashboardStats`, lekkie query.
- `data/local/db/Daos.kt`, `Entities.kt`, `AppDatabase.kt` — indeksy (Faza B), ewentualnie `local_review_log`.
- `data/local/LocalAnswerCheck.kt`, `localDistractors` — jedyna ścieżka (Faza D).

**Android — sieć**

- `di/AppModule.kt` — rozdział timeoutów (albo zostawić, jak A wytnie odczyty).
- `data/sync/SyncWorker.kt` / `SyncScheduler.kt` — jedyny legalny pull.

**Backend — dopiero Faza E**

- `api/v1/learning.py` (`dashboard_stats`, `list_words`, `list_cards`)
- `services/word_lists.py` (N+1)
- `services/distractors.py`

**Nie ruszać w A:** import jobs, lookup LLM, enrichment pipeline, FSRS backend (zostaje źródłem prawdy między urządzeniami przez sync).

---

## 9. Regresja — must‑pass po Fazie A

1. Po syncu: airplane → Home, Listy, Ćwicz, ocena, undo, move, rename listy, ustawienia. Zero requestów. Stan po restarcie ten sam.
2. Online: te same ekrany **nie czekają** na BE. Sync w logcat w tle.
3. Lookup / import / enrichment nadal wymagają sieci; offline search → Oczekujące.
4. Dwie listy, zmiana chipa — karty od razu, bez mignięcia pustki.
5. Pending inbox: stuby + karty serwerowe, licznik = kafelki, flush po online bez duplikatów (istniejący mutex zostaje).
6. Ocena offline → po online SRS zgodny (idempotencja `client_id`).
7. Zmiana pary językowej: overlay busy, potem Room tej pary (pełny pull tej pary w tle, nie na każdym wejściu).
8. Pusty nowy profil: puste stany, nie spinner 8 s.

Scenariusze z `plan-offline-first.md` §9 (R‑A1…R‑A7, R‑B1) nadal obowiązują.

---

## 10. Odpowiedź na „dlaczego to tak chujowo wolno działa”

Nie dlatego, że Compose jest wolny. Nie dlatego, że 10k kart to za dużo. Nie dlatego, że FSRS jest ciężki.

Dlatego, że **architektura UX jest wciąż klientem HTTP z cache’em na czarną godzinę**, a nie lokalną aplikacją ze syncem. Telefon ma dane. Kod woli poczekać, aż Postgres na innym komputerze policzy te same liczby i odeśle te same zdania.

`plan-offline-first.md` zrobił połowę (zapis). Ta połowa, której nie zrobiono (odczyt), jest dokładnie tym, czego używasz co sekundę.

Faza A to nie refaktor „na przyszłość”. To poprawka tego, co teraz widzisz na telefonie.

---

*Podstawa: `LearningRepository`, `OfflineStore`, `Home/Practice/Learning/App ViewModel`, `HomeScreen`, `AppModule` (OkHttp), `VocabularioApi`, `AuthRepository`, `SyncWorker`, `EnrichmentCheckWorker`, `Daos`/`Entities`/`AppDatabase`, `LocalFsrs`, `learning.py` (`dashboard_stats`, `list_words`, `list_cards`, `srs_queue`), `word_lists.py`, `distractors.py`, `sync.py`, `docs/plan-offline-first.md`.*
