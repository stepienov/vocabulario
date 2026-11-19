# T-003 · Wiarygodny wynik synchronizacji i rozpoznawania profili

**ID:** `E-001/F-003/T-003` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Sesja i offline](../README.md). **Źródło:** B-09a; F-08/F-11 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zależności

Sukces oznacza potwierdzony wynik, nie samo zakończenie coroutine. Odróżnić brak profilu od awarii, dane lokalne od serwerowych i pełne zakończenie sync od częściowego postępu.

**Start:** bez gotowego UI/sesji Androida. Wspólny kształt kontekstu pochodzi z [E-001/F-003/T-002](./T-002-sesja-androida.md), nie czekamy na jego implementację. **Integracja:** E-001/F-003/T-001 (auth), E-001/F-003/T-004 (prezentacja i profile). **Akceptacja:** izolowany PostgreSQL i scenariusze E-001/F-008/T-001.

## Stan faktyczny

- [LearningRepository](../../../../../../android/app/src/main/java/com/vocabulario/app/data/LearningRepository.kt) zwraca `Unit` z `syncNow`; flush/push/pull mają niezależne `runCatching`. Worker uznaje normalny powrót za sukces także po ukrytej awarii.
- `hasProfile` zamienia błąd listy profili na pustą listę; bootstrap może wysłać istniejącego użytkownika do onboardingu.
- [OfflineStore](../../../../../../android/app/src/main/java/com/vocabulario/app/data/local/OfflineStore.kt) liczy w `pendingCount()` tylko reviews; istnieją też moves, undos, lookups i outbox, w tym parked. Niektóre błędne payloady/nieznane typy outbox wracają bez wyjątku i są usuwane jako wykonane.
- [sync/push](../../../../../../backend/app/api/v1/sync.py) zatwierdza batch jedną transakcją, zwraca liczniki applied/skipped i wyniki tylko zastosowanych moves/SRS. **Nie ma dziś per-item potwierdzenia przyczyny skip**. Klient usuwa wszystkie wysłane review/move po 200; sam brak w `moves`/`srs` nie dowodzi więc utraty operacji. Potrzebny jawny kontrakt dla skip, retry i konfliktów, nie błędna interpretacja obecnego API.
- [undo](../../../../../../backend/app/api/v1/learning.py) usuwa ReviewLog i ponownie stosuje przesłany snapshot także gdy loga już brak. Nie można uznać tego za bezpieczne ponowienie wobec kolejnych ocen.

## 1. Typowane wyniki i reguły sukcesu

Wprowadzić zamknięte typy Kotlin, bez `Boolean`, `Unit` i pustej listy jako zastępstwa awarii.

**`ProfileResolution`:**

- `Found(profiles, activeId, source=cache|server)` — dane należą do bieżącego właściciela; cached nie znaczy właśnie potwierdzone przez serwer.
- `ConfirmedEmpty` — wyłącznie poprawne 200 z pustą listą dla bieżącego kontekstu.
- `Unavailable(cause, hasCache)`, `AuthRequired(reason)`, `VerificationRequired`, `LegalAcceptanceRequired`, `Superseded`.

Onboarding tylko przy `ConfirmedEmpty`. Bez cache i przy offline/timeout/błędzie pokazujemy stan pobierania z ponowieniem/pomocą, nie pustą bibliotekę ani onboarding. Dostępny poprawny cache pozostaje używalny w granicach stanu sesji. Pusta odpowiedź nie usuwa profilu z niewysłanymi danymi.

**`SyncReport`:** owner+generation, żądany zakres (`activeProfile` lub `allPendingProfiles`), czasy start/koniec, wynik każdej fazy, liczby wysłanych/potwierdzonych/oczekujących/zablokowanych operacji oraz per-profile status pull. Bez treści słów/odpowiedzi w logach.

Zamknięte wyniki: `Complete`, `Partial`, `Offline`, `Busy`, `AuthRequired`, `VerificationRequired`, `LegalAcceptanceRequired`, `Failed(code, retryable, retryAfter?)`, `Superseded`. Faza może być `NotRun(reason)`; nie udaje wtedy sukcesu. Legal gate F-007 nie zamienia się w pusty profil, logout ani usunięcie kolejki.

- `Complete`: wszystkie wymagane fazy zakresu zakończone, brak błędów i nierozwiązanej pracy tego zakresu. Pusta kolejka bez udanego wymaganego pull to nie pełny sukces sync.
- `Partial`: zatwierdzono część pracy, ale pozostały błędy, konflikty, kolejki lub fazy; UI zachowuje te informacje.
- `Busy`: drugi sync już trwa; ręczny sync/logout może dołączyć do istniejącego zadania i następnie sprawdzić pełny zakres. Sam `tryLock=false` nie kończy logout jako sukces.
- Offline rozpoznaje także rzeczywisty błąd transportu przy pozornie dostępnym Wi-Fi. Typ błędu przechowuje przyczynę bez traktowania każdego IOException jako pewnego braku Internetu.
- `lastSuccessfulSyncAt` aktualizuje tylko pełny udany zakres profilu. `lastAttemptAt`/błąd i cursor pull są osobne; udany pull nie świadczy o wysłaniu outboxu.

Snapshot kolejki jest spójny w transakcji Room: reviews, moves, undos, lookups queued/needs_review oraz outbox pending/parked/blocked, ze wszystkich profili. Operację liczymy raz, nie ponownie za jej optymistyczny wiersz cache. Globalne ustawienia liczymy na poziomie konta. Import już przyjęty na serwerze pokazujemy osobno, nie jako niewysłaną operację.

Dodać jawny typ `content_report` z [F-007/T-002](../../F-007-prywatnosc-i-wsparcie/tasks/T-002-wsparcie-i-dostepnosc.md) do tego samego outboxu/QueueSnapshot i handlera ACK. Szkic po decyzji wysłania liczymy jako jedną oczekującą operację właściciela; 201/200 dokładnego retry potwierdza zapis raportu, nie poprawienie treści. Brak automatycznej wysyłki całej diagnostyki i brak cichego skip nieznanego typu.

## 2. Wykonanie, zakres i lokalna atomowość

Jeden właściciel/generacja na przebieg; snapshot ID operacji przed wysłaniem. Zmiana aktywnego profilu nie zmienia docelowego profilu już wykonywanej operacji. Lookups wysyłać według ich `profileId`, nie aktualnego globalnego profilu. Operacje bez profilu wymagające go są błędem danych, bez domyślnego zastępowania.

Kolejność: rozpoznanie sesji/profili → flush istniejących operacji z zachowaniem zależności → push review/move → pull właściwych profili. Logout używa `allPendingProfiles`, nie tylko widocznego języka. Zwykły sync nie pobiera bez potrzeby całej biblioteki wszystkich profili.

- Zapis lokalnej oceny/ruchu/undo/zmiany ustawień i jej trwałego intentu musi być jedną transakcją Room. Śmierć procesu nie zostawia lokalnego postępu bez kolejki ani kolejki bez zmiany.
- Po HTTP usuwamy tylko ID wysłanego snapshotu potwierdzone w odpowiedzi. Zastosowanie wyniku, usunięcie odpowiednich intentów oraz remap lokalnych ID odbywa się w jednej transakcji z kontrolą kontekstu.
- Ocena wykonana podczas lotu wcześniejszego push nie znika ani nie zostaje nadpisana starym SRS. Najpierw baza serwerowego SRS, potem odtworzenie nowszych lokalnych intencji w kolejności; analogicznie dla moves/ustawień/list. Nie stosować serwerowego snapshotu wprost nad nowszym lokalnym stanem.
- Full/incremental pull zachowuje wszystkie lokalne overlaye, nie tylko lokalne listy/pending inbox. Tombstone kolidujący z lokalną pracą staje się jawnym rozstrzygnięciem/konfliktem, bez wskrzeszania usuniętej karty.
- Cursor per-profile przesuwamy wyłącznie w tej samej transakcji co udane zastosowanie całego pull. Błąd parsowania/aplikacji/restart przed commit nie przesuwa kursora. Serwerowy kontrakt snapshot opisuje punkt 3.

`CancellationException` propaguje się. Pozostałe błędy są klasyfikowane i raportowane przez istniejące logowanie, a nie zamieniane na puste dane. Awaria auth przerywa kolejne autoryzowane fazy; błąd niezależnego profilu może dać Partial bez wymazania sukcesów pozostałych.

## 3. Pull i bezpieczny cursor

Obecne `server_time` po odczytach nie jest bezpiecznym watermark; timestamp sprzed SELECT także nie obejmuje wszystkich długo otwartych transakcji. Wybrany projekt wykorzystuje snapshot PostgreSQL i **jawny top-level xid**, bez uzależnienia poprawności od zegara, stałego overlap ani ponownego pełnego pobierania przy każdym sync.

1. Dodać `sync_xid xid8` do kart i list; DB trigger przy INSERT/UPDATE zapisuje `pg_current_xact_id()`. Zmiana głównego SRS dotyka znacznika powiązanej karty w tej samej transakcji. Dzięki triggerom dotyczy to także enrichment/importu i ścieżek bezpośrednio zapisujących ORM, bez ręcznego pamiętania o znaczniku w każdym callerze. Nie używać systemowej kolumny `xmin`, która podlega freezing, ani subtransaction ID z SAVEPOINT.
2. Ewentualny fizyczny DELETE karty/listy zapisuje w tej samej transakcji minimalny tombstone: owner, profil, typ, entity ID, sync_xid — bez treści słowa. Usunięcie konta usuwa także jego tombstones. Soft-delete pozostaje rozpoznawalny po dotychczasowym polu i nowym sync_xid.
3. Nowy `POST /sync/pull` przyjmuje `{profile_id, cursor: null|string}`; zachować legacy GET z `since` tylko na okres zgodności. Odpowiedź zachowuje dotychczasowe dane i dodaje `cursor`; `server_time` zostaje czasem prezentacji/diagnostyki, nie podstawą usuwania danych ani kolejnego delta.
4. Po autoryzacji i sprawdzeniu własności **dokładnie wskazanego profilu** 404 bez fallback. Dotychczasowe ensure settings/system list, jeśli konieczne, kończy własną transakcję przygotowania przed snapshotem. Następnie osobna krótka transakcja read-only `REPEATABLE READ`, od pierwszego SELECT bez wcześniejszego READ COMMITTED; wszystkie dane pull i `pg_current_snapshot()` czytane w tym samym widoku.
5. Pierwszy pull zwraca pełny profil i snapshot S. Kolejny wybiera widoczne w nowej transakcji zmiany, których `sync_xid` **nie był widoczny** w poprzednim S: `NOT pg_visible_in_snapshot(sync_xid, S)`. Wstępny filtr `sync_xid >= pg_snapshot_xmin(S)` z indeksem `(user_id, profile_id, sync_xid)` ogranicza pracę; ta sama reguła dla tombstones. Wykluczone wcześniej aktywne transakcje zostaną zauważone po commit nawet z małym XID. Transakcje anulowane nie pozostawiają widocznych wierszy.
6. Listy/ustawienia mogą nadal wracać jako mały pełny snapshot jak dziś; karty i usunięcia są delta. Zmiana SRS musi trafić do delta także bez zmiany treści karty. Wynik przywróconej karty/listy usuwa wcześniejszy lokalny tombstone, o ile nie ma nowszego intentu.
7. Cursor jest opaque dla klienta: wersjonowany base64url JSON z `db_epoch`, owner, profile i tekstem pg_snapshot. Maksymalnie 8192 znaków; ścisła walidacja UUID, zakresów xid8, kolejności/listy snapshotu i limitu rozmiaru przed funkcjami PostgreSQL. Cursor nie jest sekretem ani dowodem uprawnień, nie wymaga nowego klucza auth; każdy odczyt nadal filtruje po zalogowanym owner i sprawdzonym profilu. Zły format/inny profil/niemożliwy przyszły snapshot →422 `invalid_sync_cursor`, bez dynamicznego SQL.
8. `db_epoch` to trwały UUID instalacji bazy, zmieniany przed udostępnieniem odtworzonej bazy/zmianą niezgodną z kursorem. Inny epoch lub cursor starszy od zachowanego horyzontu tombstones →410 `sync_cursor_expired`. Klient wykonuje pojedynczy nowy pełny pull **z zachowaniem overlayów i kolejek**, nie reset danych ani pętlę full pull. Bez ważnego kursora po błędzie protokołu nie oznacza sync jako Complete.
9. Minimalne tombstones zachowujemy **30 dni**, wcześniej przy purge konta. `profile_sync_state` przechowuje per owner/profil `min_supported_xid`; GC w tej samej transakcji co fizyczne usunięcie podnosi granicę co najmniej ponad największy usunięty sync_xid. Cursor jest konserwatywnie akceptowany tylko przy `pg_snapshot_xmin(S) >= min_supported_xid`, inaczej 410. Nie zmieniamy globalnego epoch co 15 min i nie zmuszamy wszystkich do full pull przy pojedynczym usunięciu. Purge całego konta usuwa także jego sync state, bez zmiany horyzontu innych kont.
10. Ograniczony/zbyt duży snapshot lub niemożność utworzenia świeżego obsługiwanego S daje jawny 503 `sync_snapshot_unavailable` i alert, nie ucięty cursor lub pętlę full pull. Cały profil w becie zwracany jednym spójnym pull jak dziś, bez paginacji przez różne snapshoty. Jeśli rzeczywisty rozmiar przekracza limity transportu, jawne ograniczenie i odrębny projekt paginacji przed zwiększeniem skali, nie ciche ucięcie kart.

Addytywna migracja: nullable kolumna → triggery → backfill brakujących znaczników w kontrolowanych batchach → sprawdzenie kompletności/indeksy i NOT NULL → udostępnienie nowego pull. Podczas backfill nie obiecujemy nowego protokołu. E-001/F-008 sprawdza funkcje/isolation na docelowej wersji PostgreSQL oraz na osobnej bazie testowej; brak obsługi nie ma cichego timestamp fallback.

Podstawa: [funkcje snapshot i transakcji PostgreSQL](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-PG-SNAPSHOT). `pg_current_xact_id()` zwraca top-level ID także z podtransakcji; `pg_visible_in_snapshot` nie może dostawać subxid. Identyfikator zapisujemy jawnie, a widoczność samych wierszy zapewnia świeża transakcja RR.

## 4. Potwierdzenia push, undo i REST

Addytywnie rozszerzyć `SyncPushResponse` o `review_results` i `move_results`. Zachować dotychczasowe liczniki oraz `srs`/`moves` dla kompatybilnego klienta w czasie rollout.

Każdy wynik: `client_id`, `card_id`, `outcome` (`applied`, `duplicate`, `superseded`, `not_found`, `conflict`) i opcjonalny zamknięty `reason` (`card_unavailable`, `target_unavailable`, `undo_already_applied`, `operation_id_conflict`). Dokładnie jeden wynik na każdą wysłaną operację właściwego typu. `srs` nie służy jako lista ACK.

- `applied`/zgodny `duplicate`/`superseded`: można zdjąć konkretny intent; dla superseded UI nie twierdzi, że nasz starszy ruch wygrał.
- `not_found`: zasób własny niedostępny/usunięty, bez ujawniania cudzego właściciela. Ruch do usuniętej listy i review usuniętej karty wymagają jawnej informacji o niewykonaniu. Intent przechodzi do blocked, nie znika bez wiedzy użytkownika; „Odrzuć” usuwa go świadomie.
- `conflict`: pozostaje blocked z bezpieczną przyczyną. Nie wysyłać bez końca ani nie kasować.
- Brakujące/zdublowane/obce ID lub nieznany outcome w odpowiedzi to błąd protokołu. Nie usuwać niepotwierdzonych wierszy; bez polegania na samych licznikach.
- Deduplikacja na serwerze sprawdza właściciela, kartę i zgodność semantycznego payloadu, nie tylko globalne istnienie client ID. Jednoczesne ponowienia nie mogą dawać 500 ani dwóch efektów: wspólne uporządkowane blokady kart/SRS w `/sync/push`, `/srs/review` i `/srs/undo`, plus ograniczenia unikalności. Zmiany tylko w bezpośrednio zależnych ścieżkach SRS.
- Soft-deleted card jest niedostępna także dla push/undo; brak tworzenia SRS/oceny za tombstone.

**Undo:** niesłany review można anulować lokalnie w transakcji. Gdy wysyłka mogła dotrzeć, trwałe undo używa oryginalnego `client_id`; serwer zapisuje osobny minimalny znacznik zastosowanego undo, niezależny od kasowanego ReviewLog. Ponowienie tego samego undo zwraca już wykonany wynik **bez ponownego nadpisania SRS**. Opóźniony push anulowanej oceny trafia w znacznik i dostaje `superseded/undo_already_applied`. Jeśli istnieje nowsza ocena, undo nie przywraca ślepo starego snapshotu: 409 `undo_conflict`, zachowany intent i wybór odrzucenia konfliktowego undo/przyjęcia serwera. Znaczniki mają właściciela i znikają przy usunięciu konta/karty; retencja inna niż czas życia zasobu wymaga protokołu dopuszczalnego wieku operacji, nie arbitralnego cleanup po 7 dniach.

Do sprawdzenia „nowsza ocena” służy monotoniczne `SrsState.review_revision` pod blokadą karty i `ReviewLog.applied_revision`, nie zegar telefonu ani UUID loga. Zmiana SRS podnosi rewizję; undo znanego review może cofnąć snapshot tylko przy zgodnej rewizji. Gdy pierwotnego review nie ma i nie ma wcześniejszego znacznika undo, zapisujemy anulowanie jego ID bez zmiany SRS; nie stosujemy dowolnego starego snapshotu. Fingerprint intencji zapisany przy review/move/undo wykrywa inne body pod tym samym ID. Starszy log bez rewizji nie daje prawa do ślepego odtworzenia — jawny konflikt.

**Pozostały outbox:** typowane `Applied`, `AlreadyApplied`, `Deferred(dependency)`, `Blocked(code)` zamiast wczesnego `return`. Nieznany typ/wadliwy JSON zostaje blocked i widoczny; nie jest ACK. Rename zależny od `local:<uuid>` czeka na create/remap. 404 delete może oznaczać bezpieczne already absent; 404 rename/update oznacza brak zasobu, a nie udaną zmianę. Create po utracie odpowiedzi wymaga odnalezienia jednoznacznego zasobu w tym samym profilu lub stabilnego klucza idempotencji, nie nowej losowej mutacji. Remap obejmuje zależne payloady atomowo.

Dla create listy wymagany stabilny `client_op_id` UUIDv4 z lokalnego intentu. Dedykowany minimalny `list_creation_receipts` unique(owner, client_op_id) przechowuje fingerprint kanonicznego body/profil, wynikowy list ID i czas; lista+receipt w jednym commit, konflikt innego body 409. Receipt nie ma CASCADE od listy: usunięta lista przy retry nie powstaje ponownie (`already_deleted` → jawny AlreadyApplied bez remap do żywej listy). Minimalny receipt do końca konta, bez tekstu nazwy; kasowany przez purge User. Nie robić globalnego frameworka idempotencji dla każdego PUT; profile używają swojego ostatniego mutation/revision z T-004, raport swojego client_report_id.

`already_deleted` blokuje zależne rename/move do tego lokalnego ID jako `target_unavailable`, z widoczną możliwością rozstrzygnięcia; nie zostawia ich wiecznie w Deferred i nie tworzy zastępczej listy.

Lookups zachowują istniejącą serializację i sprawdzanie, czy stub nadal istnieje po HTTP. `needs_review` nie jest automatycznie ponownie lookupowane. Błąd sieci/5xx nie uruchamia kolejnego add/LLM z innym payloadem; 409 jest ACK tylko po potwierdzeniu semantycznego „już istnieje” w docelowym profilu/liście. Nie przywracamy usuniętych przez użytkownika stubów. Limity importu i moment `learnable` pozostają bez zmian.

## 5. Worker i UI

- Worker `Complete` → success; `Superseded` → spokojne zakończenie bez sukcesu widocznego jako sync nowego konta.
- `Offline`/przejściowy `Failed`/retryable Partial → WorkManager retry z istniejącym ograniczeniem sieci i backoff; respektować Retry-After. Po wyczerpaniu obecnego limitu prób zachować kolejkę i jawny ostatni błąd. Brak nowego szybkiego pollingu.
- Auth/weryfikacja/konflikt wymagający działania → zatrzymanie automatycznych prób tej pracy, zachowana kolejka i stan dla UI. Po prawidłowym reauth/weryfikacji istniejący scheduler wznawia pracę właściciela.
- Logout nie opiera się wyłącznie na `Complete`: finalnie sprawdza pod barierą **wszystkie** kolejki. Przy błędzie pull, lecz potwierdzonej pustej kolejce, może uczciwie wyjść; nie twierdzi wtedy, że wszystkie fazy sync zakończono.
- Przełączyć bezpośrednie call sites `syncNow`/`syncPendingReviews`, App/Auth/Home/Practice ViewModels i workerów; nie zostawić adaptera `runCatching { Unit }`, który z powrotem zgubi wynik.

## 6. Dostarczenie i testy

Podział L: najpierw typy/profil i lokalne wyniki, potem ACK/undo backend+Android oraz transakcje, następnie call sites/worker. Backend rozszerza odpowiedź przed wymagającym jej klientem; nowy klient nie usuwa kolejki na odpowiedzi starego serwera bez nowych ACK. Mechanizm minimalnej wersji/maintenance i granica odrzucenia starego klienta należą do wspólnego rollout E-001/F-002/F-008.

**Przegląd integracyjny:** pkt 3 definiuje snapshot/horyzont, pkt 4 ACK/deduplikację, F-007 retencję, a F-002/T-001 migrację/granicę zgodności. Restore i 426/503 z F-008 nie kasują overlayów; `restore_recovery_required` mapować do AuthRequired, backup protection do retryable Failed, AI budżet do zachowania oczekującej pracy. Testy niżej są wymaganiem implementacji, nie kolejną ankietą.

- [ ] A-08/A-11/A-20: timeout/500 profili nie otwiera onboardingu; tylko potwierdzona pusta lista to robi. Pierwszy nieudany pull nie udaje pustej biblioteki.
- [ ] Każda faza osobno: offline, busy, 401/403/429/5xx, częściowe powodzenie i anulowanie mają poprawny report, UI i wynik WorkManager.
- [ ] Wszystkie rodzaje kolejek, statusy i profile są objęte finalnym licznikiem logout; równoległa lokalna ocena nie ginie.
- [ ] Push commit + utracona odpowiedź + retry i dwa równoczesne retry dają jeden efekt; błędna lista ACK nie usuwa niepotwierdzonych danych.
- [ ] Undo retry po nowszej ocenie oraz opóźniony pierwotny review nie cofają nowego postępu ani nie odtwarzają anulowanej oceny.
- [ ] Push/pull z nowszą lokalną oceną, move, listą i ustawieniami nie nadpisuje overlayów. Restart przed/po lokalnym commit zachowuje parę intent+stan.
- [ ] Snapshot: commit między odczytem i odpowiedzią oraz długo otwarta transakcja z wcześniejszym XID są widoczne w kolejnym delta; rollback SAVEPOINT nie tworzy fałszywej zmiany. Zmiana samego SRS i fizyczne usunięcie trafiają do właściwego profilu.
- [ ] Restore/zmiana epoch i purge tombstones unieważniają nieobsługiwany cursor; ponowny pełny pull zachowuje niewysłaną pracę. Nieprawidłowy/zbyt duży cursor nie daje 500, odczytu innego właściciela ani częściowo przesuniętego kursora.
- [ ] Lookups ze stubów dwóch profili nie używają aktywnego profilu zamiast zapisanego; needs_review i błędy nie generują dodatkowych LLM/add.
- [ ] Testy backendu na wydzielonym PostgreSQL; Android unit/Room/fake transport oraz urządzenie, wyniki dołączone dopiero po implementacji.

Zakres L podzielony powyżej nie wymaga nowej numeracji. **Poza zakresem:** nowy panel diagnostyczny i architektura całego sync od zera. **Wynik weryfikacji:** analiza kodu/dokumentacji PostgreSQL i spójny projekt kontraktu/retencji/rollout; bez implementacji/runtime.
