# Optymalizacja długich żądań

Dokument roboczy na sesję 7–8 listopada 2026. Zbiera fakty z produkcji, opis tego, co użytkownik czeka, i zamknięte decyzje naprawy. Opis kolejki jest kompletny. Kod ruszamy dopiero na osobne polecenie.

Pomiary pochodzą z produkcji `https://vocabulario.up.railway.app`, bazy Postgres na Railway i logów `app_logs` / `lookup_events` / `llm_usage`. Konto kontrolne: `nowy4@test.com`, włączony profil polski → hiszpański (`pl>es`). Deploy, na którym to mierzono: 2 listopada 2026, commit `33a3b6d` (deploy `6b584601`).

8 listopada 2026 dokument przeszedł weryfikację z kodem backendu i Androida, z produkcją i z gołym API modeli. Poprawki są w tekście, a lista zmian z powodami jest na końcu, w „Rejestrze zmian”. Instrukcje implementacji w kolejności wdrażania są w `docs/taski/`.

## Jak czytać czasy

„Całe żądanie” to jedna wycieczka HTTP. Telefon wysyła słowo, proces API przyjmuje je, wykonuje kod i odsyła JSON. Czas w `app_logs.duration_ms` liczy się w tym procesie, od wejścia w obsługę do chwili, gdy `call_next` odda odpowiedź. Nie wlicza drogi telefonu do Railway ani zapisu samego wiersza logu.

Ten zapis nie dzieje się po odpowiedzi. `AppLogMiddleware` (`backend/app/core/app_log_middleware.py`) czeka na `log_event` i dopiero potem oddaje odpowiedź do Railway. Telefon czeka więc dłużej niż `duration_ms`, o jeden zapis do bazy. Na replice, która dziś obsługuje telefon, to około 0,4 s na każde żądanie (rozdział 0).

Czas widziany przez telefon najlepiej pokazuje log HTTP Railway (`totalDuration` na krawędzi `europe-west4`). Przy `prado` (punkt 1) to 3,46–3,89 s, czyli o 0,4–0,45 s więcej niż `duration_ms` tych samych żądań.

Czas wykonania SQL (`EXPLAIN ANALYZE`) to co innego: praca samej bazy, bez drogi z procesu API do Postgresa. Przy `prado` odczyt wiersza cache trwał w bazie **0,07 ms**, a całe żądanie na serwerze **3,0–3,5 s**.

Z komputera, z którego robione było śledztwo, jedna podróż do tej samej bazy (`SELECT 1` i odczyt wiersza `prado`) trwa około **410 ms**. To droga sieciowa tego komputera, nie czas bazy i nie czas procesu API. Pokazuje rząd wielkości czekania, gdy pytający nie siedzi tuż przy Postgresie.

## Kolejka

| # | Co czeka użytkownik | Stan |
|---|---------------------|------|
| 0 | Każde żądanie: odległość API od bazy, zapisy pomocnicze, pętla `learnable` | opis dodany 8 listopada, implementacja czeka |
| 1 | Szybkie szukanie, gdy odpowiedź jest już zapisana | opis poprawiony 8 listopada, implementacja czeka |
| 2 | Szybkie szukanie, gdy zapisu jeszcze nie ma | opis poprawiony 8 listopada, implementacja czeka |
| 3 | Dociągnięcie pełnej listy propozycji | opis poprawiony 8 listopada, implementacja czeka |
| 4 | Szukanie skojarzeń | opis poprawiony 8 listopada, implementacja czeka |
| 5 | Zapis karty po wybraniu propozycji | opis poprawiony 8 listopada, implementacja czeka |
| 6 | Dociąganie treści karty po zapisie | opis poprawiony 8 listopada, implementacja czeka |
| 7 | Import listy słów | opis poprawiony 8 listopada, implementacja czeka |

Żądanie 1 świadomie nie zmienia szukania bez zapisu, dociągania modelem, kategorii, zapisu karty ani importu.

Kolejność wdrażania nie jest kolejnością numerów. Rozdział 0 idzie pierwszy, bo bez niego żaden pomiar punktów 1–7 nie pokaże efektu zmiany kodu. Pełna kolejność i zależności: `docs/taski/README.md`.

---

## 0. Wspólne przyczyny wolnych żądań

Ten rozdział dodała weryfikacja z 8 listopada 2026. Dotyczy każdego żądania z punktów 1–7.

### Odległość procesu API od bazy

Serwis API `vocabulario` ma dziś dwie repliki: jedną w `europe-west4-drams3a`, drugą w `us-west2` (`multiRegionConfig` w ustawieniach serwisu Railway, nie w `backend/railway.toml`). Postgres stoi w USA, w `sfo`.

Telefon trafia do repliki europejskiej. W logu HTTP Railway z 6–7 listopada 130 ze 141 żądań telefonu obsłużyła instancja `ef650127` za krawędzią `europe-west4`. Pozostałe 11 nie doszło do żadnej repliki.

Jedna podróż z tej repliki do bazy trwa około 141 ms. Widać to w danych produkcji, bez dostępu do kontenera: po każdym wywołaniu modelu kod zapisuje `llm_usage`, robi commit, otwiera drugą sesję i zapisuje `llm_call_payloads`. Między `created_at` tych dwóch wierszy jest na replice europejskiej 430–575 ms (3–4 podróże), na amerykańskiej 10–50 ms.

Każde żądanie robi po kolei kilka do kilkunastu takich podróży. Dlatego:

- `POST /lookup/cached` przy gotowym zapisie trwa 3–3,5 s, choć baza pracuje ułamek milisekundy (punkt 1),
- `GET /cards/{id}` trwa na krawędzi 1,7–2,9 s,
- `GET /cards` ma p50 około 1,3 s (od 3 listopada, wcześniej 0,7 s), a `GET /sync/pull` około 3,2 s,
- typowa karta od wiersza do `ready` potrzebuje 45 s, z czego okno modeli to 24,7 s, a około 19 s to zapisy i odczyty bazy między wywołaniami.

Dwie repliki psują też to, co kod trzyma w pamięci procesu:

- `_inflight` w `lookup_jobs.py` i `lookup_category_jobs.py` łączy tylko żądania w jednym procesie,
- `_claimed` i `_enrich_semaphore()` w `card_jobs.py` (3 karty naraz) działają osobno w każdej replice, więc naraz może iść 6 kart,
- `resume_pending_enrichment` po starcie i watchdog z `start_heartbeat_watchdog` (`stale_only=True`) chodzą w obu replikach. Ta sama karta może być wzbogacana w dwóch procesach naraz, bo nie ma blokady w bazie,
- `resume_unfinished_jobs` importu też startuje w obu.

Decyzja: jedna replika API w regionie bazy. Task `docs/taski/01-region-api-i-bazy.md`.

### Zapisy pomocnicze na ścieżce odpowiedzi

Na każde żądanie przypada jeden zapis `app_logs` przed odpowiedzią (sekcja „Jak czytać czasy”). Przy 141 ms na podróż to około 0,44 s.

Po każdym wywołaniu modelu `_chat_json` czeka na trzy osobne zapisy: `log_event` (`llm_call`), `record_llm_usage` w jednej sesji z commitem i zapis payloadu w drugiej sesji z commitem. To około 1,3 s na wywołanie na replice europejskiej. Karta z czterema wywołaniami traci na tym kilka sekund.

Decyzja: te zapisy idą w tle, poza ścieżką odpowiedzi i poza ścieżką wzbogacania. Błąd zapisu logujemy i nie pokazujemy użytkownikowi. Task `docs/taski/02-zapisy-pomocnicze-w-tle.md`.

### Pętla `learnable`

Siedem kart-zwrotów na koncie kontrolnym (`de repente`, `bola de helado`, `por casualidad`, `a ver`, `a la vez`, `como si no fuera poco`, `at the same time`) nigdy nie dochodzi do `ready`:

1. `inflect_pos_key` dla zwrotu bez rodzajnika zwraca `verb`, więc `content_is_complete` wymaga czasów czasownika (`_has_required_inflection`).
2. Odmiana tych kart ma klucze, ale same `null`. `finish_side_jobs` liczy `has_infl = bool(content.get("inflection") or content.get("conjugation"))`, uznaje odmianę za obecną i modelu nie woła.
3. `_persist_enrichment_result` zapisuje znowu `learnable`, ustawia `enrichment_retry_at` na teraz plus 15 minut, robi commit, loguje `enrich_ready` i woła `notify_cards_ready`.
4. Po 15 minutach watchdog bierze kartę jeszcze raz. Bez końca.

Skutki: około 61 tysięcy zdarzeń `enrich_ready` w 30 dniach, `updated_at` karty rośnie co kwadrans (8 listopada nadal), więc `sync/pull` odsyła je znowu. Przy każdym obrocie `notify_cards_ready` czyta ustawienia i tokeny użytkownika. Samego powiadomienia FCM dziś nie wysyła (`send_push_to_user` tylko loguje zamiar), ale po podłączeniu FCM użytkownik dostawałby „Cards ready” co kwadrans za każdą taką kartę. Telefon trzyma te karty w `EnrichmentStatus.needsPoll` i w `HomeViewModel.startPollingIfNeeded` odpytuje je bez limitu iteracji. To około 1500 `GET /cards/{id}` na kartę tygodniowo. W czasie testu `prado` z punktu 1 telefon co około 7 s pytał równolegle o sześć z tych kart, każde pytanie 1,7–2,9 s. Te pytania szły do tego samego procesu i tej samej puli połączeń co szukanie.

Decyzja: jeden warunek odmiany w obu miejscach, odpowiedź „odmiana nie dotyczy” jako wynik końcowy, limit automatycznych ponowień, bez powiadomienia przy ponowieniu i limit odpytywania na telefonie. Task `docs/taski/03-petla-learnable.md`. Musi wejść przed zmianami odpytywania z punktów 5 i 6.

---

## 1. Szybkie szukanie gotowej odpowiedzi

### Co użytkownik robi

Wpisuje słowo w dodawaniu i czeka na listę propozycji. Jeśli to hasło było już kiedyś dokończone, ma dostać zapisane propozycje i na tym skończyć. Nie ma wołać modelu i nie ma kręcić dalszego czekania.

Słowo próbne: samo `prado`. Zapis dla `pl>es` jest dokończony, ma trzy propozycje (`el prado`, `el derecho`, `la ley`) i był wielokrotnie użyty. `el prado` jest innym hasłem i do tego testu nie służy.

### Jak to działa dzisiaj

Telefon, po zatwierdzeniu słowa, woła `POST /api/v1/lookup/cached`.

Serwer (`LexicalService.lookup_cached`):

1. Ładuje użytkownika z tokenu (`get_current_user`).
2. Ładuje profil.
3. Normalizuje wpis (małe litery, bez znaków diakrytycznych, obcięte do 200 znaków) i szuka jednego wiersza w `lookup_query_cache` po parze języków i tym kluczu.
4. Jeśli wiersz jest i ma propozycje albo flagę „dokończone” (`ai_complete`), podbija licznik użyć i składa odpowiedź w `_present_lookup`. Na tym ta gałąź się kończy. Wikisłownik i modele nie startują.
5. Składanie odpowiedzi układa propozycje w pamięci, dociąga identyfikatory haseł z `lexical_entries` i czyta karty oraz listy użytkownika, żeby dopisać, czy dana propozycja jest już w nauce.
6. Endpoint dopisuje wiersz historii w `lookup_events` i robi commit. Commit niesie też zapis licznika użyć.

Dopiero JSON wraca do telefonu. Telefon (`LookupSession.applyCachedOutcome`) pokazuje propozycje. Gdy flaga „dokończone” jest prawdziwa, nie woła dociągania.

Równolegle `LookupCoordinator.start` zawsze kolejkuje `LookupPollWorker` (`enqueueLookup(replace=true)`). Worker od razu woła to samo szybkie szukanie jeszcze raz. Przy gotowej odpowiedzi ta druga wycieczka nic nie wnosi: ekran i tak kończy po pierwszej. Worker kolejkuje też `AppVisibilityHandler`, gdy aplikacja schodzi w tło w trakcie szukania.

Zapisane propozycje w cache mają `lemma`, `pos` i `gloss`. Kod potrafi zapisać też `reading` i `typed_as` (`_payload_candidate`), ale 8 listopada żaden ze 188 wierszy `lookup_query_cache` ich nie miał. Przy `prado` nie ma w JSON identyfikatora hasła ani informacji o nauce. Jedno i drugie jest dokładane przy każdej odpowiedzi.

### Fakty z produkcji

Test `prado`, 7 listopada 2026, około 09:50 UTC. Pięć żądań `POST /api/v1/lookup/cached`, wszystkie `source=db`, `ai_complete=true`, 3 propozycje. Żadnego wpisu w `llm_usage`.

| Start (z `lookup_events`, czas transakcji) | `duration_ms` | Krawędź Railway (`totalDuration`, status) |
|---|---:|---:|
| 09:50:07.507 | 3019 ms | 3459 ms, 200 |
| 09:50:07.658 | 5020 ms | 5541 ms, 499 |
| 09:50:13.293 | 3058 ms | 3494 ms, 200 |
| 09:50:13.293 | 5090 ms | 3803 ms, 499 |
| 09:50:18.207 | 3455 ms | 3892 ms, 200 |

Widać pary: dwa żądania ruszają razem, jedno wraca po około 3 s, drugie po około 5 s. To ekran i worker. Użytkownik widzi wynik po szybszym z pary, na krawędzi po 3,46–3,89 s. Żądania workera kończą się na krawędzi kodem 499: telefon zamyka połączenie, gdy kolejne szukanie podmienia zadanie (`replace=true`). Serwer i tak liczy je do końca i zapisuje historię, więc każde szukanie kosztuje serwer podwójnie.

W tym samym czasie telefon co około 7 s pytał równolegle o sześć kart z pętli `learnable` (rozdział 0). Każde `GET /cards/{id}` trwało na krawędzi 1,7–2,9 s. Te pytania dzieliły z szukaniem jeden proces i jedną pulę połączeń.

Starsze dokończone trafienia tego samego endpointu, 30 dni do 8 listopada, 31 żądań z historią `source=db` i `ai_complete=true`: typowo 3,8 s, dziewiąty decyl 5,8 s. Trzy sekundy nie są wypadkiem jednego testu.

`EXPLAIN ANALYZE` na produkcji, wykonanie w samej bazie, powtórzone 8 listopada:

| Zapytanie | Czas | Uwaga |
|---|---:|---|
| wiersz cache `pl>es` / `prado` | 0,06 ms | indeks unikalny, 1 wiersz |
| karty tego profilu (492 żywe) | 0,7–2,9 ms | `Bitmap Index Scan` po `uq_learning_cards_live_lemma_pos`, prefiks `(user_id, profile_id)` |
| hasła `lower(lemma)` dla trzech słów | 0,5 ms | skan 715 wierszy `lexical_entries`, 2 trafienia |

Baza nie jest zajęta przez 3 sekundy. Trzy sekundy stoją między tymi krokami: proces API czeka na kolejne podróże do bazy, około 141 ms każda (rozdział 0), a każda czeka na poprzednią. Łańcuch przed odpowiedzią to co najmniej: użytkownik, profil, wiersz cache, hasła leksykalne, karty, listy, drugi odczyt profilu przy historii, zapis historii, commit z licznikiem, a po nim zapis `app_logs` w middleware.

Odczyt kart w `_annotate_candidates` korzysta z indeksu `uq_learning_cards_live_lemma_pos` po pierwszych dwóch kolumnach i bierze same kolumny (`id`, `lemma_l2`, `pos`, `deck_id`, `lexical_entry_id`, `enrichment_status`), bez `content`. Przed nim `ensure_system_list` robi osobny odczyt listy systemowej. Przy 492 wierszach sama baza kończy w milisekundach. Kosztem jest liczba podróży, nie skan.

### Czego nie wolno zmienić

- Para języków zostaje kluczem zapisu. Jedno żądanie i tak niesie identyfikator profilu. Serwer bierze z niego parę i szuka wiersza tylko dla niej.
- Samo trafienie w dokończony zapis nie uruchamia dociągania. Użytkownik może je włączyć ręcznie, napisem „Pokaż więcej propozycji”.
- Niedokończony zapis, który ma już propozycje, wraca od razu i nie uruchamia pełnego szukania. Pod kafelkami jest ten sam napis „Pokaż więcej propozycji”.
- Brak wiersza albo pusty wiersz bez flagi „dokończone” opisuje punkt 2.
- Klucz zostaje dokładnym znormalizowanym wpisem. `prado` i `el prado` pozostają dwoma hasłami.
- Kafelki dalej pokazują hasło, część mowy i tłumaczenie. Po prawej zostaje to, co jest dziś: ikona potwierdzenia z nazwą listy, przycisk dodania albo kółko, gdy karta jeszcze się tworzy.
- Dodanie karty wysyła hasło, część mowy i tłumaczenie z kafelka, czyli tę propozycję, którą widać.
- Historia szukania dalej powstaje, tuż po odpowiedzi. Tworzenie karty umie do niej dowiązać kartę w oknie 15 minut.
- Licznik użyć wiersza cache dalej rośnie po odpowiedzi, przez `hit_count = hit_count + 1`.

### Decyzja

Biznesowo domknięte 7 listopada 2026.

Przy gotowym zapisie telefon dostaje jedno szybkie żądanie. Serwer w jednym odczycie łączy profil z wierszem cache tej pary języków i odsyła zapisane propozycje oraz informację, że wynik jest pełny. Nie czyta kart użytkownika i nie woła modelu. Historię i licznik zapisuje po odesłaniu odpowiedzi.

Telefon, zanim narysuje kafelki, sprawdza wszystkie swoje karty tego profilu, nie tylko otwartą listę:

- słowo jest kartą — ikona potwierdzenia i nazwa listy, a gdy karta jeszcze się tworzy, kółko;
- słowa nie ma — przycisk dodania.

Gdy na tym telefonie nie ma jeszcze kopii kart (świeże wejście, przeinstalowanie, drugi telefon przed synchronizacją), słowo i tak pojawia się od razu. W miejscu przycisku jest kółko, aż pobranie kart się skończy. To kółko nie ma napisu „Tworzę kartę…” i nie uruchamia odpytywania kart. Drugiego szukania do tego nie ma.

Zestawienie musi dawać ten sam wynik co serwer przy 409. Inaczej telefon pokaże przycisk dodania przy słowie, które serwer uzna za duplikat, albo ptaszek przy słowie, które serwer pozwoli dodać.

Pod kafelkami jest napis „Pokaż więcej propozycji”. Dotyczy tego samego napisu, gdy zapis jest pełny, a użytkownikowi brakuje sensu: inna część mowy, inne znaczenie, słowo w języku aplikacji. Kafelki zostają. Serwer pomija skrót „oddaj sam zapis”, prosi model o brakujące odczyty i dopisuje nowe kafelki także do wspólnego zapisu tej pary. Literówka to inne hasło i idzie zwykłym szukaniem, nie tym napisem.

Drugie pytanie z tła przy pełnym zapisie nie startuje.

Czego sama zmiana kroków nie obiecuje: zejścia w dziesiątki milisekund, dopóki telefon obsługuje replika europejska, a każda podróż do bazy w USA trwa około 141 ms. Szybka gałąź to wciąż co najmniej trzy podróże (początek transakcji, zapytanie, koniec) i zapis `app_logs`, czyli około 0,6 s. Dlatego rozdział 0 (jedna replika przy bazie, zapisy w tle) wchodzi przed tą zmianą.

### Instrukcja implementacji

Dotyczy tylko trafienia w istniejący wiersz `lookup_query_cache`. Brak wiersza zostaje przy dzisiejszym kodzie.

#### Serwer: szybka odpowiedź

Pliki: `backend/app/services/lexical.py` (`lookup_cached`), `backend/app/api/v1/learning.py` (endpoint `lookup_cached`), `backend/app/services/lookup_events.py`.

Token sprawdzamy tak jak dziś, ale na tej gałęzi nie ładujemy wiersza `users`. Id użytkownika bierzemy z tokenu. Jedno zapytanie SQL łączy `language_profiles` z `lookup_query_cache`:

- profil o podanym `profile_id` należy do tego użytkownika,
- para języków to `app_lang` i `learning_lang` tego profilu,
- klucz hasła to dotychczasowe `normalize_lookup_query`,
- wiersz cache ma tę parę i ten klucz.

Brak profilu: ten sam błąd 404 co dziś. Brak wiersza cache albo wiersz pusty bez `ai_complete`: wyjście z tej gałęzi do starego `lookup_cached`, bez zmiany zachowania.

`get_current_user` sprawdza dziś tylko, że wiersz `users` istnieje (brak flag blokady). Bez tego odczytu sprawdzenie robi to samo zapytanie: `language_profiles.user_id` ma klucz obcy do `users` z `ON DELETE CASCADE`, więc profil istnieje tylko przy istniejącym użytkowniku. Usunięte konto z ważnym tokenem dostaje 404 zamiast 401. To jedyna różnica i jest akceptowalna.

Zgodność ze starszą wersją telefonu: stary telefon nie zestawia kafelków z Room i bez pól nauki pokazałby przycisk dodania przy słowie, które jest już kartą. Dlatego `LookupRequest` dostaje pole `local_membership: bool = false`. Nowy telefon wysyła `true`. Szybka gałąź bez czytania kart działa tylko przy `true`. Przy `false` odpowiedź dalej idzie przez `_present_lookup`.

Gdy wiersz jest i ma propozycje albo `ai_complete`, odpowiedź idzie natychmiast. Kandydaci mają tylko `lemma`, `pos` i `gloss` z JSON zapisu. `lexical_entry_id`, `in_learning`, `learning_card_id`, `list_id`, `list_name` i `enrichment_status` zostają puste. `source` to `db`. `ai_complete` bierzemy z wiersza. `confident` liczymy tak jak dziś, z hasła i kandydatów, bez dodatkowych zapytań.

W tej sesji nie ma `commit`, nie ma zapisu historii i nie ma zmiany `hit_count`.

Po zbudowaniu odpowiedzi, w osobnej sesji (`async_session_factory`), w tle:

- `UPDATE lookup_query_cache SET hit_count = hit_count + 1, updated_at = now() WHERE id = :id`,
- wstawienie `lookup_events` tymi samymi polami co dziś: hasło, znormalizowany klucz, para, `source=db`, liczba propozycji, `ai_complete`, skrócone propozycje, `request_id`, użytkownik, profil.

Błąd tego zapisu logujemy i nie pokazujemy użytkownikowi.

„W tle” to ten sam mechanizm co w tasku 02: zadanie `asyncio` trzymane w zbiorze silnych referencji, z limitem liczby naraz. Nie `BackgroundTasks` FastAPI: te są związane z cyklem odpowiedzi, a `AppLogMiddleware` jako `BaseHTTPMiddleware` i tak czeka na swój zapis. `asyncio.create_task` dostaje kopię `ContextVar` z chwili utworzenia (`request_id_var`, `user_id_var`, `profile_id_var`, kontekst `llm_usage`), więc zadanie musi powstać, zanim middleware zawoła `clear_request_context`. Dla czytelności `request_id`, użytkownika i profil przekazujemy też jawnie w argumentach.

Dzisiejsze `row.hit_count = row.hit_count + 1` w ORM blokuje wiersz cache do commitu, więc dwa równoczesne szukania tego samego hasła czekają na siebie. Atomowy `UPDATE` w tle tego nie robi.

#### Serwer: „Pokaż więcej propozycji”

To osobne, świadome żądanie. Nie jest częścią szybkiej odpowiedzi.

`LookupRequest` dostaje pole `more: bool = false`. Androidowe `LookupRequest` też. Zwykłe `lookup/cached` i zwykłe `lookup/expand` to pole ignorują.

Nowy przebieg w `lookup_expand`, tylko gdy `more` jest prawdziwe:

- nie wraca wcześniej przy `ai_complete`,
- do modelu idzie lista propozycji już zapisanych (`already`),
- nowe propozycje dopisujemy tą samą funkcją co dziś (`append_lookup_candidates`), starych nie kasujemy,
- wiersz zostaje z `ai_complete = true`,
- odpowiedź niesie pełną, złączoną listę, też tylko z `lemma`, `pos`, `gloss`.

Telefon dokłada ikony tak samo jak przy szybkiej odpowiedzi. Polecenie do modelu i parametry tego pytania są w punkcie 3. Gdy model nie doda żadnego nowego hasła, lista na ekranie się nie zmienia, a pod nią zostaje „Nie ma więcej propozycji.” Napis „Pokaż więcej propozycji” można tapnąć ponownie.

#### Telefon: jedno szybkie pytanie

Pliki: `LookupCoordinator.kt`, `LookupSession`, `BackgroundJobScheduler`, `LookupPollWorker`.

`LookupCoordinator.start` nie kolejkuje workera. Pełne szukanie startuje samo tylko wtedy, gdy pierwsza odpowiedź nie ma żadnej propozycji. Gdy propozycje są, choćby jedna i choćby `ai_complete` było fałszywe, expand sam nie startuje. Wtedy wołamy `cancelLookup`, żeby stare zadanie nie wysłało drugiego `lookup/cached`.

`AppVisibilityHandler` (linia 41) kolejkuje dziś workera, gdy aplikacja schodzi w tło przy trwającym szukaniu. Zostaje tylko dla trwającego pełnego szukania (`lookup/expand`), żeby jego wynik trafił do Room. Worker w tej roli woła wyłącznie `lookup/expand`, nie `lookup/cached`. Expand i tak zapisuje wynik w wierszu cache przed odpowiedzią, więc po powrocie do aplikacji szybkie szukanie oddaje go z punktu 1.

#### Telefon: ikona i przycisk przed narysowaniem

Pliki: `HomeViewModel.applyLookupSession`, `HomeScreen` (`CandidateRow`), Room przez `OfflineStore.allCards` (`cardDao.forProfile`, wszystkie karty profilu, nie `learningCards`).

Zanim kandydaci wejdą w stan ekranu, każdy jest zestawiany z kartą nową funkcją telefonu, która odtwarza serwerowe `select_live_card_for_lemma` (`backend/app/services/word_lists.py`). Istniejące `sameLemmaAndPos` się do tego nie nadaje. Porównuje dokładny tekst lemy bez rodzajnika, więc „el prado” i „prado” się w nim nie schodzą, a nieznana część mowy pasuje do każdej. Serwer robi odwrotnie w obu sprawach. `sameLemmaAndPos` zostaje tylko do łączenia kafelków w `mergeLookupCandidates`.

Reguła nowej funkcji, taka sama jak na serwerze:

- część mowy obu stron przez `normalizePosKey`. Gdy propozycja ma część mowy nieznaną, pasuje tylko karta z nieznaną. W innym razie obie muszą być równe,
- najpierw dokładna lema: przycięta, małe litery, pojedyncze spacje,
- potem klucz kanoniczny jak `canonical_lemma` (`backend/app/core/lemma_keys.py`): NFKC, małe litery, bez nawiasów okrągłych i kwadratowych, interpunkcja zamieniona na spacje, bez `l'` i bez rodzajników z początku, powtarzane do skutku. Przy kilku kartach wygrywa dłuższa lema.

Dzisiejsze `lemmaKey` w `LemmaKeys.kt` zdejmuje tylko jeden rodzajnik i nie usuwa nawiasów ani interpunkcji. Nowy klucz go nie zastępuje w innych miejscach.

Trafienie:

- `learning_card_id`, `in_learning`, `enrichment_status` z karty,
- `list_id` z `deckId`, a gdy karta jest na liście systemowej (`deckId` puste), identyfikator listy systemowej z Room,
- `list_name` z lokalnej listy. Puste `deckId` daje nazwę listy „Uczę się” tak, jak jest zapisana na telefonie.

`CandidateRow` (`HomeScreen.kt`) rysuje dziś trzy stany: ikonę z nazwą listy (`onList`), kółko z napisem „Tworzę kartę…” (`isCreating`, czyli `pending` albo `preparing`) i przycisk dodania. Dochodzi czwarty: „przynależność nieznana”, osobne pole stanu kafelka, nie `enrichment_status`. Rysuje samo kółko, bez napisu, i nie wchodzi do `enrichmentPollCardIds`.

Brak kopii kart rozpoznajemy po `lastPulledAt` tego profilu równym null (jeszcze nie było synchronizacji, pole zapisuje `applyPullLocked` w `OfflineStore`). Wtedy hasło, część mowy i tłumaczenie wchodzą na ekran od razu, a po prawej jest kółko „przynależność nieznana”. Po zakończeniu synchronizacji zestawiamy kafelki jeszcze raz. Drugiego szukania nie ma.

Kafelek dopasowany do karty `learnable` nie może uruchamiać wiecznego odpytywania. `applyLookupSession` woła na końcu `startPollingIfNeeded`, a `EnrichmentStatus.needsPoll` obejmuje `learnable`. Limit odpytywania jest w tasku 03.

Gdy `lastPulledAt` jest ustawione, a kart jest zero albo żadna nie pasuje do hasła, po prawej jest przycisk dodania. To nie jest brak kopii, tylko brak tej karty.

Dodanie karty dalej wysyła `lemma`, `pos` i `gloss` z kafelka. Brak `lexical_entry_id` jest zgodny z dzisiejszą regułą: część mowy i tłumaczenie wystarczą, żeby serwer nie podmienił wybranej propozycji.

#### Telefon: napis pod kafelkami

Klucz `lookup_more_suggestions`. Po polsku: „Pokaż więcej propozycji”. Angielski „Show more suggestions” musi być w domyślnym `values/strings.xml` (dziś angielskim). Bez klucza w `values/` lint zgłasza `MissingDefaultResource`, a język interfejsu bez własnego pliku dostaje `Resources.NotFoundException`. W pozostałych 15 plikach `values-*` (wszystkie mają przetłumaczone `action_add`) klucz dostaje tłumaczenie w tym języku, tak jak dziś reszta napisów. Angielski w nich byłby krokiem wstecz wobec obecnego stanu.

Napis widać pod listą, gdy jest choć jeden kafel. Dotyczy pełnego zapisu i zapisu z jednym słowem z punktu 2. Tapnięcie woła `POST /api/v1/lookup/expand` z `more=true` dla tego samego hasła i profilu. Kafelki, które już są, zostają. Nowe dokładają się przez `mergeLookupCandidates`. W trakcie pod listą jest to samo kółko, którego ekran używa, gdy dociąganie trwa przy już widocznych propozycjach.

#### Baza obok procesu API

Zanim pomiar uznamy za wynik naprawy, sprawdzamy, że task 01 jest wdrożony: jedna replika, w regionie bazy, `DATABASE_URL` na prywatnym adresie Railway. Kontrola bez dostępu do kontenera: przerwa między `llm_usage.created_at` a `llm_call_payloads.created_at` tego samego wywołania poniżej 50 ms, a w logu HTTP Railway jedno `deploymentInstanceId` dla wszystkich żądań telefonu.

### Jak sprawdzimy

Konto `nowy4@test.com`, profil polski → hiszpański, wpisane samo `prado`, karty tego profilu już pobrane na telefon:

- Jedno `POST /api/v1/lookup/cached` w `app_logs`, bez pary z workera. `duration_ms` poniżej 150 ms. Na krawędzi Railway (`totalDuration`) poniżej 600 ms: zostaje droga Europa–Kalifornia, około 150 ms w jedną stronę. Powyżej sekundy wracamy do taska 01.
- Odpowiedź: trzy propozycje, `ai_complete=true`, bez identyfikatorów kart i list.
- Telefon sam nie woła `lookup/expand`.
- Brak nowego wiersza w `llm_usage`.
- W ciągu paru sekund `lookup_events`: `query=prado`, `source=db`, `ai_complete=true`, `candidate_count=3`. `hit_count` wiersza rośnie o 1.
- Na ekranie te same trzy tłumaczenia. Hasło, które jest kartą, ma ikonę i nazwę listy. Hasło, którego nie ma, ma przycisk dodania. Pod spodem widać „Pokaż więcej propozycji”.
- `el prado` nie korzysta z wiersza `prado`.
- Tap „Pokaż więcej propozycji” nie usuwa starych kafelków. Nowe, jeśli model je poda, pojawiają się pod spodem i zostają w tym samym wierszu cache.
- Świeże wejście, zanim synchronizacja zapisze `lastPulledAt`: kafelki słów są od razu, po prawej kółko bez napisu „Tworzę kartę…”, bez `GET /cards/{id}`, a po synchronizacji ikona albo przycisk.
- Zestawienie z Room daje ten sam wynik co serwer: `prado` przy karcie `el prado` (rzeczownik) ma ikonę, a tap dodania przy słowie bez ikony nie kończy się 409. Testy jednostkowe nowej funkcji mają te same przypadki co `select_live_card_for_lemma`: rodzajnik, nawias, część mowy nieznana po jednej i po obu stronach.
- Stary telefon (bez `local_membership`) dostaje kafelki z polami nauki, jak dziś.

---

## 2. Szybkie szukanie, gdy zapisu jeszcze nie ma

### Co użytkownik robi

Wpisuje słowo, którego w `lookup_query_cache` jeszcze nie ma, albo jest tam pusty wiersz bez flagi „dokończone”. Ma dostać pierwsze poprawne słowo mniej więcej po sekundzie. Pełnej listy sam nie czeka. Jak pierwsze słowo mu nie wystarcza, tapnie „Pokaż więcej propozycji”. To tapnięcie jest tym samym pełnym szukaniem co przy gotowym zapisie i opisuje je punkt 3.

### Jak to działa dzisiaj

Ta sama trasa: `POST /api/v1/lookup/cached`. Gałąź w `LexicalService.lookup_cached` po tym, jak wiersz cache nie nadaje się do oddania.

1. Szukanie w `lexical_entries` tej pary (`search_db`, `ILIKE`, limit 10).
2. Gdy nic nie jest pewnym trafieniem, `_fuzzy_l1_db_candidates` ładuje do 800 haseł pary i do 400 kart, żeby złapać literówkę w języku ojczystym.
3. Pewne trafienie zapisuje się z `ai_complete = false` i wraca do telefonu.
4. Brak pewnego trafienia uruchamia wyścig. Wikisłownik i mały model `gpt-5.6-luna` (`lookup_draft`) idą równolegle. Budżet to 3,5 s (`LOOKUP_DRAFT_BUDGET_S`). Wikisłownik ma pierwszeństwo: gdy ma hasła, odpowiedź idzie od razu. Gdy model skończy wcześniej, a słownik jeszcze nie, serwer i tak czeka na słownik do końca budżetu. Gdy słownik jest pusty, do odpowiedzi wchodzi model.
5. Przed JSON-em `_present_lookup` dociąga identyfikatory haseł oraz karty i listy użytkownika. Potem zapis historii i commit.

Telefon (`LookupSession.applyCachedOutcome`) pokazuje propozycje, a gdy `ai_complete` jest fałszywe, sam woła `POST /api/v1/lookup/expand`. Pusty wynik też idzie w to pełne szukanie. W trakcie telefon co 2 s ponawia `lookup/cached`.

Wikisłownik w tym wyścigu to trzy równoległe GET-y składane w `lookup_dictionary_candidates`. Gotowy JSON definicji istnieje tylko na `en.wiktionary.org`. Polski i hiszpański serwer odpowiadają na ten adres kodem 501. Przy polskim interfejsie kod i tak odrzuca angielskie glosy z bloku języka nauki i czeka na sekcję tego języka na Wikisłowniku języka interfejsu. Parser odrzuca część mowy, której nie zna, na przykład „liczebnik”.

Mały model dostaje dziś długi prompt (opis pary, odmiana, tabela, której ta odpowiedź nie niesie) i nie dostaje `reasoning_effort`. Przy rodzinie GPT-5 temperatura nie jest wysyłana: API przyjmuje tylko wartość domyślną 1. Limit to `max_completion_tokens` 1200, a ten limit obejmuje też ukryte myślenie.

### Fakty z produkcji

Ostatnie 90 dni, `POST /api/v1/lookup/cached` połączone z `lookup_events`, z wyłączeniem gotowego zapisu (`source=db` i `ai_complete`):

| Co wróciło | Liczba | Całe żądanie, typowo | Najszybsze | Dziewiąty decyl |
|---|---:|---:|---:|---:|
| `source=db`, pusto, niedokończone | 157 | 6,4 s | 1,0 s | 7,8 s |
| `source=db`, są słowa, niedokończone | 50 | 4,0 s | 1,8 s | 7,9 s |
| `source=dict`, są słowa | 36 | 7,5 s | 3,9 s | 11,3 s |

`source=ai` na tym endpoincie: zero razy w tych 90 dniach. Mały model kończył w budżecie, a do odpowiedzi i tak wchodził Wikisłownik albo nic.

Sam czas modelu, `llm_usage`, cel `lookup_draft`, model `gpt-5.6-luna`: 6 wywołań, od 1,6 s do 2,5 s, typowo 2,2 s. To tylko czekanie na model, bez bazy i bez Wikisłownika.

Osobny pomiar gołych wywołań HTTP, 7 listopada 2026, bez bazy aplikacji. Słowa z języków danej pary: niemiecki `Haus` i `Wasser`, wietnamskie `sách`, włoskie `acqua` i `casa`, portugalskie `livro`, `casa` i `água`, tureckie `kitap`. Pary: niemiecki→wietnamski, włoski→portugalski (Portugalia), portugalski (Brazylia)→turecki.

- Długi prompt i włączone myślenie: około 2–6 s. Portugalskie „casa” na turecki dało ev, hane, konut, yuva.
- Ten sam długi prompt i `reasoning_effort=none`: około 0,8–1,4 s, zero tokenów myślenia. Przy „casa” na turecki zostały słowa podobne brzmieniem (kasa, kas), bez „ev”.
- Krótki prompt po angielsku, ta sama zasada „najpierw tłumaczenie, hasło języka nauki tylko gdy wpis jest dokładnie tym hasłem, bez podobnych brzmień”, `reasoning_effort=none`, limit 400: 9 na 9 poprawnych głównych tłumaczeń, w tym „casa” → „ev”. Czas od 0,9 s do 2,4 s, środek 1,1 s, około 150 tokenów wejścia.
- Ten sam krótki tekst po polsku: 8 na 9, przy „sách” pusta lista, około 210 tokenów wejścia.
- Ten sam krótki tekst w języku interfejsu pary: 9 na 9, około 175–180 tokenów, czas jak angielski.

Obcięcie limitu do 256 przy włączonym myśleniu zjada cały limit na myślenie i zwraca pustkę. Temperatura 0 jest odrzucana.

Weryfikacja 8 listopada 2026, ten sam krótki prompt, luna, `reasoning_effort=none`. Prompt z dokumentu nie mówi nic o rodzajniku. Dzisiejsze polecenia (`LOOKUP_OUTPUT_FORM_RULES` w `backend/app/ai/prompts/v1.py`) wymagają rodzajnika określonego przy rzeczowniku w językach, które go piszą, a `ensure_noun_article` w `sanitize_lookup_candidates` dokleja go tylko przy znanym rodzaju. Propozycja ze szkicu rodzaju nie ma. Bez zdania o rodzajniku kafelek pokazałby `castillo` zamiast `el castillo`, a karta dostałaby lemę bez rodzajnika, inną niż reszta kart.

| Wariant zdania o rodzajniku | `acqua` → portugalski, 4 przebiegi | `łąka` → hiszpański | `Haus` → wietnamski | Czas |
|---|---|---|---|---:|
| brak | bez rodzajnika | bez rodzajnika | `nhà` | 0,8–1,5 s |
| „When L2 writes nouns with a definite article…” | `água` 4 na 4, bez rodzajnika | `el prado` 1 raz, `la pradera` 3 razy | `nhà` 4 na 4 | 0,8–2,3 s |
| ART2 (niżej) | `a água` 4 na 4 | `la pradera` 4 na 4 | `ngôi nhà` 3 na 4, z klasyfikatorem | 0,7–1,1 s |

ART2 jest jedynym wariantem, który trzyma rodzajnik. Klasyfikator wietnamski (`ngôi`, `cái`) zostaje ryzykiem tej jednej pary. Filtra na niego nie dajemy: zdjęcie `cái` albo `con` z początku zepsułoby hasła, w których to słowo jest częścią leksemu (`con` to też „dziecko”).

Pomyłka szkicu trafia do wspólnego wiersza cache tej pary i następna osoba dostaje ją z punktu 1. W jednej z serii 8 listopada wróciło `aqua` zamiast `água`. Pełne szukanie z punktu 3 tej propozycji nie usuwa, bo dostaje ją jako „już pokazane”. To ryzyko jest przyjęte. Wiersz poprawia się ręcznie albo przez dotychczasowe zgłoszenie poprawki.

### Decyzja

Biznesowo domknięte 7 listopada 2026. Zdanie o rodzajniku dodane po weryfikacji 8 listopada.

Z tego zapytania wypada Wikisłownik, wyścig z budżetem 3,5 s i ładowanie do 800 haseł pod literówkę. Wikisłownik zostaje przy sprawdzaniu poprawek (`correction_evidence`). Tu go nie wołamy.

Kolejność:

1. Jedno tanie `search_db` (dotychczasowy `ILIKE`, limit 10). Pewne trafienie zapisujemy z `ai_complete = false` i odsyłamy. Mały model nie startuje.
2. Brak pewnego trafienia: jedno wywołanie `gpt-5.6-luna` bez myślenia, krótkim promptem po angielsku, limitem 400 tokenów.
3. Są propozycje: zapis do `lookup_query_cache` z `ai_complete = false`, odpowiedź tylko z `lemma`, `pos`, `gloss`. Telefon rysuje kafelki i napis „Pokaż więcej propozycji”. Pełnego szukania sam nie woła.
4. Pusto: nic nie zapisujemy jako dokończone. Telefon sam woła pełne szukanie, bo nie ma czego pokazać.

Następna osoba z tą samą parą i tym samym hasłem dostaje zapisane słowo zwykłą szybką ścieżką z punktu 1 i też widzi napis. Mały model drugi raz nie startuje.

### Instrukcja implementacji

Pliki: `backend/app/services/lexical.py` (`lookup_cached`, `_light_draft_candidates`), `backend/app/services/llm.py` (`lookup_draft`, `_chat_json_openai`), `android/.../LookupCoordinator.kt`.

Gałąź gotowego wiersza zostaje przy punkcie 1. Tu wchodzi tylko brak wiersza albo wiersz pusty bez `ai_complete`.

`_fuzzy_l1_db_candidates` na tej gałęzi nie jest wołane. `_dictionary_candidates` i `collect_first_lookup_hits` też nie.

`lookup_draft` dla tego przebiegu:

- model zostaje `llm_light_model` (`gpt-5.6-luna`),
- `reasoning_effort` to `none`,
- `max_completion_tokens` to 400,
- temperatury nie ustawiamy,
- `response_format` zostaje `json_object`.

Prompt systemowy, po angielsku:

```
Dictionary lookup. JSON only. If the query is a real L1 word, the first candidates are its ordinary L2 translations and the gloss is that L1 word. Add an L2 headword only when the query is exactly that headword, ignoring case and diacritics. Do not return a word only because it sounds similar. lemma is the L2 citation form. gloss is the L1 citation form. Noun lemma: in Spanish, French, Italian, Portuguese and German it starts with the singular definite article (el/la, le/la/l', il/lo/la/l', o/a, der/die/das); in other languages it has no article and no classifier.
```

Ostatnie zdanie to ART2. To samo zdanie, dosłownie, dochodzi do promptów systemowych z punktów 3 i 4. Nazwy języków w zdaniu są stałe, bez wstawiania pary, żeby prompt był identyczny dla wszystkich par.

Prompt użytkownika:

```
L1: {native_name}. L2: {learning_name}. Query: "{text}". At most 4 candidates. pos: noun, verb, adj, adv, or other. JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

`{native_name}` i `{learning_name}` to dotychczasowe angielskie nazwy z `lang_name_en`. Długi `language_pair_guidance` do tego przebiegu nie wchodzi.

Odpowiedź do telefonu jest taka sama jak w szybkiej ścieżce punktu 1: bez identyfikatorów kart i list, bez czytania kart użytkownika. `source` przy trafieniu w naszą bazę to `db`, przy modelu `ai`. `ai_complete` jest fałszywe.

Zapis propozycji do `lookup_query_cache` dzieje się w tym żądaniu i jest commitowany przed odpowiedzią. Bez tego następne szukanie i pełne szukanie nie widzą słowa. Historia `lookup_events` i `hit_count = hit_count + 1` idą po odpowiedzi, osobną sesją, tak jak w punkcie 1. Pusta odpowiedź modelu nie tworzy wiersza cache.

Propozycje modelu przechodzą przez dotychczasowe `sanitize_lookup_candidates`, tak jak dziś przez `_raw_to_candidates`. Tam działa `canonicalize_lookup_candidate`, a ono przy znanym rodzaju naprawia rodzajnik.

Dwa równoczesne szukania tego samego nowego hasła na tej samej parze mogą oba zawołać lunę i oba zapisać wynik. Wiersz ma unikalny klucz `(lang_pair, input_norm)`. Zapis idzie dotychczasowym `_merge_into_query_cache`: `INSERT … ON CONFLICT (lang_pair, input_norm) DO NOTHING`, potem `SELECT … FOR UPDATE` i złączenie `append_lookup_candidates` w Pythonie. Drugie żądanie czeka na blokadę wiersza, dokleja swoje propozycje i nie dostaje `IntegrityError`. Złączenia nie da się zrobić w samym `DO UPDATE`, bo `append_lookup_candidates` jest funkcją Pythona.

Sesja żądania nie trzyma połączenia z bazą w czasie wywołania modelu. Po odczycie profilu i wiersza cache jest `commit` (albo `rollback`, gdy nic nie zapisano), a zapis wyniku otwiera nową transakcję. Dziś połączenie z puli jest zajęte przez cały wyścig, do 3,5 s.

Telefon: `applyCachedOutcome` przy niepustych propozycjach publikuje kafelki, ustawia `expanding` na fałsz i kończy szukanie, także gdy `ai_complete` jest fałszywe. Napis „Pokaż więcej propozycji” jest pod kafelkami. Pusta odpowiedź zostawia `expanding` włączone i woła wyłącznie `lookup/expand`. W trakcie tego pełnego szukania telefon nie ponawia `lookup/cached`. Worker też nie.

### Jak sprawdzimy

Nowe hasło, którego nie ma w `lookup_query_cache` dla pary profilu, na przykład portugalski (Brazylia) → turecki i wpis `casa`, oraz niemiecki → wietnamski i wpis `Wasser`:

- Jedno `POST /api/v1/lookup/cached`. Brak wywołań Wikisłownika w logu tego żądania. Jeden wiersz `llm_usage` z `purpose=lookup_draft`, `reasoning_tokens=0`, czas modelu w okolicy 1 s. Całe żądanie poniżej 2 s, gdy API jest przy bazie.
- Odpowiedź ma propozycję, `ai_complete=false`. Dla `casa` pierwsza propozycja to `ev`. Dla `Wasser` to `nước`.
- Rzeczownik w języku z rodzajnikiem ma rodzajnik: polskie `zamek` przy hiszpańskim daje `el castillo` i `la cerradura`, włoskie `acqua` przy portugalskim daje `a água`.
- Dwa równoczesne `lookup/cached` z tym samym nowym hasłem kończą się oba kodem 200, a w `lookup_query_cache` jest jeden wiersz.
- Telefon sam nie woła `lookup/expand`. Pod kafelkami widać „Pokaż więcej propozycji”.
- Drugie wpisanie tego samego hasła na tym samym profilu nie tworzy nowego `lookup_draft`.
- Gdy model odda pustkę, wiersza cache nie ma, a telefon woła `lookup/expand` bez drugiego `lookup/cached`.

---

## 3. Dociągnięcie pełnej listy propozycji

### Co użytkownik robi

Ma już kafelki albo dostał pustkę z punktu 2. Pełna lista ma dopisać brakujące propozycje i zostawić te, które widać. Startuje w dwóch miejscach: tap „Pokaż więcej propozycji”, albo samo, gdy punkt 2 nie oddał żadnego słowa.

### Jak to działa dzisiaj

Telefon woła `POST /api/v1/lookup/expand`. Endpoint nie trzyma pracy w sesji tego żądania. `await_lookup_expand` uruchamia jedno zadanie na użytkownika, profil i znormalizowany tekst. Drugie takie samo żądanie czeka na to zadanie. Zerwanie połączenia go nie przerywa.

Zadanie ładuje użytkownika i profil, potem wiersz `lookup_query_cache`. Gdy `ai_complete` jest prawdziwe, oddaje zapisane propozycje i modelu nie woła. W przeciwnym razie `lookup_expand` woła `gpt-5.6-terra` poleceniem `LOOKUP_EXPAND_PROMPT_V1`: opis pary, odmiana i reguły formy, około 7400 znaków. `reasoning_effort` nie jest ustawione, limitu tokenów też nie. Nowe propozycje doklejają się do starych, wiersz dostaje `ai_complete = true`. Przed JSON-em `_present_lookup` czyta `lexical_entries` oraz karty i listy użytkownika.

Telefon w trakcie co 2 s ponawia `lookup/cached`. `LookupCoordinator.start` potrafi puścić to samo dociąganie jeszcze raz z workera.

Klucz łączenia zadań w `_inflight` (`backend/app/services/lookup_jobs.py`) to krotka użytkownik, profil, znormalizowany tekst. Słownik żyje w pamięci jednego procesu (rozdział 0). Zadanie trzyma swoją sesję bazy, a z nią połączenie z puli, przez całe wywołanie modelu.

### Fakty z produkcji

Ostatnie 90 dni, `POST /api/v1/lookup/expand`: 185 żądań, 1 błąd. Całe żądanie typowo 11,4 s, dziewiąty decyl 20,0 s, najdłużej 32,3 s.

Sam model, `llm_usage`, cel `lookup_expand`, model `gpt-5.6-terra`: 103 wywołania. Typowo 5,7 s, dziewiąty decyl 12,1 s. Wejście typowo 2036 tokenów, myślenie typowo 204 tokeny, treść odpowiedzi typowo 299 tokenów. Na ekran wychodzi zwykle 2 do 4 propozycji. Na 185 żądań HTTP przypada 103 wywołania modelu, bo dwa wywołania potrafią czekać na jedno zadanie.

Od października historia tego pytania ma `source=ai` i `ai_complete=true`. W listopadzie takich jest 10, typowo 10,1 s.

Osobny pomiar gołego wywołania modelu, 7 listopada 2026, bez bazy aplikacji. Polecenie krótkie, po angielsku, `reasoning_effort=none`, limit 500 tokenów. Dwa pełne przejścia po 25 wpisach: 25 na 25 za każdym razem. Środek czasu około 0,9 s, najwolniej 2,2 s. W zestawie były literówki, braki znaków, zapis fonetyczny, liczba mnoga, odmieniony czasownik, frazy i słowo istniejące w obu językach. Ten pomiar był na pustej liście: model nie dostawał słów, które już są na ekranie.

Weryfikacja 8 listopada 2026, z listą „już pokazane”, terra, `reasoning_effort=none`, limit 500:

- Polecenie z dokumentu bez zmian: przy `casa` → turecki i pokazanym już `ev` model dopisał podobne brzmieniem `kasa`, bo polecenie nie mówi, że pusta lista jest dobrą odpowiedzią.
- Z dodanym zdaniem `If no other real reading exists, return an empty candidates list.`: `casa` z `ev`, `prado` z `el prado`, `Wasser` z `nước`, `zlew` z `el fregadero` wróciły z pustą listą, 4 na 4, 0,8–1 s, 11 tokenów odpowiedzi. `pies` z pokazanym `el perro` dało `el pie` = stopa. To prawdziwy drugi odczyt (hiszpańskie `pies` to liczba mnoga od `pie`), zgodny z regułą „oba języki”.
- Bez zdania o rodzajniku rzeczowniki hiszpańskie wracały bez rodzajnika. Ze zdaniem `zamek` dało `el castillo` i `la cerradura`. W szkicu (punkt 2) tylko brzmienie ART2 trzymało rodzajnik we wszystkich przebiegach, więc expand dostaje to samo brzmienie.

### Decyzja

Biznesowo domknięte 7 listopada 2026. Zdania o rodzajniku i o pustej liście dodane po weryfikacji 8 listopada.

To pytanie zostaje przy `gpt-5.6-terra`. Polecenie jest tym krótkim, które przeszło 25 na 25. Myślenie wyłączone. Limit 500 tokenów. Temperatury nie ustawiamy.

Słowa z ekranu idą w poleceniu jako lista „nie powtarzaj”. Nowe doklejają się do starych funkcją `append_lookup_candidates` i do tego samego wiersza `lookup_query_cache`. Wiersz zostaje z `ai_complete = true`. Odpowiedź niesie złączoną listę, tylko `lemma`, `pos`, `gloss`. Kart użytkownika to pytanie nie czyta. Ikona i nazwa listy powstają na telefonie, tym samym zestawieniem co w punkcie 1, także dla słów dopisanych teraz. Słowo, które użytkownik już ma, zostaje na liście: ikona potwierdzenia i nazwa listy. Przycisk dodania jest wtedy, gdy takiej karty na telefonie nie ma.

Telefon wysyła to pytanie raz. Nie ponawia `lookup/cached` w trakcie. Worker też nie.

Gdy model nie doda żadnego nowego hasła, kafelki się nie zmieniają. Pod nimi jest „Nie ma więcej propozycji.” Napis „Pokaż więcej propozycji” zostaje i można go tapnąć ponownie.

### Instrukcja implementacji

Pliki: `backend/app/services/lexical.py` (`lookup_expand`), `backend/app/services/llm.py` (`lookup_expand`), `backend/app/services/lookup_jobs.py`, `android/.../LookupCoordinator.kt`, `HomeViewModel.applyLookupSession`.

`LookupRequest.more = true` przychodzi z tapnięcia „Pokaż więcej propozycji”. Przy `more` zadanie nie wraca wcześniej, nawet gdy `ai_complete` jest prawdziwe. Pusta odpowiedź z punktu 2 woła ten sam przebieg z pustą listą „już pokazane”.

Klucz `_inflight` dostaje `more` jako czwarty element. Bez tego tap „więcej” w chwili, gdy trwa zwykłe dociąganie tego hasła, dołączy do zadania bez `more`, a to zadanie przy `ai_complete` wraca wcześniej i modelu nie woła. Dwa tapnięcia „więcej” jedno po drugim dalej łączą się w jedno zadanie.

Dzisiejszy drugi powrót w `LexicalService.lookup_expand` (po modelu, gdy `row.ai_complete` jest już prawdziwe, bo inne zadanie zdążyło zapisać) przy `more` też nie wraca wcześniej. Wynik modelu dokleja się do wiersza.

Odpowiedź niesie pole `added: int`, liczbę nowych haseł z `append_lookup_candidates` (dziś ten wynik jest odrzucany jako `_added`). Telefon na jego podstawie pokazuje „Nie ma więcej propozycji.” Starsza wersja telefonu to pole ignoruje.

Sesja zadania nie trzyma połączenia w czasie wywołania modelu: odczyt profilu i wiersza, `commit`, model, potem zapis w nowej transakcji z ponownym odczytem wiersza `FOR UPDATE`. Ponowny odczyt jest potrzebny, bo w czasie modelu inne zadanie mogło dopisać propozycje.

Pole `local_membership` działa tak jak w punkcie 1. Przy `true` odpowiedź nie czyta kart i list.

`llm.lookup_expand` dla tego przebiegu:

- model zostaje `llm_lookup_model` (`gpt-5.6-terra`),
- `reasoning_effort` to `none`,
- `max_completion_tokens` to 500,
- temperatury nie ustawiamy,
- `response_format` zostaje `json_object`,
- długi `LOOKUP_EXPAND_PROMPT_V1` i `language_pair_guidance` do tego przebiegu nie wchodzą.

Prompt systemowy:

```
Bilingual dictionary for one language pair. JSON only. lemma is the L2 dictionary headword. gloss is the L1 dictionary form of that same meaning. The query may be L1, L2, or both, and it may contain a missing diacritic, one small typo, a phonetic spelling, or an inflected form. Recover the intended word and return its citation form. An L1 word yields its common L2 translations. An L2 word yields that headword with an L1 gloss. A fixed phrase stays a phrase: do not reduce it to one word inside it. Return the part of speech the query actually is. Once the intended word is clear, do not add a different word that only sounds similar. A plural noun becomes the singular citation of that same noun. A conjugated verb becomes the infinitive. The gloss is that citation too, never the inflected text the user typed. When the same string is a real word in both languages, return both readings. At most 6 rows. Noun lemma: in Spanish, French, Italian, Portuguese and German it starts with the singular definite article (el/la, le/la/l', il/lo/la/l', o/a, der/die/das); in other languages it has no article and no classifier. If no other real reading exists, return an empty candidates list.
```

Prompt użytkownika dokleja słowa już zapisane w wierszu, jeśli są:

```
L1: {native_name}. L2: {learning_name}. Query: "{text}".
Already shown, do not repeat these lemma+pos pairs:
- lemma=...; pos=...; gloss=...
pos is one of noun, verb, adj, adv, prep, conj, pron, det, interj, phrase, particle.
JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

Pusta lista „już pokazane” zamiast tych linii ma zdanie `Nothing shown yet.`

Złączenie i `ai_complete = true` zapisuje zadanie z `lookup_jobs` przed odesłaniem JSON, tak jak dziś, żeby zerwanie połączenia nie zgubiło listy. Historia `lookup_events` zostaje w tym samym commicie. Przy `local_membership=true` `_present_lookup` na tej ścieżce nie czyta kart ani list. W JSON nie ma wtedy `list_name`, `list_id`, `in_learning`, `learning_card_id`, `enrichment_status`.

Telefon: nowe pozycje, zanim wejdą w stan ekranu, przechodzą przez zestawienie z Room opisane w punkcie 1 (`allCards`, nowa funkcja zgodna z `select_live_card_for_lemma`). `mergeLookupCandidates` zostawia ikonę kafelka, który już był na ekranie. W trakcie pod listą jest dotychczasowe kółko dociągania.

Klucz `lookup_no_more_suggestions`. Po polsku: „Nie ma więcej propozycji.” Po angielsku „No more suggestions.” w domyślnym `values/strings.xml`. W pozostałych `values-*` tłumaczenie w tym języku, jak przy `lookup_more_suggestions` w punkcie 1.

### Jak sprawdzimy

Hasło, które punkt 2 oddał jako jedno słowo, na przykład portugalskie `casa` przy nauce tureckiego, kafelek `ev` już na ekranie:

- Tap „Pokaż więcej propozycji” wysyła jedno `POST /api/v1/lookup/expand` z `more=true`. Drugiego z workera nie ma. W trakcie telefon nie woła `lookup/cached`.
- Jeden wiersz `llm_usage`, `purpose=lookup_expand`, model `gpt-5.6-terra`, `reasoning_tokens=0`. Czas modelu w okolicy 1 s.
- `ev` zostaje na ekranie. Nowe słowa, jeśli są, dochodzą pod spodem. W tym samym wierszu `lookup_query_cache` są i stare, i nowe. `ai_complete=true`.
- Słowo, które jest kartą na telefonie, ma ikonę i nazwę listy. Słowo, którego nie ma, ma przycisk dodania.
- Gdy model nie doda nowego hasła, kafelki są te same, odpowiedź ma `added=0`, a pod nimi widać „Nie ma więcej propozycji.” Przy `casa` z samym `ev` model nie dopisuje `kasa`.
- Pusty wynik punktu 2 woła to samo pytanie bez `more` i bez linii „już pokazane”. Literówka z zestawu pomiaru, na przykład `Waser` przy niemiecki→wietnamski, dostaje `nước`.
- Test jednostkowy `lookup_jobs`: zadanie bez `more` w toku i drugie wywołanie z `more=true` dla tego samego hasła tworzą dwa zadania. Dwa wywołania z `more=true` tworzą jedno.

---

## 4. Szukanie skojarzeń

### Co użytkownik robi

Przy polu szukania jest checkbox. Napis zmienia się na „Szukaj skojarzeń”. Wpisuje słowo, nie nazwę działu. `wysyłać`, `łąka`, `Haus`, `kitap` mają dać to słowo w języku nauki i słowa z tej samej codziennej sytuacji.

Słowa z sytuacji są tym, co pełna karta trzyma w `lexical_entries.content` → `associations_l2`. Na produkcji, para `pl>es`, taka lista ma 17–20 pozycji (8 listopada: 87 rzeczowników, 78 czasowników i 61 przymiotników z niepustą listą, typowo 18–19). Na wszystkich 78 czasownikach: 48% rzeczowników, 26% czasowników, 21% przymiotników, 5% przysłówków. Prompt wzbogacania żąda rzeczowników 40–55%, czasowników 20–30%, przymiotników 15–25%, co najmniej 4 czasowników i 3 przymiotników. `enviar` = wysyłać ma tam między innymi `carta`, `paquete`, `sello`, `correo`, `escribir`, `entregar`, `urgente`. `el sonido` = dźwięk ma między innymi `música`, `voz`, `escuchar`, `fuerte`.

Ósemka na tym szukaniu jest krótszym wycinkiem tej siatki: 4 rzeczowniki, 2 czasowniki, 2 przymiotniki. Przysłówka przy ósemce nie ma. Pełna karta nadal dostaje go przy wzbogacaniu.

### Jak to działa dzisiaj

Checkbox ma napis „Szukaj słów dla podanej kategorii” (`search_by_category`). Telefon woła `POST /api/v1/lookup/category/cached`, a potem sam `POST /api/v1/lookup/category/expand`. `CategoryLookupCoordinator.start` puszcza też pracę w tle.

Klucz w `lookup_query_cache` to `cat:` plus znormalizowany wpis (`CATEGORY_QUERY_PREFIX`). Jedno hasło kategorii i to samo hasło jako zwykłe słowo to dwa wiersze. W `candidates` leżą lema, część mowy i glosa. Osobnego wiersza dla każdego słowa z listy nie ma. `associations_l2` na karcie i w `lexical_entries` z tego szukania się nie zapisuje. Tap słowa na karcie otwiera dodanie karty, nie szukanie.

Gdy wiersza `cat:` nie ma, `lookup_category_cached` bierze do 10 haseł z `lexical_entries`. Gdy pewnych trafień jest mniej niż 8 (`LOOKUP_CATEGORY_DRAFT_LIMIT`), mały model `gpt-5.6-luna` dostaje `LOOKUP_CATEGORY_DRAFT_PROMPT_V1` i ma oddać 8 słów jednego tematu. Myślenie jest włączone, limit 1200 tokenów. Zapis idzie z `ai_complete = false`. Potem `lookup_category_expand` woła `gpt-5.6-terra` promptem `LOOKUP_CATEGORY_EXPAND_PROMPT_V1`, żeby dobić zestaw do około 21 (`LOOKUP_CATEGORY_LIMIT` to 24). Przed JSON-em `_present_lookup` czyta karty i listy.

Ostatnie 90 dni:

| Pytanie | n | p50 | p90 | max |
|---|---:|---:|---:|---:|
| `POST /lookup/category/cached` | 102 | 6,7 s | 20,4 s | 25,4 s |
| `POST /lookup/category/expand` | 40 | 13,4 s | 18,1 s | 19,7 s |

Gdy luna naprawdę liczy ósemkę, całe pierwsze pytanie ma p50 18,2 s (n=39, średnio 10 słów; 8 listopada n=43, średnio 9,1). Sam model: n=43, p50 9,0 s, około 780 tokenów polecenia, około 400 tokenów myślenia. Gotowa lista 21 słów z wiersza `cat:` wraca z p50 4,3 s (n=26), bez modelu. Wszystkie pierwsze pytania bez modelu, łącznie z trafieniami z `lexical_entries`: n=59, p50 4,0 s, średnio 15,6 słowa. Te 4 s to w większości podróże do bazy z rozdziału 0. Expand HTTP n=40 przy 21 wywołaniach terry (p50 modelu 8,2 s): ekran i praca w tle czekają na to samo zadanie.

### Co jest wolne

Nowa kategoria pokazuje ósemkę po typowo 18 s, a pełną dwudziestkę jedynkę po kolejnych 13 s. Hasło wpisane po polsku i tak nie zbiera ośmiu hiszpańskich trafień w `lexical_entries`, a to szukanie stoi przed modelem. Myślenie zjada kilka sekund przy obu modelach. Gotowy wiersz i tak czyta karty użytkownika i bywa wołany drugi raz z pracy w tle.

### Decyzja

Biznesowo domknięte 7 listopada 2026.

Checkbox zostaje tym samym przełącznikiem. Polski napis: „Szukaj skojarzeń”. Angielski „Search associations” w domyślnym `values/strings.xml`. W pozostałych `values-*` tłumaczenie w tym języku. Dziś `search_by_category` jest przetłumaczone we wszystkich 16 plikach `values-*`. Wpisanie tam angielskiego zamieniłoby 14 działających tłumaczeń na angielski (poza `values-en` i `values-pl`).

Ścieżka jest dla jednego wpisanego słowa. Dwa pytania idą naraz.

1. Mały model oddaje jedno słowo, język nauki, forma słownikowa. To pierwszy kafelek.
2. Duży model oddaje ósemkę sceny: 4 rzeczowniki, 2 czasowniki, 2 przymiotniki. Dopóki jej nie ma, pod kafelkiem stoi „szukam słów skojarzeń”.

Słowo z pierwszego kafelka, jeśli wróci w ósemce, telefon wyrzuca z ósemki. Porównanie idzie kluczem kanonicznym z punktu 1, bez rodzajnika i bez części mowy: `la pradera` z pierwszego kafelka wyrzuca `pradera` z ósemki. Ósemka może wtedy mieć 7 słów.

Pod listą jest button „szukaj dalszych skojarzeń”. Da się go wcisnąć dwa razy. Każde wciśnięcie dokleja ósemkę o tym samym składzie. Stare kafelki zostają. Po drugim razie zostaje napis „brak dalszych skojarzeń”. Pusta doklejka wstawia ten napis od razu.

Ikona kafelka jest z Room, zestawienie z punktu 1: wszystkie karty profilu, ta sama lema i ta sama część mowy. Ptaszek i nazwa listy, gdy karta jest. Button dodania, gdy jej nie ma. Kółko na kafelku tylko w trakcie tworzenia tej karty albo gdy `lastPulledAt` jest puste.

Słowa z listy trafiają do cache. Zostają w wierszach tego jednego wpisu, w tablicy `candidates`, pola `lemma`, `pos`, `gloss`. Własnego wiersza dla słowa `carta` z listy przy `wysyłać` nie zakładamy. Późniejsze wpisanie `carta` idzie zwykłym szukaniem z punktów 1–3. `associations_l2` na karcie i w `lexical_entries` z tej listy się nie uzupełnia. Tego zapisu nie zmieniamy: i dziś lista kategorii jest jedną tablicą przy kluczu `cat:`, a karta dostaje skojarzenia dopiero przy wzbogacaniu.

Klucz nowego szukania to `assoc:` plus dotychczasowy `_query_cache_key`. Wiersze `cat:` zostają w tabeli i ta ścieżka ich nie czyta. Słowo tematu leży pod `assoc:{klucz}`. Pierwsza ósemka pod `assoc:{klucz}:1`, druga pod `:2`, trzecia pod `:3`. Osobne wiersze, bo oba pierwsze pytania idą naraz i każde zapisuje swój wynik.

Kolumna `lookup_query_cache.input_norm` ma 200 znaków, a `normalize_lookup_query` obcina wpis właśnie do 200. `assoc:` (6 znaków) plus 200 plus `:3` daje 208 i zapis kończy się błędem bazy (500). Dlatego klucz bazowy w `assoc:` obcinamy do 190 znaków, zanim dołożymy przedrostek i rundę. Ten sam błąd ma dziś `cat:` (204 znaki przy wpisie 200-znakowym). Na produkcji najdłuższy klucz ma 28 znaków, więc nikt go jeszcze nie trafił.

Dwie osoby z tą samą parą i tym samym wpisem mogą naraz liczyć tę samą rundę. Wstawienie wiersza idzie przez `INSERT … ON CONFLICT (lang_pair, input_norm) DO NOTHING`, a przegrany odczytuje wiersz zwycięzcy.

Następna osoba z tą samą parą i tym samym wpisem dostaje słowo i pierwszą ósemkę z tych wierszy, bez modelu. Button zostaje. Kolejna ósemka jest brana z wiersza `:2` albo `:3`, gdy już leży. Model startuje tylko dla brakującej rundy. Rundy 4 serwer nie woła.

### Instrukcja implementacji

Pliki: `backend/app/services/lexical.py` (`lookup_category_cached`, `lookup_category_expand`), `backend/app/services/llm.py` (`lookup_category_draft`, `lookup_category_expand`), `backend/app/ai/prompts/v1.py`, `android/.../CategoryLookupCoordinator.kt`, `HomeScreen.kt`, `values-pl/strings.xml` i pozostałe `values-*/strings.xml`, w których jest `search_by_category`.

`lookup_category_cached` na tej ścieżce szuka wiersza `assoc:{klucz}`. Jest: oddaje jego `candidates` i modelu nie woła. Nie ma: jedno wywołanie `gpt-5.6-luna`. `lexical_entries`, Wikisłownik i ładowanie do 800 haseł odpadają. `_present_lookup` kart i list nie czyta.

`lookup_category_draft` dla tego przebiegu:

- model `llm_light_model` (`gpt-5.6-luna`),
- `reasoning_effort` to `none`,
- `max_completion_tokens` to 120,
- temperatury nie ustawiamy,
- `response_format` zostaje `json_object`.

Prompt systemowy:

```
Bilingual dictionary. JSON only. lemma is the L2 citation form and is written in L2, never in L1. gloss is the L1 citation form and is written in L1, never in L2. An L1 query returns its ordinary L2 translation. An L2 query returns that L2 headword. One small typo or a missing diacritic still counts as that word. After the intended word is clear, do not switch to a similar-sounding word. Exactly one candidate. No neighbours. Noun lemma: in Spanish, French, Italian, Portuguese and German it starts with the singular definite article (el/la, le/la/l', il/lo/la/l', o/a, der/die/das); in other languages it has no article and no classifier.
```

Ostatnie zdanie (ART2) dodane po weryfikacji 8 listopada. Bez niego rzeczowniki wracają bez rodzajnika. Z krótszym zdaniem o rodzajniku `łąka` dała `la pradera`, `wysyłać` dało `enviar`, ale `Haus` przy wietnamskim wróciło z klasyfikatorem, `cái nhà`.

Prompt użytkownika:

```
L1: {native_name}. L2: {learning_name}. Query: "{text}". The lemma must be in {learning_name}. The gloss must be in {native_name}. At most 1 candidate. pos: noun, verb, adj, adv, or other. JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

`{native_name}` i `{learning_name}` to `lang_name_en`. Pomiar 7 listopada 2026, gołe API, bez bazy aplikacji: 10 na 10 (`kolory`, `zwierzęta`, `czerwony`, `samochód`, `zwierzenta`, `Farben`, `Waser`, `cucina`, `casa`, `animals`). Po rozgrzaniu 0,7–1,1 s, około 185 tokenów polecenia, około 27 odpowiedzi, zero tokenów myślenia. `casa` przy tureckim wraca jako `ev`, `Waser` jako `nước`, `zwierzenta` jako `animales`.

Wynik ląduje w wierszu `assoc:{klucz}` od razu, przed JSON. Pusty wynik wiersza nie tworzy. `ai_complete` tego wiersza zostaje fałszywe: to jest słowo, nie lista skojarzeń. Telefon i tak nie traktuje fałszywego `ai_complete` jako rozkazu dociągnięcia.

`lookup_category_expand` dostaje w body pole `round`: 1, 2 albo 3. Brak pola znaczy 1. Starszy telefon pola nie wysyła i po `category/cached` sam woła `category/expand`, a wynikiem zastępuje listę (`LookupSession`: `expanded.candidates.ifEmpty { it.candidates }`). Dlatego przy braku pola odpowiedź ma na początku słowo z `assoc:{klucz}`, a za nim ósemkę rundy 1. Nowy telefon wysyła `round` zawsze i dostaje samą ósemkę. Dla `round` czyta wiersz `assoc:{klucz}:{round}`. Wiersz z kandydatami wraca bez modelu. Brak wiersza woła `gpt-5.6-terra`. Już pokazane lemy serwer składa sam: słowo z `assoc:{klucz}` i kandydaci z rund 1…`round-1`. Listy z telefonu nie bierze.

Klucz `_inflight` w `lookup_category_jobs.py` (`_key`) dostaje `round`. Inaczej tap rundy 2 w trakcie rundy 1 dołączy do zadania rundy 1 i dostanie tę samą ósemkę.

Runda 2 wymaga zapisanej rundy 1, a runda 3 rundy 2, bo z nich serwer składa „już pokazane”. Gdy wiersza poprzedniej rundy nie ma (runda 1 jeszcze się liczy albo padła), serwer zwraca 409 `assoc_round_not_ready`, a telefon zostawia button aktywny.

`lookup_category_expand` dla tego przebiegu:

- model `llm_lookup_model` (`gpt-5.6-terra`),
- `reasoning_effort` to `none`,
- `max_completion_tokens` to 400,
- temperatury nie ustawiamy,
- `response_format` zostaje `json_object`,
- długi `LOOKUP_CATEGORY_EXPAND_PROMPT_V1` i `language_pair_guidance` do tego przebiegu nie wchodzą.

Prompt systemowy:

```
Everyday scene around ONE dictionary word. JSON only. lemma is the L2 citation form, written in L2. gloss is the L1 citation form, written in L1. pos is exactly noun, verb, or adj. The query may be L1 or L2, with one small typo or a missing diacritic. Decide the word's most common everyday meaning. Return other words from that broad everyday situation: objects, people, actions, qualities. Not one narrow setting. A different root from the headword. Not the headword. Not a synonym list. Not the other members of a named class: a color is not a list of other colors, an animal is not a list of other animals. Exactly 4 nouns, 2 verbs and 2 adjectives. Common A2-B1 words. Noun lemma: in Spanish, French, Italian, Portuguese and German it starts with the singular definite article (el/la, le/la/l', il/lo/la/l', o/a, der/die/das); in other languages it has no article and no classifier.
```

Ostatnie zdanie (ART2) dodane po weryfikacji 8 listopada. Ze zdaniem o rodzajniku `wysyłać` dało w 1,7 s `el correo`, `la carta`, `el paquete`, `la dirección`, `recibir`, `escribir`, `urgente`, `postal`, nadal 4 + 2 + 2. Bez niego ósemki z tabeli niżej mają rzeczowniki bez rodzajnika.

Prompt użytkownika. Pierwsza runda:

```
L1: {native_name}. L2: {learning_name}. Query: "{text}".
Nothing shown yet.
Exactly 4 nouns, 2 verbs, 2 adjectives. pos is noun, verb, or adj.
JSON: {"candidates":[{"lemma":"...","pos":"...","gloss":"..."}]}
```

Runda 2 i 3 zamiast `Nothing shown yet.` ma:

```
Already shown, do not repeat these lemmas:
- carta
- correo
```

Zapis rundy commituje się przed JSON. `round` większe niż 3 modelu nie woła i zwraca pustych kandydatów. Historia `lookup_events` przy trafieniu w istniejący wiersz idzie po odpowiedzi, tak jak w punkcie 1. Przy świeżym modelu zostaje w commicie zapisu.

Pomiar tej ósemki, 7 listopada 2026, gołe API, terra, bez myślenia, limit 400. Siedem słów, każde 4 + 2 + 2, `pos` równe `noun` / `verb` / `adj`. Czas 1,7–2,7 s, jedno zimne wywołanie 4,5 s, około 240 tokenów polecenia.

| Słowo | Ósemka |
|---|---|
| `wysyłać` | carta, correo, dirección, sello, recibir, escribir, urgente, correcto |
| `dźwięk` | música, teléfono, puerta, voz, escuchar, hablar, alto, silencioso |
| `łąka` | campo, flor, hierba, mariposa, caminar, correr, verde, tranquilo |
| `czerwony` | manzana, semáforo, camiseta, corazón, parar, pintar, maduro, brillante |
| `Haus` → wietnamski | cửa, phòng, gia đình, bếp, ở, dọn dẹp, ấm áp, yên tĩnh |
| `acqua` → portugalski | copo, torneira, garrafa, sede, beber, lavar, frio, limpo |
| `kitap` → turecki | okul, masa, kalem, sayfa, okumak, yazmak, ilginç, eski |

`wysyłać` pokrywa się z produkcyjną kartą `enviar` w pięciu słowach: list, poczta, znaczek, pisać, pilny. Druga runda dla `wysyłać`, `czerwony` i `kitap`, z pierwszą ósemką w poleceniu, dała kolejne 4 + 2 + 2 i zero powtórek. Dla `wysyłać` doszły `paquete`, `oficina`, `mensaje`, `teléfono`, `llamar`, `entregar`, `rápido`, `importante`.

Telefon, `CategoryLookupCoordinator.start`: oba pytania naraz, rundę 1 i słowo. `enqueueLookup` odpada. `LookupPollWorker` tej ścieżki nie powtarza. `applyCachedOutcome` przy tym checkboxie nie woła expand sam z siebie.

Odpowiedź niesie `lemma`, `pos`, `gloss`. Zestawienie z Room jest takie jak w punkcie 1, zanim kafelek wejdzie na ekran.

Nowe klucze napisów: polski w `values-pl`, angielski w domyślnym `values/` i w `values-en`, w pozostałych 14 plikach `values-*` tłumaczenie w tym języku (rozdział o napisach w punkcie 1):

| Klucz | Polski | Angielski |
|---|---|---|
| `search_by_category` | Szukaj skojarzeń | Search associations |
| `lookup_assoc_searching` | szukam słów skojarzeń | searching for associations |
| `lookup_assoc_more` | szukaj dalszych skojarzeń | search for more associations |
| `lookup_assoc_no_more` | brak dalszych skojarzeń | no more associations |

`lookup_assoc_searching` stoi pod pierwszym kafelkiem, dopóki runda 1 nie dojdzie. `lookup_assoc_more` jest buttonem, gdy na ekranie jest runda 1 albo runda 1 i 2, a runda 3 jeszcze nie była proszona. `lookup_assoc_no_more` wchodzi po rundzie 3 albo gdy runda 2 lub 3 wróci bez nowego słowa.

### Jak sprawdzimy

Profil polski → hiszpański, wpis `wysyłać`, checkbox włączony. W `lookup_query_cache` nie ma jeszcze `assoc:` dla tego wpisu.

- Wychodzą dwa pytania: `POST /api/v1/lookup/category/cached` i `POST /api/v1/lookup/category/expand` z `round=1`. Trzeciego z workera nie ma. `lookup/cached` zwykłego szukania nie idzie.
- Jedno `llm_usage` `lookup_category_draft`, model `gpt-5.6-luna`, `reasoning_tokens=0`. Jedno `lookup_category_expand`, model `gpt-5.6-terra`, `reasoning_tokens=0`.
- Pierwszy kafelek to `enviar`. Pod nim ósemka ma 4 rzeczowniki, 2 czasowniki i 2 przymiotniki. Wiersz `assoc:` plus klucz trzyma słowo. Wiersz z przyrostkiem `:1` trzyma ósemkę. Wiersza dla samej lemy `carta` nie ma. `lexical_entries` dla `wysyłać` nie dostaje nowego `associations_l2`.
- Słowo, które jest kartą na telefonie, ma ikonę i nazwę listy. Słowo, którego nie ma, ma przycisk dodania.
- Tap „szukaj dalszych skojarzeń” wysyła expand z `round=2`. Powstaje wiersz `:2`. Stare kafelki zostają, nowe dochodzą, powtórki pierwszej ósemki na liście nie ma. Drugi tap, `round=3`, robi to samo z wierszem `:3` i zostawia „brak dalszych skojarzeń”.
- To samo hasło na drugim koncie tej samej pary bierze słowo i ósemkę z wierszy, bez nowego `llm_usage`. Button nadal odkrywa `:2` i `:3` z tabeli, też bez modelu.
- Rzeczowniki w kafelkach mają rodzajnik (`el correo`, `la carta`).
- Wpis o długości 200 znaków z checkboxem kończy się 200, nie 500, a `input_norm` wierszy ma najwyżej 200 znaków.
- Test serwera: `round=2` przed zapisem rundy 1 daje 409 `assoc_round_not_ready`, a nie ósemkę rundy 1. Równoczesne `round=1` i `round=2` to dwa osobne zadania w `_inflight`.

---

## 5. Zapis karty po wybraniu propozycji

### Co użytkownik robi

Na kafelku propozycji klika dodanie i wybiera listę. Wybór listy jest na telefonie. Po wybraniu listy kafelek od razu dostaje kółko, napis „Tworzę kartę…” i nazwę tej listy. Ptaszek wchodzi, gdy karta ma status `learnable` albo `ready`, tak jak opisuje punkt 6. Sama odpowiedź serwera z `pending` ptaszka nie daje.

### Jak to działa dzisiaj

Zwykła ścieżka, gdy listy są już w pamięci telefonu, to `POST /api/v1/lists/{id}/words`. `POST /api/v1/cards` idzie, gdy listy systemowej w pamięci nie ma. `HomeViewModel.addToList` woła `beginCreating` przed HTTP, potem `LearningRepository.addWordToList`. Oba pytania dostają z kafelka `lemma`, `pos` i `gloss`. `already_resolved` jest wtedy prawdziwe i `best_lookup_candidate` nie startuje.

Serwer, po kolei:

1. Czyta profil i wiersz `word_lists`.
2. `find_card_anywhere` bierze wszystkie żywe `learning_cards` tego profilu, razem z kolumną `content`. `select_live_card_for_lemma` porównuje je w Pythonie: dokładna lema, a gdy jej nie ma, ta sama forma kanoniczna (`el cerrajero` i `cerrajero`). Ta sama lema z inną częścią mowy zostaje osobną kartą. Zgodność daje 409 `word_already_on_list`, a telefon cofa kółko.
3. Wstawia `learning_cards`. Na liście systemowej dokłada `srs_state`. `POST /cards` dopina jeszcze `lookup_event_id` z ostatnich zdarzeń szukania.
4. `hydrate_from_lexical_cache` szuka gotowej treści w `lexical_entries`. Pudło dopisuje `lexical_cache_miss` osobną sesją `log_event`. Trafienie kopiuje treść na kartę, ustawia `enrichment_status` na gotowy i woła `sync_word_family`.
5. `attach_card_to_word_family`. `_seed_family_from_citing_cards` drugi raz czyta wszystkie żywe karty profilu z `content` i patrzy, czy któraś ma to słowo w rodzinie wyrazów.
6. Commit i JSON. Gdy status został `pending`, `spawn_enrich` odpala zadanie w tle i go nie czeka. To zadanie i tak zaczyna od `hydrate_from_lexical_cache` w `_enrich_card_unlocked`.

Telefon zapisuje odesłaną kartę w Room. `markCandidateOnList` przepisuje na kafelek `enrichment_status` z odpowiedzi. Przy trafieniu hydracji to `ready` i kółko zamienia się na ptaszek. Przy pudle to `pending`: `isCreating` w `CandidateRow` dalej rysuje kółko i „Tworzę kartę…”, a ptaszek wchodzi dopiero wtedy, gdy odpytywanie `GET /cards/{id}` przyniesie `learnable`. Treść, której jeszcze nie ma, dociąga punkt 6.

Gdy Room był nieświeży i serwer odda 409, `revertCreating` przywraca przycisk dodania. Kolejny tap znowu kończy się 409, a kafelek nie pokazuje listy, na której karta już jest.

Ostatnie 90 dni. Przy `POST /lists/{id}/words` dwie odpowiedzi były błędami, w tym jeden 409. Udane:

| Pytanie | n | najszybciej | p50 | p90 | max |
|---|---:|---:|---:|---:|---:|
| `POST /lists/{id}/words` | 207 | 2,0 s | 5,9 s | 9,3 s | 21,0 s |
| `POST /cards` | 46 | 2,1 s | 6,2 s | 15,0 s | 18,6 s |

Na tych 253 żądaniach w tym samym `request_id`:

| Wynik | n | p50 | p90 |
|---|---:|---:|---:|
| `lexical_cache_miss` | 231 | 5,9 s | 9,7 s |
| `enrich_cache_hit` | 12 | 14,6 s | 20,2 s |
| bez takiego wpisu | 10 | 6,7 s | 8,0 s |

### Co jest wolne

Model w tym pytaniu nie stoi. Przy pudle `spawn_enrich` startuje po commicie. Odpowiedź i tak czeka typowo 5,9 s, a najkrótsze udane dodanie na listę trwa 2,0 s. W tym czasie serwer dwa razy czyta pełne karty profilu (`find_card_anywhere` i `_seed_family_from_citing_cards`, oba z `content`) i robi kilkanaście podróży do bazy po około 141 ms (rozdział 0). Pudło hydracji dopisuje `lexical_cache_miss` przez `log_event`, czyli jeszcze jeden zapis przed odpowiedzią. Przy trafieniu gotowej treści kopiowanie `lexical_entries` i rodzina wyrazów wchodzą przed JSON, i te 12 żądań trwa typowo 14,6 s.

### Decyzja

Biznesowo domknięte 7 listopada 2026.

To pytanie wstawia kartę i potwierdza ptaszka. Gotowa treść i rodzina wyrazów dochodzą zadaniem w tle, tym samym, które dziś startuje przy `pending`.

`POST /lists/{id}/words` i `POST /cards`:

1. Zostaje sprawdzenie duplikatu. Odczyt bierze `id`, `lemma_l2` i `pos`, bez `content`. Reguła `select_live_card_for_lemma` zostaje. 409 cofa kółko.
2. Wstawia `learning_cards` z `build_pending_content` i `enrichment_status = pending`. Lista systemowa dokłada `srs_state`. `POST /cards` dalej dopina `lookup_event_id`.
3. Commit i odpowiedź: identyfikator, lema, część mowy, glosa, `pending`.
4. `hydrate_from_lexical_cache` i `attach_card_to_word_family` z tego pytania wychodzą.
5. Kafelek miał `lemma`, `pos` i `gloss`, więc `best_lookup_candidate` dalej nie startuje.
6. `spawn_enrich` zostaje po commicie.

`_enrich_card_unlocked` już na początku woła hydrację. Jedno `attach_card_to_word_family` dochodzi w tym zadaniu po hydracji, a gdy hydracja nie znajdzie treści, po zapisie wyniku modelu. Drugi raz, w GET karty, zostaje dotychczasowy `backfill_card_word_family` dla starych kart.

Hydracja w zadaniu w tle nie może czekać w kolejce modeli. Dziś `_run_claimed_enrich` bierze `_enrich_semaphore()` (3 karty naraz) na całe `_enrich_card_unlocked`, razem z hydracją. Przy trzech kartach liczonych modelem gotowa kopia z `lexical_entries` czekałaby za nimi, do 120 s każda. Dlatego hydracja i jej `attach_card_to_word_family` idą przed wejściem do semafora. Semafor obejmuje tylko wywołania modeli.

`attach_card_to_word_family` dostaje dziś `source_card`: kartę, z której użytkownik dodał słowo (`source_card_id` w body, sprawdzane przez `_owned_source_card`). Ta karta też jest zmieniana: dostaje nowe słowo w swojej rodzinie. Zadanie w tle musi znać ten identyfikator. `spawn_enrich` dostaje argument `source_card_id`, a zadanie sprawdza własność karty tak jak `_owned_source_card`. Gdy proces padnie przed zadaniem, wznowienie nie zna już źródła. Wtedy działa dotychczasowe `_seed_family_from_citing_cards`, które szuka kart cytujących to słowo. Rodzina dojdzie, ale karta źródłowa nie dostanie od razu nowego członka. To ryzyko jest przyjęte.

Telefon zostaje przy `beginCreating` przed HTTP. Po odpowiedzi `markCandidateOnList` zapisuje identyfikator karty i `pending`. Kółko i „Tworzę kartę…” zostają do `learnable` (punkt 6). Karty, które dziś trafiały hydrację w tym żądaniu (12 na 253 w 90 dniach), dostaną ptaszek po pierwszym `GET /cards/{id}`, około 2,5 s po odpowiedzi, a nie w niej.

Po 409 telefon nie zostawia samego przycisku dodania. Woła przyrostową synchronizację (`sync/pull` z `since`), zestawia kafelek z Room jeszcze raz i pokazuje ikonę z nazwą listy, na której karta jest.

### Instrukcja implementacji

Pliki: `backend/app/api/v1/learning.py` (`create_card`, `add_word_to_list`), `backend/app/services/word_lists.py` (`find_card_anywhere`), `backend/app/services/card_jobs.py` (`_enrich_card_unlocked`).

`find_card_anywhere` ładuje kolumny `id`, `lemma_l2`, `pos` dla żywych kart użytkownika i profilu. `select_live_card_for_lemma` dostaje te wiersze i działa jak dziś. Inni wołający `find_card_anywhere` (import, `resolve_list_for_card`) potrzebują czasem pełnej karty. Lekki odczyt jest osobną funkcją, a pełną kartę po trafieniu dociąga `db.get(LearningCard, id)`.

Unikalny indeks `uq_learning_cards_live_lemma_pos` (`user_id`, `profile_id`, `lower(lemma_l2)`, `lower(pos)`) zostaje drugą zaporą. Dwa równoczesne dodania tej samej lemy dają jeden wiersz i jedno 409 z `IntegrityError`, tak jak dziś.

W `create_card` i `add_word_to_list` po `flush` wstawionej karty nie ma `hydrate_from_lexical_cache` ani `attach_card_to_word_family`. Jest commit, `refresh` i przy `pending` dotychczasowe `spawn_enrich`.

W `_enrich_card_unlocked`:

- hydracja przed semaforem, w `_run_claimed_enrich` albo na początku zadania, zanim zadanie weźmie `_enrich_semaphore()`,
- trafienie hydracji: commit treści, potem `attach_card_to_word_family(source_card=…)`, potem dotychczasowe `notify_cards_ready`,
- pudło i późniejszy zapis wyniku modelu: `attach_card_to_word_family` raz, po zapisie treści, zanim zadanie się kończy,
- `lexical_cache_miss` loguje się w tle (task 02).

Odpowiedź HTTP niesie szkic z `build_pending_content`. Pełnego `content` z `lexical_entries` w tym JSON nie ma.

### Jak sprawdzimy

Profil polski → hiszpański, kafelek `enviar` (czasownik) z glosą, dodanie na listę nauka. Tej karty jeszcze nie ma.

- Jedno `POST /api/v1/lists/{id}/words`. W tym `request_id` nie ma `lexical_cache_miss`, `enrich_cache_hit` ani wiersza `llm_usage`.
- Odpowiedź ma `enrichment_status = pending` i identyfikator karty. W `learning_cards` jest ten wiersz, na liście systemowej jest `srs_state`. `content` to szkic: lema, część mowy, glosa, puste skojarzenia.
- Kafelek ma nazwę listy, kółko i „Tworzę kartę…”. Kółko schodzi, a ptaszek wchodzi przy `learnable`.
- Czas odpowiedzi na krawędzi Railway poniżej 600 ms po tasku 01.
- Drugie dodanie tego samego `enviar` jako czasownika daje 409. Kafelek po synchronizacji pokazuje ikonę i nazwę listy, a nie przycisk dodania.
- Dodanie słowa, które jest już w `lexical_entries`, gdy trzy inne karty liczą się modelem: karta jest `ready` w ciągu kilku sekund, nie czeka na semafor.
- Dodanie słowa z sekcji rodziny innej karty (`source_card_id`): po zadaniu w tle karta źródłowa ma nowe słowo w rodzinie.
- Ta sama lema z inną częścią mowy przechodzi i jest osobną kartą (test serwera: `enviar` z `pos=noun` przy zapisanym czasowniku). Lema z rodzajnikiem przy karcie bez niego (`el prado` przy `prado`, ta sama część mowy) daje 409.
- Treść z `lexical_entries` albo z modelu oraz rodzina wyrazów pojawiają się po tym żądaniu, w zadaniu w tle. Samo pojawienie się treści sprawdza punkt 6.

---

## 6. Dociąganie treści karty po zapisie

Schemat czasów: `docs/wzbogacanie-karty-schemat.md`.

### Co użytkownik robi

Po zapisie karty otwiera ją albo zostaje przy wyniku szukania. Ma widzieć hasło, tłumaczenie wybrane z listy i nazwę listy od razu. Ćwiczenie na fiszce zaczyna się, gdy są znaczenia, zdania i zwroty. Synonimy, przeciwieństwa, rodzina, skojarzenia, słowa podobne i odmiana dochodzą w swoich sekcjach. Pusta sekcja, która jeszcze powstaje, ma kółko. Kółko znika, gdy treść tej sekcji jest już w karcie.

### Jak to działa dzisiaj

Po `pending` startuje `spawn_enrich`. Zadanie w `_enrich_card_unlocked` najpierw woła `hydrate_from_lexical_cache`. Trafienie kopiuje treść z `lexical_entries` i ustawia `ready`. Pudło woła `run_lemma_enrichment`.

Trzy wywołania idą naraz:

1. Rdzeń `enrich_core` na `gpt-5.6-terra`. Długie polskie polecenie `ENRICHMENT_CORE_STATIC_V1`, z opisem pary i rodziny. Myślenie włączone. Z rdzenia są znaczenia, zdania, zwroty, synonimy, przeciwieństwa, rodzina i skojarzenia.
2. `similar_words` na `gpt-5.6-luna`.
3. `inflection` na `gpt-5.6-terra`.

Przed złożeniem karty `fill_related_articles_on_core` sprawdza, czy rzeczowniki w synonimach, przeciwieństwach, rodzinie i skojarzeniach mają rodzajnik. Gdy nie mają, woła lunę (`purpose=article_repair`). Potem `assemble_core_card` składa kartę: pilnuje hasła (`prefer_citation_headword`), normalizuje zwroty, tnie znaczenia do `MAX_MEANINGS`, filtruje rodzinę i skojarzenia względem synonimów, a `ui_hints` uzupełnia z manifestu języka (`script`, `rtl`, `inflection_kind`, `show_conjugation`). Z rdzenia bierze też `headword_note`, `language_specific`, `notes` i `confidence`.

Status `learnable` zapisuje się po całym rdzeniu, w `on_core`, po `sync_word_family`. Telefon dostaje wtedy także synonimy, rodzinę i skojarzenia. `ready` jest po słowach podobnych, odmianie i zapisie kopii do `lexical_entries`.

`ready` daje `content_is_complete` (`card_jobs.py`): treść do nauki, wymagana odmiana (`_has_required_inflection`) i co najmniej 7 słów podobnych (`MIN_SIMILAR_FOR_QUIZ`). 12 (`MIN_SIMILAR_WORDS`) to cel, o który `finish_side_jobs` prosi model. Powiązanych ta funkcja nie sprawdza: dziś przychodzą w tym samym JSON co znaczenia, więc zawsze są.

Gdy po rdzeniu lema albo część mowy zmieni się względem wpisu (`side_jobs_need_retry`), słowa podobne i odmiana startują drugi raz, z nową lemą.

Telefon po zapisie woła `GET /api/v1/cards/{id}` i powtarza co 2,5 s, dopóki status jest `pending`, `preparing` albo `learnable` (`EnrichmentStatus.needsPoll`). W `HomeViewModel.startPollingIfNeeded` ta pętla nie ma limitu, a `LearningViewModel` kończy po 20 obrotach co 3 s. Karta, która zostaje `learnable` na zawsze (rozdział 0), jest odpytywana bez końca. Kółko na kafelku wyniku (`isCreating`) stoi przy `pending` i `preparing`. Napis przy kafelku: „Tworzę kartę…”.

`GET /cards/{id}` przy statusie `pending` sam woła `spawn_enrich`, przy `preparing` po terminie też, a przy `learnable` i `ready` za każdym razem woła `backfill_card_word_family`.

Ostatnie 90 dni, same wywołania modelu:

| Pytanie | Model | n | p50 | p90 |
|---|---|---:|---:|---:|
| `enrich_core` | terra | 590 | 23,7 s | 35,0 s |
| `similar_words` | luna | 633 | 7,6 s | 12,3 s |
| `inflection` | terra | 617 | 4,4 s | 19,8 s |

Rdzeń: około 3800 tokenów polecenia, około 820 tokenów myślenia, około 2400 tokenów odpowiedzi. Osobne `examples` było 2 razy, `article_repair` 4 razy.

Dla kart dopisanych przy dodaniu słowa, które doszły do `ready` w ciągu 3 minut (102 karty), od wiersza `learning_cards` do `ready` mija typowo 43 s, najszybciej 20 s. 8 listopada, to samo okno 90 dni: 130 kart, typowo 43 s, najszybciej 16 s. Z tych 43 s okno modeli to około 24,7 s, reszta to zapisy i odczyty bazy (rozdział 0). Odczyt `GET /cards/{id}`: 49 395 razy, typowo 0,8 s. Dużą część tych odczytów robią karty z pętli `learnable`, około 1500 na kartę tygodniowo.

Osiem kart z 6 i 7 listopada, para `pl>es`, ma jedno albo dwa znaczenia, przy każdym trzy zdania A2, B2 i C2 oraz zwroty, synonimy tej samej części mowy, rodzinę od tego samego rdzenia, 17–19 skojarzeń i osobno dwanaście słów podobnych oraz odmianę.

### Co jest wolne

Do ćwiczenia telefon czeka na cały rdzeń, typowo 24 s, choć fiszce wystarczą znaczenia, zdania i zwroty. Synonimy, przeciwieństwa, rodzina i skojarzenia siedzą w tym samym JSON-ie i w tych samych tokenach odpowiedzi. Słowa podobne i odmiana i tak lecą obok i przy rdzeniu 24-sekundowym zwykle kończą się wcześniej. Na ekranie przez ten czas jest jedno kółko i napis „Tworzę kartę…”.

### Decyzja

Biznesowo domknięte 8 listopada 2026.

Jakość układu karty zostaje. Model rdzenia zostaje `gpt-5.6-terra`. Długie polskie polecenie i myślenie schodzą.

Rdzeń dzieli się na dwa pytania, oba startują zaraz po wierszu karty i nie czekają na siebie. Trzecie i czwarte to dotychczasowe słowa podobne i odmiana.

1. Nauka: znaczenia, po trzy zdania A2, B2 i C2, zwroty (`usages`), IPA. Po zapisie tej części status jest `learnable`. Da się ćwiczyć.
2. Powiązane: synonimy, przeciwieństwa, rodzina, skojarzenia.
3. `similar_words` na lunie, bez zmiany polecenia.
4. `inflection` na terrze, bez zmiany polecenia.

`ready` jest, gdy są nauka, powiązane, słowa podobne, wymagana odmiana i kopia w `lexical_entries`. `attach_card_to_word_family` jest po powiązanych, przed `ready`, i nie wstrzymuje `learnable`.

Po podziale powiązane mogą nie dojść (błąd, przekroczony czas), a nauka, słowa podobne i odmiana tak. Dzisiejsze `content_is_complete` uznałoby taką kartę za pełną i zapisało ją do `lexical_entries`. Następni użytkownicy tej pary dostaliby przez hydrację kartę bez synonimów, rodziny i skojarzeń. Dlatego karta po zapisie nauki dostaje w `content` znacznik `related_pending: true`, a `content_is_complete` wymaga, żeby go nie było. Zapis powiązanych go zdejmuje. Stare treści tego klucza nie mają i dalej są pełne.

Sprawdzenie rodzajników (`fill_related_articles_on_core`) i filtry rodziny oraz skojarzeń przechodzą z rdzenia do powiązanych. Poprawki hasła, zwrotów i znaczeń z `assemble_core_card` zostają przy nauce. `assemble_core_card` dzieli się na dwie funkcje, jedną dla każdej części.

`headword_note` (na przykład „(e>ie)” przy czasowniku z oboczną samogłoską) telefon pokazuje pod hasłem w `CardDetailContent.kt` i `FlashcardBackContent.kt`. Polecenie nauki z pomiaru tego pola nie ma, więc nowe karty straciłyby widoczną notkę. Polecenie nauki dostaje pole `headword_note` (krótkie, albo null). `ui_hints` składa kod z manifestu, jak dziś. Pola z rdzenia, których dziś telefon nie pokazuje (`conjugation_kind`, `has_articles`, `has_cases`, `has_gender` w `ui_hints`, `language_specific`, `notes`, `confidence`), w nowych kartach są puste. `notes` czyta tylko `card_corrections` przy porównaniu poprawki. Puste pole tego nie psuje.

Gdy nauka zmieni lemę albo część mowy (`side_jobs_need_retry`), słowa podobne, odmiana i powiązane startują drugi raz, z nową lemą. Dziś dotyczy to dwóch pierwszych.

Polecenie powiązanych z pomiaru 8 listopada, w brzmieniu z tego dokumentu, zostawia część rzeczowników bez rodzajnika i przy haśle bez prawdziwego synonimu dopisuje sztuczne pozycje (przy `el millón` samo hasło z innym rodzajnikiem albo liczbę). Dzisiejszy rdzeń zapisuje pozycje powiązane jako `{lemma bez rodzajnika, pos, article, gloss_l1}` i tak je normalizuje `_normalize_related_words` (`backend/app/services/enrichment.py`). Na końcu `drop_related_missing_articles` wyrzuca rzeczownik bez rodzajnika w języku z rodzajnikami, więc każdy brak rodzajnika to jedno skojarzenie albo synonim mniej na karcie. Polecenie powiązanych przechodzi na ten format i dostaje zdanie, że pusta lista jest dobrą odpowiedzią (wariant REL2 w instrukcji).

Trafienie `hydrate_from_lexical_cache` dalej kopiuje gotową kartę i ustawia `ready` bez tych czterech pytań.

Na ekranie od zera widać hasło, wybrane tłumaczenie i nazwę listy. Sekcja bez treści ma kółko, dopóki status nie jest `ready`. Przy `ready` pusta lista zostaje pusta. Tak jest przy haśle bez przeciwieństwa, na przykład przy „milion” z próbki z 6 listopada. Kółko na kafelku wyniku schodzi przy `learnable`, tak jak dziś schodzi `isCreating`. Pętla `GET /cards/{id}` co 2,5 s zostaje do `ready`, ale z limitem z taska 03: karta `learnable` wypada z odpytywania, gdy serwer odda `enrichment_active=false` (żadne zadanie tej karty nie trwa), a najpóźniej po 3 minutach od pierwszego odpytania w tej sesji ekranu. `CardResponse` nie ma `updated_at`, więc telefon nie może sam rozpoznać, że nic się nie zmienia. Sekcje z kółkiem pokazują wtedy pustą listę bez kółka, a następna synchronizacja przyniesie resztę.

Pomiar 8 listopada 2026, gołe API, terra, `reasoning_effort=none`. Para polski–hiszpański.

Część do nauki, z poleceniem „każde częste znaczenie”:

| Hasło | Czas | Znaczenia |
|---|---:|---|
| `publicar` | 5,3 s | publikować; ogłaszać |
| `frontera` | 5,1 s | granica państwa; granica między dziedzinami, hasło `la frontera` |

W tej samej serii, zanim doszło zdanie o każdym częstym znaczeniu: `encargado` 4,5 s (jedno znaczenie, jak karta z 6 listopada), `tremendo` 5,3 s (dwa znaczenia). Wejście około 310 tokenów, odpowiedź 230–510. Każde znaczenie miało trzy zdania A2, B2, C2 i co najmniej dwa zwroty.

Część powiązana, ten sam pomiar: 4,4–5,3 s, wejście około 275 tokenów, odpowiedź 450–570. 17 albo 18 skojarzeń, co najmniej 4 czasowniki i 3 przymiotniki, oraz synonimy, przeciwieństwa i rodzina.

Weryfikacja 8 listopada, terra, `reasoning_effort=none`:

- Nauka, pięć haseł (`publicar`, `frontera`, `banco`, `millón`, `de repente`): 2,9–5,7 s. Każde znaczenie miało trzy zdania A2, B2, C2 i zwroty. Rzeczowniki wróciły z rodzajnikiem w lemie.
- Powiązane w formacie REL2 (niżej), cztery hasła (`publicar`, `la frontera`, `el millón`, `el banco`), dwie serie: 3,2–5,7 s, 480–615 tokenów odpowiedzi. Wszystkie rzeczowniki w skojarzeniach miały pole `article` (10 na 10, 10 na 10, 8 na 8, 8 na 8). 17–18 skojarzeń, 4–5 czasowników, 3–4 przymiotniki, 1 przysłówek. `el millón` dostał puste synonimy i przeciwieństwa, a `publicar` puste przeciwieństwa. Tak ma być.

### Instrukcja implementacji

Pliki: `backend/app/lsp/enrichment.py` (`run_lemma_enrichment`), `backend/app/services/llm.py`, `backend/app/ai/prompts/v1.py`, `backend/app/services/card_jobs.py` (`_enrich_card_unlocked`), ekran karty w `CardDetailContent.kt` i `FlashcardBackContent.kt`.

Cztery zadania startują razem. Nauka i powiązane: model `llm_lookup_model`, `reasoning_effort=none`, `max_completion_tokens` 2200, bez temperatury, `response_format` `json_object`. `{native_name}` i `{learning_name}` to `lang_name_en`.

Polecenie systemowe nauki, `purpose=enrich_study`:

```
You write the study part of one flashcard. JSON only. lemma is the same L2 headword. When this L2 writes a noun with a dictionary article, the lemma includes that article even if the input omitted it. Do not translate the lemma into L1. gloss_l1, example l1 and usage l1 are L1. Example l2 and usage l2 are L2. Meanings in frequency order. Include every common everyday meaning. The gloss hint is the first meaning, not a reason to drop another common one. Each meaning has exactly 3 full sentences: A2 short, B2 complex, C2 idiomatic. No repeated l2 sentence. Each meaning has 2 or 3 short usages: a collocation or fixed phrase in L2 with an L1 translation. ipa transcribes the word itself, without the article. No synonyms, antonyms, word family, associations, conjugation, or similar words.
```

Polecenie użytkownika nauki:

```
L1: {native_name}. L2: {learning_name}. Lemma: {lemma}. POS: {pos}. Gloss hint: {gloss}.
JSON: {"lemma":"...","pos":"{pos}","ipa":"...","headword_note":null,"meanings":[{"gloss_l1":"...","examples":[{"l2":"...","l1":"...","cefr":"A2"},{"l2":"...","l1":"...","cefr":"B2"},{"l2":"...","l1":"...","cefr":"C2"}],"usages":[{"l2":"...","l1":"..."}]}]}
```

Do polecenia systemowego nauki dochodzi na końcu zdanie: `headword_note is a short grammar note shown next to the headword, such as a stem change "(e>ie)" or an irregular plural, otherwise null.` To pole nie było w pomiarze. Sprawdzenie jest w tasku 10.

Polecenie systemowe powiązanych, `purpose=enrich_related`, wariant REL2 z weryfikacji 8 listopada:

```
You add related words to one flashcard whose meanings already exist. JSON only. Every item is {lemma, pos, article, gloss_l1}. lemma is the L2 citation form without any article. article is the singular definite article of a noun in Spanish, French, Italian, Portuguese or German, otherwise null; never guess it. pos is exactly noun, verb, adj, adv, or phrase. gloss_l1 is L1. synonyms_l2 and antonyms_l2 match the headword POS and are real single words or fixed phrases, never the headword with an article or a number. An empty list is correct when no real synonym or antonym exists. Do not repeat the headword. word_family_l2 is same-root derivation only, other POS allowed, never a negative prefix, never the headword. associations_l2 is one everyday scene of the gloss hint, 16 to 18 items, other roots: about half nouns, at least 4 verbs, at least 3 adjectives, one adverb if it fits. Not synonyms and not the word family.
```

Polecenie użytkownika powiązanych:

```
L1: {native_name}. L2: {learning_name}. Lemma: {lemma}. POS: {pos}. Gloss hint: {gloss}.
JSON: {"synonyms_l2":[{"lemma":"...","pos":"{pos}","article":null,"gloss_l1":"..."}],"antonyms_l2":[],"word_family_l2":[],"associations_l2":[]}
```

Pozycje przechodzą przez `_normalize_related_words`, `filter_word_family` i `filter_associations`, jak dziś pozycje z rdzenia. `fill_related_articles_on_core` dostaje tylko część powiązaną i woła lunę wyłącznie wtedy, gdy rzeczownikowi w języku z rodzajnikami brakuje pola `article`.

Gdy nauka wróci, zadanie zapisuje znaczenia, zdania, zwroty, IPA i `headword_note`, ustawia `learnable` i `related_pending: true`, robi commit i woła `notify_cards_ready`. Powiązane, które wróciły wcześniej, dochowuje w pamięci i dokleja w tym samym zapisie, bez `related_pending`. `attach_card_to_word_family` i zapis do `lexical_entries` czekają, aż są nauka, powiązane, słowa podobne i odmiana. Dopiero wtedy status jest `ready`.

Gdy powiązane wrócą po `learnable`, zadanie dokleja je do karty, zdejmuje `related_pending` i robi commit bez czekania na słowa podobne i odmianę. Status zostaje `learnable`, dopóki brakuje słów podobnych albo wymaganej odmiany.

Gdy powiązane padną, a reszta jest, karta zostaje `learnable` z `related_pending` i wchodzi w ponowienie z taska 03 (`enrichment_retry_at`). Ponowienie woła tylko brakującą część. Do `lexical_entries` taka karta nie trafia.

Zapis karty w tym zadaniu idzie zawsze przez ponowny odczyt wiersza `learning_cards` w tej samej sesji. Nauka i powiązane mogą wrócić w dowolnej kolejności, a każdy zapis dokleja swoją część do aktualnego `content`, nie do kopii sprzed wywołań.

Każde z czterech wywołań kończy się po wpisie `llm_usage`, ale ten wpis idzie w tle (task 02). Zapis treści na kartę nie czeka na metrykę.

`similar_words` i `inflection` zostają przy dotychczasowych poleceniach i modelach.

Ekran karty: sekcje synonimów, przeciwieństw, rodziny, skojarzeń, słów podobnych i odmiany przy statusie `pending`, `preparing` albo `learnable` i pustej liście pokazują kółko. Przy `ready` pusta lista jest pusta. Znaczenia i zdania przy `pending` mają kółko. Po `learnable` są treścią do fiszki.

### Jak sprawdzimy

Profil polski → hiszpański, nowe hasło `publicar`, tłumaczenie „publikować”, brak wiersza w `lexical_entries`.

- Po zapisie wiersza w `llm_usage` są cztery wywołania: `enrich_study` i `enrich_related` na terra, `reasoning_tokens=0`, oraz `similar_words` na lunie i `inflection` na terra.
- `enrich_study` kończy się w okolicy 5 s. W karcie są dwa znaczenia, przy każdym trzy zdania A2, B2, C2 i zwroty. Status `learnable`. Fiszka tego hasła startuje.
- `enrich_related` dokleja synonimy, przeciwieństwa, rodzinę i 16–18 skojarzeń. Kółka tych sekcji schodzą przy najbliższym `GET /cards/{id}`, który ma te listy.
- Po słowach podobnych, odmianie i kopii w `lexical_entries` status jest `ready`. Drugie dodanie `publicar` jako czasownika bierze tę kopię przez hydrację i nie woła tych czterech pytań.
- Hasło z karty z 6 listopada, które nie ma przeciwieństwa (`el millón`), przy `ready` pokazuje pustą sekcję przeciwieństw, bez kółka.
- Czasownik z oboczną samogłoską (`pensar`, `volver`) ma `headword_note` pod hasłem, jak karty sprzed zmiany.
- Rzeczowniki w skojarzeniach mają rodzajnik, a liczba skojarzeń po `drop_related_missing_articles` jest 16–18.
- Wymuszony błąd `enrich_related` (test): karta zostaje `learnable` z `related_pending`, nie trafia do `lexical_entries`, a ponowienie woła tylko `enrich_related`.

---

## 7. Import listy słów

### Co użytkownik robi

W zakładce Dodaj są dwie zakładki: „Szukaj” i „Import”. Po wejściu otwarta jest „Szukaj”. Import nie zasłania szukania.

W „Import” jest przycisk „Importuj”. Otwiera dotychczasowe okno: wklejenie tekstu albo plik oraz wybór listy docelowej, z możliwością nowej listy. Przycisk jest wyłączony, gdy na tym profilu trwa import albo gdy dzienny limit kart jest wykorzystany.

Po starcie przycisk zostaje wyłączony. Pod nim jest kółko i napis „Trwa analiza słów”. Po analizie, w tej samej zakładce:

1. Sekcja „Błędy”: słowo i powód odrzucenia.
2. Sekcja „Duplikaty”: słowo i nazwa listy, na której karta już jest. Powtórzenie w tym samym pliku zostaje przy dotychczasowym powodzie „To samo hasło powtórzyło się w tym imporcie.”
3. Kafelki poprawnych słów. W miejscu ikony dodania jest checkbox, na starcie zaznaczony. Odznaczenie wyłącza słowo z zatwierdzenia.
4. Na dole „Porzuć” i „Zatwierdź”.

„Porzuć” kasuje całe zadanie. Żadna karta nie powstaje. „Zatwierdź” jest wyłączone, gdy zaznaczonych kafelków jest więcej niż zostało z dziennego limitu. Zapisuje tylko zaznaczone.

Potem zakładka Import wraca do przycisku. Karty są na liście docelowej i dociągają treść jak w punkcie 6, po jednej. Zamknięcie aplikacji nie przerywa analizy, zapisu ani dociągania. Po ponownym wejściu w Dodaj zakładka „Szukaj” jest znowu pierwsza, a „Import” pokazuje ten sam stan zadania, dopóki użytkownik go nie porzuci albo nie zatwierdzi.

### Jak to działa dzisiaj

Ostatnie 90 dni: 11 importów doszło do końca, same wklejki. Przy 30 słowach analiza trwa 66–83 s, a zapis kart 151–229 s. Czas od utworzenia zadania do końca, typowo 275 s, zawiera też siedzenie na ekranie zatwierdzenia. Pomiar z 8 listopada, liczony od zdarzeń `import_job_events` zamiast od pól zadania: analiza 51–62 s, zapis 147–224 s, całość 233–308 s. Poza nimi 3 zadania padły i 6 anulowano, wszystkie na długich listach.

`POST /api/v1/imports/jobs` trwa typowo 2,5 s i zwraca numer zadania. Telefon pyta o postęp co 1 s. Sam odczyt postępu trwa około 1 s. Jedno zadanie aktywne na parę użytkownik i profil (`uq_import_jobs_one_active`). Status zostaje w `import_jobs` po zamknięciu aplikacji. `resume_unfinished_jobs` wznawia zadanie po starcie procesu. Ekran Dodaj przy aktywnym zadaniu chowa szukanie i pokazuje albo postęp, albo akordeon „Wejdzie / Duplikaty / Błędy”.

Rozpoznanie, `_run_analyze`:

1. Lista słowo w linii, do sześciu słów w linii, ma `kind=plain` i nie woła modelu formatu. Inny układ woła `import_format` na `gpt-5.6-terra`, typowo 2,8 s.
2. `import_classify`, terra, jedno wywołanie na całą listę. 13 wywołań w 90 dniach, typowo 10,2 s, około 1400 tokenów polecenia i 1600 odpowiedzi. Myślenie włączone. Najdłuższe wywołanie trwało 48 s. Odpowiedź jest obcięta do 6000 tokenów, a kod przyjmuje do 10 000 notatek w jednym wywołaniu.
3. Dla każdego słowa `find_card_anywhere` czyta wszystkie żywe karty profilu. Co 10 słów jest commit.
4. `import_verify`, terra, typowo 1,3 s.

Przy 30 słowach modele to około 15 s. Reszta analizy i cały zapis to czytanie pełnych kart, po razie na słowo. Zapis jednej pozycji woła ten sam `find_card_anywhere` i `hydrate_from_lexical_cache` co punkt 5, potem `spawn_enrich`.

Nie ma limitu liczby słów na zadaniu. Wklejka ma najwyżej 500 000 znaków, plik 80 MB. Stary `POST /api/v1/imports/validate` odrzuca listę dłuższą niż 50 słów. Aplikacja ma tekst o 50 kartach i tej ścieżki nie woła. Wklejka może też być adresem URL: `create_job_from_text` pobiera wtedy słowa przez `fetch_words_from_url`.

`import_verify` w 90 dniach: 14 wywołań, zero odrzuceń. Jego zdjęcie nie zmienia wyniku żadnego z tych importów.

Anulowanie (`finalize_cancel`) nie kasuje kart, tylko ustawia im `deleted_at`. Zostają tombstony z `import_job_id`. `created_at` kart ma `server_default=func.now()`, więc karty wstawione w jednej transakcji mają ten sam czas.

### Co jest wolne

Ekran zatwierdzenia dochodzi po minucie, bo duplikaty są liczone osobnym odczytem wszystkich kart na każde słowo. Zapis 30 kart trwa kolejne trzy minuty z tego samego powodu. Klasyfikacja dokłada około 10 s, z tokenami myślenia.

### Decyzja

Biznesowo domknięte 8 listopada 2026.

Limit jest na profil językowy i na dobę od północy UTC. Do limitu wchodzą karty importu faktycznie wstawione tego dnia, także te później usunięte. Odrzucone, duplikaty, odznaczone i porzucony import nie wchodzą. Szukanie nie wchodzi. Jedno wklejenie i jeden plik mają najwyżej 25 niepustych pozycji. Powyżej tej liczby zadanie się nie zakłada. Gdy zostało mniej miejsc niż zaznaczonych kafelków, „Zatwierdź” czeka na odznaczenie nadmiaru. Na pełnym limicie dnia wszystkie poprawne kafelki startują zaznaczone, bo 25 pozycji mieści się w limicie.

Analiza listy słowo w linii zostaje bez modelu formatu. Inny układ zostaje przy jednym `import_format`. Klasyfikacja zostaje przy `gpt-5.6-terra`, z `reasoning_effort=none`. Drugie wywołanie `import_verify` schodzi. Zostają filtry mechaniczne już obecne przy odrzuceniu śmieci. Duplikaty biorą się z jednego odczytu lemy, części mowy i nazwy listy. Przycisk „Importuj” w trakcie analizy pokazuje jeden napis „Trwa analiza słów”, bez przełączania etapów format, klasyfikacja i duplikaty.

Zapis zatwierdzonych pozycji jest wstawieniem wiersza `pending` z punktu 5, bez hydracji i bez czytania treści kart w tym żądaniu. Zadanie kończy się po wstawieniu wierszy. Kolejny import może wystartować, o ile został dzienny limit i nie ma innego aktywnego zadania.

Dociąganie idzie kolejką profilu, jedna karta po drugiej. Hasło (`lemma`) bierze cztery wywołania z punktu 6. Następne hasło startuje, gdy poprzednie ma status `learnable`. Zwrot, konstrukcja i `other` biorą dotychczasowe jedno wywołanie adaptive. Następna karta startuje, gdy to wywołanie jest zapisane. Kolejka przeżywa zamknięcie aplikacji i nie trzyma blokady importu.

Dziś trzy miejsca puszczają wzbogacanie karty `pending` od razu i ominęłyby kolejkę: `GET /cards/{id}` (`spawn_enrich` przy `pending`), wznowienie po starcie (`resume_pending_enrichment`) i watchdog (`stale_only`, karta `pending` starsza niż 45 s). Telefon odpytuje karty z listy, więc pierwsze odpytanie puściłoby wszystkie 25 naraz. Dlatego bramka kolejki siedzi w samym zadaniu (`_enrich_card_unlocked`), nie w miejscu wywołania. Karta importu startuje tylko wtedy, gdy żadna wcześniejsza karta importu tego profilu nie ma statusu `pending`. Inaczej zadanie kończy się bez zmian. Stan kolejki jest w bazie, więc przeżywa restart.

Kolejność kolejki to kolejność pozycji w imporcie. `created_at` się do tego nie nadaje (ten sam czas w jednej transakcji). Commit nadaje kartom rosnące `created_at` (czas commitu plus numer pozycji w mikrosekundach) albo bramka sortuje po pozycji `import_job_items`.

Licznik dnia liczy karty z `import_job_id` zadań tego profilu, utworzone od północy UTC, także z `deleted_at`, ale bez kart zadań o statusie `cancelled`. Anulowanie zostawia tombstony (`finalize_cancel`), a porzucony import nie może zjadać limitu.

Limit 25 pozycji dotyczy też wklejonego adresu URL. Przy wklejce, której układ rozpoznaje dopiero `import_format`, liczba pozycji nie jest znana przy zakładaniu zadania. Wtedy przed zadaniem liczymy niepuste linie, a po `import_format` sprawdzamy liczbę notatek jeszcze raz. Ponad 25 kończy analizę błędem `import_too_many`, bez klasyfikacji.

Pomiar 8 listopada 2026, gołe API, terra, `reasoning_effort=none`, 25 linii polski → hiszpański: 9,2 s, 1191 tokenów polecenia, 1357 odpowiedzi, zero tokenów myślenia. Powtórka w weryfikacji: 8,3 s, 1190 / 1357 tokenów, zero myślenia, `valid=false` dokładnie przy tych samych pięciu liniach. Polskie `dźwięk` i `łąka`, angielskie `the house`, `ppppppppp` i `123456` wróciły jako `valid=false` z powodem. Hiszpańskie hasła, zwroty i konstrukcja wróciły jako `valid=true`.

### Instrukcja implementacji

Pliki: `backend/app/services/import_jobs.py`, `backend/app/services/llm.py` (`analyze_import_classify`), `backend/app/api/v1/imports.py`, `android/.../home/HomeScreen.kt` (`AddTab`), `android/.../home/ImportUi.kt`.

Przed `create_job_from_text` i `create_job_from_file` serwer liczy niepuste pozycje. Więcej niż 25 daje błąd `import_too_many`. Liczba kart importu profilu od północy UTC równa 25 daje błąd `import_daily_limit` i wyłączony przycisk. Odpowiedź postępu niesie `daily_used` i `daily_limit=25`.

`analyze_import_classify`: `reasoning_effort=none`, `max_completion_tokens` 2500, bez temperatury. `_verify_ready_lemmas` nie jest wołane. Duplikat: jeden `SELECT` żywych kart profilu, kolumny `id`, `lemma_l2`, `pos`, `deck_id`, nazwa listy. `deck_id` puste to lista systemowa. Dopasowanie lemy i części mowy zostaje przy dotychczasowej regule, razem z formą z rodzajnikiem. Pozycja duplikatu w odpowiedzi ma `list_name`.

Ekran: zakładki „Szukaj” i „Import”, domyślnie „Szukaj”. Akordeon schodzi. Sekcje błędów i duplikatów są otwarte. Kafelki poprawnych mają checkbox. „Porzuć” woła dotychczasowe anulowanie. „Zatwierdź” woła commit z `item_ids` zaznaczonych pozycji.

Commit wstawia karty jak lekki zapis z punktu 5, wszystkie w jednej transakcji, i ustawia zadanie `done`. Nie woła `spawn_enrich` w pętli. Osobna kolejka profilu bierze nowe karty importu w kolejności pozycji i puszcza następną, gdy poprzednie hasło jest `learnable` albo gdy karta adaptive ma zapisany wynik. Bramka kolejki w `_enrich_card_unlocked` obejmuje też `get_card`, wznowienie i watchdog.

Dziś `_run_commit` robi kilka commitów na pozycję. Jedna transakcja na całe zatwierdzenie znaczy, że błąd jednej pozycji (na przykład `IntegrityError` z równoczesnym ręcznym dodaniem tej samej lemy) nie może wywrócić reszty. Każda pozycja idzie w `SAVEPOINT` (`begin_nested`). Pozycja z błędem dostaje dotychczasowy powód duplikatu, a reszta się zapisuje.

Teksty: polski w `values-pl`, angielski w domyślnym `values/` i w `values-en`, w pozostałych `values-*` tłumaczenie w tym języku (jak w punkcie 1):

| Klucz | Polski | Angielski |
|---|---|---|
| `add_tab_search` | Szukaj | Search |
| `add_tab_import` | Import | Import |
| `import_analyzing` | Trwa analiza słów | Analyzing words |
| `import_abandon` | Porzuć | Discard |
| `import_confirm` | Zatwierdź | Confirm |
| `import_too_many_lines` | Jednorazowo możesz podać najwyżej 25 pozycji. | You can submit at most 25 items at once. |
| `import_daily_used` | Dzienny limit 25 kart jest wykorzystany. | The daily limit of 25 cards is used up. |
| `import_daily_remaining` | Dziś możesz zaimportować jeszcze %1$d z 25. | You can import %1$d of 25 cards today. |

`import_limit_exceeded` o 50 kartach schodzi z użycia.

### Jak sprawdzimy

Profil polski → hiszpański, lista 25 linii: hasła hiszpańskie, jeden zwrot, jedno polskie słowo, jeden śmieć, jedno hasło już obecne na liście.

- Zadanie ponad 25 pozycji nie powstaje. Przy 25 zapisanych kartach importu od północy UTC przycisk „Importuj” jest wyłączony.
- Do ekranu z kafelkami mija około 10 s. W `llm_usage` jest jedno `import_classify` z `reasoning_tokens=0` i nie ma `import_verify`. Polskie słowo i śmieć są w „Błędy” z powodem. Hasło z listy jest w „Duplikaty” z nazwą tej listy.
- Odznaczenie jednego kafelka i „Zatwierdź” wstawia tylko zaznaczone wiersze `pending`. „Porzuć” zostawia zero nowych kart i nie podbija licznika dnia.
- W `llm_usage` studia haseł idą po kolei: drugie `enrich_study` startuje po `learnable` pierwszego. Zwrot ma jedno wywołanie `adaptive`, nie cztery z punktu 6. Kolejność odpowiada kolejności linii.
- Telefon odpytujący listę docelową w trakcie kolejki nie przyspiesza jej: `GET /cards/{id}` dla karty dalej w kolejce nie tworzy wiersza `llm_usage`. Restart procesu w trakcie kolejki nie puszcza wszystkich kart naraz.
- Anulowanie w trakcie zapisu: albo zapis się kończy i karty są, albo kart nie ma. Karty anulowanego zadania nie podbijają licznika dnia.
- Zabicie aplikacji w trakcie analizy i ponowne wejście w Dodaj pokazuje „Szukaj”, a w „Import” ten sam stan zadania.

---

## Rejestr zmian

### 8 listopada 2026: weryfikacja z kodem, produkcją i modelami

Źródła: kod backendu i Androida z commitu `33a3b6d` (ten sam, który działa na produkcji, deploy `6b584601`), odczyty bazy produkcji tylko do odczytu, log HTTP Railway z 6–7 listopada, gołe wywołania OpenAI na kluczu z `.env`. Skrypty pomiarowe po weryfikacji zostały usunięte.

Nagłówek i „Jak czytać czasy”

- Było: wiersz `app_logs` powstaje po odpowiedzi. Jest: powstaje przed odpowiedzią i telefon na niego czeka. Powód: `AppLogMiddleware` robi `await log_event(...)` przed `return response`. Log krawędzi Railway pokazuje 0,44 s ponad `duration_ms` tych samych żądań `prado`.
- Dodane: odnośnik do rejestru i do `docs/taski/`, identyfikator deployu.

Kolejka

- Dodany wiersz 0 i zdanie, że kolejność wdrażania jest w `docs/taski/README.md`. Powód: bez rozdziału 0 pomiary punktów 1–7 nie pokażą efektu.

Rozdział 0 (nowy)

- Dwie repliki w dwóch regionach, baza w USA, telefon na replice europejskiej, około 141 ms na podróż do bazy. Powód: konfiguracja serwisu, log HTTP (130 ze 141 żądań na `ef650127`, krawędź `europe-west4`), przerwy `llm_usage` → `llm_call_payloads` 430–575 ms wobec 10–50 ms w USA.
- Pamięć procesu (`_inflight`, `_claimed`, semafor, wznowienia) przy dwóch replikach. Powód: kod `lookup_jobs.py`, `lookup_category_jobs.py`, `card_jobs.py`, `import_jobs.py`.
- Trzy zapisy po każdym wywołaniu modelu. Powód: kod `_chat_json` i `record_llm_usage`.
- Pętla `learnable`. Powód: kod (`finish_side_jobs` liczy odmianę inaczej niż `_has_required_inflection`), produkcja (7 kart, około 61 tysięcy `enrich_ready` w 30 dniach, `updated_at` co 15 minut), log HTTP (6 tych kart odpytywanych w czasie testu `prado`).
- `notify_cards_ready` dziś nie wysyła FCM, tylko czyta bazę i loguje. Powód: kod `send_push_to_user`.

Punkt 1

- Tabela `prado` dostała kolumnę z krawędzi Railway i statusy 499 workera. Opis: worker podwaja pracę serwera.
- 30 dni: 31 żądań, typowo 3,8 s, dziewiąty decyl 5,8 s (było 26 / 3,9 / 6,1, okno przesunięte o dzień).
- `EXPLAIN`: odczyt kart idzie po indeksie `uq_learning_cards_live_lemma_pos`, nie skanem tabeli. Hasła dla trzech słów: 2 trafienia, nie 0. Powód: `EXPLAIN ANALYZE` powtórzony 8 listopada.
- Odczyt kart przy odpowiedzi bierze same kolumny, bez `content`, a przed nim jest `ensure_system_list`. Powód: kod `_annotate_candidates`.
- `reading` i `typed_as` mogą być w cache, choć dziś nie ma ich w żadnym wierszu. Powód: kod `_payload_candidate`, odczyt 188 wierszy.
- Było: zestawienie z Room przez `sameLemmaAndPos`, które łączy `el prado` z `prado`. Jest: nowa funkcja zgodna z `select_live_card_for_lemma`. Powód: `sameLemmaAndPos` porównuje dokładny tekst i przepuszcza nieznaną część mowy do każdej, serwer robi odwrotnie. Rozjazd dałby przycisk dodania przy duplikacie i 409.
- Było: kółko przy braku kopii kart bez zmian w `CandidateRow`. Jest: czwarty stan kafelka, bez napisu „Tworzę kartę…” i bez odpytywania. Powód: `CandidateRow` rysuje kółko tylko przez `isCreating`, a ono zawsze pokazuje ten napis i włącza odpytywanie.
- Dodane: zgodność ze starym telefonem (`local_membership`), znaczenie pominięcia odczytu `users` (404 zamiast 401 dla usuniętego konta), mechanizm zapisów w tle, blokada wiersza przez `hit_count` w ORM, rola `AppVisibilityHandler`.
- Napisy: angielski w domyślnym `values/`, tłumaczenia w `values-*`. Powód: `values/strings.xml` jest angielskim domyślnym zasobem, a wszystkie 16 plików `values-*` ma dziś przetłumaczone `action_add`.
- Próg sprawdzenia: `duration_ms` poniżej 150 ms i krawędź poniżej 600 ms po tasku 01, zamiast „poniżej 800 ms”. Powód: 800 ms było celem bez znanej przyczyny opóźnienia. Po przeniesieniu API do bazy zostaje droga Europa–Kalifornia.

Punkt 2

- Dodane zdanie o rodzajniku (ART2) w promptach punktów 2, 3 i 4. Powód: pomiar 8 listopada. Bez niego rzeczowniki wracają bez rodzajnika, krótsze brzmienie nie trzyma `a água`, ART2 trzyma 4 na 4. `ensure_noun_article` nie pomoże, bo szkic nie zna rodzaju.
- Ryzyka: klasyfikator wietnamski (`ngôi nhà` 3 na 4) i utrwalanie pomyłki szkicu we wspólnym cache.
- Dodane: zwolnienie połączenia na czas modelu, przypadki z rodzajnikiem i równoległym wpisem w sprawdzeniu.
- Równoległy zapis tego samego hasła: było „`ON CONFLICT DO UPDATE` ze złączeniem `append_lookup_candidates`”, jest dotychczasowe `_merge_into_query_cache` (`DO NOTHING`, `SELECT … FOR UPDATE`, złączenie w Pythonie). Powód: kod `_ensure_query_cache_row` już tak działa i nie daje `IntegrityError`, a złączenia w Pythonie nie da się wpisać w `DO UPDATE`. Poprawione przy pisaniu taska 05.

Punkt 3

- Dodane zdanie `If no other real reading exists, return an empty candidates list.` Powód: bez niego `casa` z pokazanym `ev` dało `kasa`, z nim 4 na 4 puste odpowiedzi przy pełnej liście.
- `more` w kluczu `_inflight` i bez drugiego wczesnego powrotu. Powód: kod `lookup_jobs.py` i `LexicalService.lookup_expand`. Bez tego „więcej” dołącza do zwykłego zadania i modelu nie woła.
- Pole `added` w odpowiedzi. Powód: telefon musi wiedzieć, kiedy pokazać „Nie ma więcej propozycji.”, a `append_lookup_candidates` już tę liczbę zwraca.
- Sesja zadania bez połączenia na czas modelu i ponowny odczyt `FOR UPDATE` przy zapisie.

Punkt 4

- Liczby skojarzeń: 17–20 pozycji, mieszanka na wszystkich 78 czasownikach 48 / 26 / 21 / 5% (było: próbka 12 czasowników, 18–20). Pierwsze pytanie bez modelu: n=59, p50 4,0 s.
- Długość klucza `assoc:` w kolumnie `String(200)`, z tym samym błędem przy `cat:`. Powód: model `LookupQueryCache` i `normalize_lookup_query`, `LookupRequest.text` do 200 znaków.
- `round` w kluczu `_inflight`, 409 przy brakującej poprzedniej rundzie, `ON CONFLICT DO NOTHING` przy wspólnym wierszu, filtr słowa tematu kluczem kanonicznym.
- Napisy: było angielski we wszystkich `values-*`, jest tłumaczenie. Powód: `search_by_category` jest dziś przetłumaczone w 16 plikach, angielski zastąpiłby 14 tłumaczeń.
- Brak pola `round` (starszy telefon): odpowiedź ze słowem na początku i ósemką rundy 1. Powód: `LookupSession` starszej wersji zastępuje listę wynikiem `category/expand` i zgubiłby pierwszy kafelek. Dopisane przy pisaniu taska 08.

Punkt 5

- Było: ptaszek po odpowiedzi serwera. Jest: kółko i „Tworzę kartę…” do `learnable`, zgodnie z punktem 6. Powód: `markCandidateOnList` przepisuje `pending` z odpowiedzi, a `CandidateRow` przy `pending` rysuje kółko. Dokument przeczył sam sobie (punkt 5 i punkt 6).
- Hydracja w tle przed semaforem wzbogacania. Powód: `_run_claimed_enrich` trzyma `_enrich_semaphore()` na całym zadaniu, więc gotowa kopia czekałaby za trzema kartami liczonymi modelem.
- `source_card_id` przekazany do zadania w tle. Powód: `attach_card_to_word_family(source_card=…)` zmienia też kartę źródłową, a zadanie w tle tej informacji dziś nie ma.
- 409 po nieświeżym Room: synchronizacja i ponowne zestawienie. Powód: `revertCreating` przywraca przycisk, a kolejny tap znowu daje 409.
- Sprawdzenie: `enviar` jest czasownikiem. Poprzednie punkty sprawdzenia zakładały rzeczownik.

Punkt 6

- Opis dzisiejszego przebiegu uzupełniony o `fill_related_articles_on_core`, `assemble_core_card`, próg 7 słów podobnych (`MIN_SIMILAR_FOR_QUIZ`, cel 12), ponowienie przy zmianie lemy, brak limitu odpytywania w `HomeViewModel`, skutki uboczne `GET /cards/{id}`. Powód: kod.
- 8 listopada: 130 kart, typowo 43 s, najszybciej 16 s, okno modeli 24,7 s.
- Znacznik `related_pending` w bramce `ready`. Powód: po podziale `content_is_complete` przepuściłoby kartę bez powiązanych do `lexical_entries`.
- `headword_note` w poleceniu nauki. Powód: telefon pokazuje je pod hasłem (`CardDetailContent.kt`, `FlashcardBackContent.kt`), a polecenie z pomiaru go nie miało.
- Polecenie powiązanych zamienione na REL2 z polem `article` i zdaniem o pustej liście. Powód: format, który czyta `_normalize_related_words`, `drop_related_missing_articles` wyrzuca rzeczownik bez rodzajnika, pomiar 8 listopada (100% rzeczowników z rodzajnikiem, puste listy tam, gdzie trzeba).
- Ponowienie samej brakującej części, ponowny odczyt karty przy każdym zapisie, limit odpytywania po stronie telefonu.
- Limit odpytywania: było „karta `learnable` bez zmiany `updated_at` przez 3 minuty”, jest flaga `enrichment_active` z `GET /cards/{id}` i 3 minuty od pierwszego odpytania. Powód: `CardResponse` (serwer i `Models.kt`) nie ma `updated_at`, więc telefon nie miałby czego porównać. Poprawione przy pisaniu taska 03.

Punkt 7

- Liczby z 8 listopada, `import_verify` zero odrzuceń w 14 wywołaniach, adres URL jako wklejka, tombstony po anulowaniu, ten sam `created_at` w jednej transakcji. Powód: produkcja i kod `import_jobs.py`, model `LearningCard`.
- Bramka kolejki w zadaniu, nie w miejscu wywołania. Powód: `get_card`, `resume_pending_enrichment` i watchdog same puszczają karty `pending`.
- Licznik dnia bez kart anulowanych zadań, kolejność po pozycji, sprawdzenie liczby po `import_format`, zapis w jednej transakcji z `SAVEPOINT` na pozycję.
- Napisy: tłumaczenia zamiast angielskiego, domyślne `values/`.

Nie zmienione, bo pomiar potwierdził: czasy z punktów 2–5 w granicach przesunięcia okna, czasy gołych wywołań modeli z punktów 2–4 i 7, skład ósemek skojarzeń, czasy rdzenia (23,7 s) i części do nauki.
