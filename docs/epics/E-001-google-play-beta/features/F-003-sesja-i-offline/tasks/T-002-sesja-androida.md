# T-002 · Spójna sesja Androida i bezpieczny logout

**ID:** `E-001/F-003/T-002` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Sesja i offline](../README.md). **Źródło:** B-03; F-04/F-05/F-12 w [analizie](../../../sources/analiza-2026-11-17.md).

## Postęp

### Krok 1 · Zaszyfrowany rekord sesji i wspólny refresh (18.11.2026)

Pakiet [`data/session`](../../../../../../android/app/src/main/java/com/vocabulario/app/data/session/):

- `SessionRecord`: jeden wersjonowany rekord (właściciel, `session_id`, para tokenów, `pending_refresh {request_id, input_refresh}`, status `ACTIVE`/`REAUTH_REQUIRED`). Zapis do osobnego DataStore `vocabulario_session` przez `KeystoreSessionCipher` (AES-256/GCM, świeży IV, format v1). Brak klucza lub uszkodzony blob → `RecoveryRequired`, bez zapisu i bez kasowania danych.
- `SessionCoordinator`: jedna blokada dla interceptora, authenticatora i repozytorium. Zapis przed publikacją w pamięci. `request_id` zapisany przed HTTP i ponawiany po timeout/restarcie. Kompletność i zgodność właściciela/sesji odpowiedzi są sprawdzane. 409 jednorazowo porównuje się z trwałym snapshotem. 401 `session_revoked`/`session_expired`/`session_upgrade_required`/`invalid_refresh_token`/`invalid_token` → `ReauthRequired` z zachowanym właścicielem. Timeout, IO, 429, 5xx i wadliwa odpowiedź nie są wylogowaniem.
- Migracja jawnych tokenów z `vocabulario_prefs`: najpierw trwały zaszyfrowany zapis, potem usunięcie jawnych kluczy. Migrowany rekord nie ma właściciela, więc backend odpowie `session_upgrade_required` → reauth.
- Publiczne `/auth/register|login|google|refresh|logout` bez Bearer i bez refresh po 401. Pozostałe `/auth/...` są traktowane jak zwykłe uwierzytelnione trasy. Usunięte `TokenRefresher`, `saveTokensAsync`, nieużywane `isLoggedIn` z tokena i Retrofitowe `auth/refresh`.
- Start aplikacji: AUTH tylko przy stanie innym niż `Active`. Błąd sieci przy starcie nie wywołuje już `logout()` ani kasowania Room. `hasSyncableSession` wymaga `Active`. Nieudany trwały zapis wylogowania nie przechodzi do AUTH.
- `err_session_ended` w 17 lokalizacjach dla kodów sesji.
- Testy: [`SessionCoordinatorTest`](../../../../../../android/app/src/test/java/com/vocabulario/app/data/session/SessionCoordinatorTest.kt) (14 przypadków, m.in. współbieżne 401 → jeden refresh, ten sam ID po restarcie, błąd zapisu nie publikuje pary, recovery bez zapisów). Gradle: unit tests 235/235, lint i `assembleDebug` OK.

**Tymczasowo, do kolejnych kroków:** login nadal czyści dane przed wynikiem, stan `ReauthRequired`/`RecoveryRequired` prowadzi na zwykły ekran AUTH (kroki 2–3: ekrany i nawigacja, login tego samego/innego konta), logout bez `POST /auth/logout` i bez zlecenia odwołania (krok logout), brak metadanych właściciela w Room i ochrony workerów (część d). Ta wersja Androida wymaga backendu z F-003/T-001 (pola `user_id`/`session_id` w odpowiedzi); oba wdrażamy razem.

## Cel, decyzje i zależności

Jedna spójna sesja Androida, bez utraty pracy i mieszania kont. **Zatwierdzone:** zwykła awaria sieci pozwala kontynuować naukę z cache; jednoznacznie odwołana/wygasła sesja blokuje bibliotekę i naukę do ponownego loginu tego samego właściciela, ale nie usuwa danych. Logout może zakończyć się lokalnie offline; odwołanie serwerowe jest wtedy jawnie odroczone.

**Start kontraktu:** [E-001/F-003/T-001](./T-001-sesje-backendu.md) i [E-001/F-003/T-003](./T-003-wynik-synchronizacji.md). T-003 może powstawać wcześniej, bez cyklu wykonawczego. **Integracja:** zatwierdzona [polityka F-004](../../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026), Google/recent-auth E-001/F-005/T-001, UI E-001/F-006/T-001, kolejka E-001/F-003/T-004. **Akceptacja wydania:** E-001/F-002 i E-001/F-008 — backup, aktualizacja, środowisko i urządzenie.

## Stan kodu i miejsca integracji

- [TokenStore](../../../../../../android/app/src/main/java/com/vocabulario/app/data/local/TokenStore.kt) publikuje tokeny przed trwałym zapisem; asynchroniczny zapis ukrywa błędy. Brak trwałego ID właściciela, generacji i identyfikatora refresh.
- [TokenRefresher](../../../../../../android/app/src/main/java/com/vocabulario/app/data/api/TokenRefresher.kt) przy części przejściowych błędów czyści tylko pamięć; restart może przywrócić stare poświadczenia. [TokenAuthenticator](../../../../../../android/app/src/main/java/com/vocabulario/app/data/api/TokenAuthenticator.kt) wyklucza całe `/auth/`, także przyszłe uwierzytelnione operacje konta.
- [AuthRepository](../../../../../../android/app/src/main/java/com/vocabulario/app/data/AuthRepository.kt) usuwa poprzednią sesję i Room przed wynikiem loginu. [AppViewModel](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/AppViewModel.kt) wnioskuje o zalogowaniu z obecności access i o onboardingu z zawodnego rozpoznawania profili.
- Room jest jedną bazą bez właściciela; [ImportStatePersistence](../../../../../../android/app/src/main/java/com/vocabulario/app/data/imports/ImportStatePersistence.kt) przechowuje sam job ID. Prace sync/import/lookup i przypomnienia muszą otrzymać wspólną ochronę przed zmianą sesji.

Poniżej projekt, nie opis już działającej implementacji.

## 1. Stan sesji i nawigacja

Jedno źródło stanu w koordynatorze sesji; UI nie wylicza `isLoggedIn` z ciągu tokena. Stan połączenia jest osobną cechą, nie odpowiednikiem wylogowania.

| Stan | Dostęp i przejście |
|---|---|
| `Loading` | Odczyt i uzgodnienie trwałych magazynów. Timeout daje ekran ponowienia/pomocy, nie domyślne AUTH/HOME ani kasowanie |
| `SignedOut` | Formularz loginu/rejestracji, bez dostępu do poprzedniego cache |
| `Active(owner, session, generation)` | Nauka lokalna przy ostatnio potwierdzonej weryfikacji adresu i dostępnym profilu. Brak sieci nie usuwa dostępu |
| `VerificationRequired` | Weryfikacja/korekta/resend/wyjście/pomoc; blokada nauki, importu i zwykłego sync, zachowany cache/outbox |
| `LegalAcceptanceRequired` | Ważna sesja, wymagane warunki/18+ z F-007/T-003: dokumenty/potwierdzenie, pomoc/prawa/logout/usunięcie; zachowany cache/outbox, bez nauki/sync do akceptacji |
| `ReauthRequired(owner, reason)` | Login tego samego konta, reset/pomoc lub jawna zmiana konta; bez biblioteki i nowych zapisów nauki |
| `DeletionPending(owner, receipt)` | Stan/termin z F-006, cofnięcie i pomoc; biblioteka/nauka/sync zablokowane, lokalna praca ukryta i zachowana przez grace |
| `DeletionOutcomeUnknown(owner, receipt)` | Po niepewnym żądaniu usunięcia najpierw ustalenie wyniku; brak dalszej nauki na założeniu, że request nie dotarł |
| `Transitioning` | Bariera logout/zmiany konta/odnowienia bezpieczeństwa; brak nowych operacji poprzedniego kontekstu |
| `RecoveryRequired` | Niespójność magazynów, brak klucza lub dane legacy bez właściciela: informacja, ponowienie/pomoc; nigdy automatyczny reset danych |

Po 401 access dopuszczona jedna próba wspólnego refresh i jedno ponowienie bezpiecznego żądania. `session_revoked`, `session_expired`, `session_upgrade_required` lub definitywnie odrzucony refresh prowadzą do reauth. Samo 401 formularza loginu nie zmienia sesji A; nie jest zdarzeniem globalnym. Timeout, IOException, 429/5xx i wadliwa odpowiedź nie dowodzą odwołania. Błąd protokołu/zapisu ma jawny komunikat i log bez sekretów.

403 `email_verification_required` zmienia uprawnienie, nie właściciela. Ostatni znany stan weryfikacji zapisujemy z kontem; przy braku takiego potwierdzenia nie przyznajemy pełnego dostępu offline. Refresh nie weryfikuje skrzynki. Stan `/me` uaktualniamy po loginie, powrocie z procesu konta i istniejącej synchronizacji, bez nowego pollingu.

403 `terms_acceptance_required` jest osobnym legal gate, nie powodem odwołania/rotowania sesji. Akceptacja online według [F-007/T-003](../../F-007-prywatnosc-i-wsparcie/tasks/T-003-warunki-i-informacje-prawne.md); jej brak nie kasuje pracy, a potwierdzenie nie weryfikuje adresu. Priorytet: lifecycle/ważność sesji → weryfikacja adresu → warunki. Stan przy owner; zaakceptowany cache offline nie odkrywa zdalnej zmiany, lecz raz otrzymane wymaganie respektuje także bez sieci. Bez nowego pollingu.

Reset i zmiana adresu wymagają nowego loginu na wszystkich urządzeniach. Zmiana/dodanie hasła oraz dołączenie Google zachowują bieżące urządzenie dopiero po trwałym przyjęciu odnowionej pary; pozostałe wymagają reauth. Utrata odpowiedzi nie oznacza cofnięcia operacji na serwerze.

## 2. Trwałość, właściciel i bariera odpowiedzi

Zachowujemy **jedną bazę jednego właściciela**; nie budujemy wielu przełączalnych offline kont ani nie dodajemy `user_id` do każdej tabeli bez potrzeby.

- Addytywna migracja Room dodaje pojedynczy rekord metadanych: `owner_user_id` UUID nullable, monotoniczna `generation`, `phase` (`signed_out`, `active`, `reauth`, `verification`, `installing`, `logging_out`, `legacy_unclaimed`), `transition_id` UUID nullable. Wszystkie wiersze cache i kolejek należą wyłącznie do tego właściciela. Rekord i licznik generacji nie są kasowane/resetowane przy logout; stary kontekst nie może znów pasować po ponownym loginie A.
- Rozszerzenie F-006 dodaje fazy `deletion_pending`/`deletion_unknown` i zabezpieczony receipt przy tym samym owner. Samo 202 przyjęcia nie kasuje Room. Cofnięcie wymaga nowego loginu do tego samego ID; potwierdzony nieodwracalny etap ma odrębną zgodę usunięcia z F-006, nie ogólną regułę „wyczyść po 401”.
- Jeden wersjonowany rekord sesji DataStore zawiera razem: właściciela, `session_id`, generację, parę tokenów, stan dostępu/weryfikacji, opcjonalne `pending_refresh {request_id, input_refresh}` i identyfikator przejścia. Zapis całego rekordu kończy się **przed** publikacją nowej sesji w pamięci. Brak `saveTokensAsync` z pomijaniem błędów.
- Sekretny rekord i zlecenia odwołania chroni Android Keystore (AES/GCM, świeży IV dla zapisu, wersjonowany format); bez hasła użytkownika i bez wdrażania przestarzałego magazynu jako nowej zależności. Błąd klucza/odszyfrowania nie uruchamia czyszczenia Room. Konfiguracja backup/transfer E-001/F-002 wyklucza poświadczenia, zlecenia odwołania i prywatną bazę z automatycznego przenoszenia między instalacjami; synchronizacja serwerowa pozostaje drogą odtworzenia. Lokalne niewysłane dane nie mają obietnicy przetrwania odinstalowania.
- Nie istnieje transakcja Room + DataStore. Koordynator serializuje przejścia i używa trwałego znacznika w Room: najpierw bariera/nowa generacja i zamiar, potem zapis docelowego rekordu DataStore, na końcu zakończenie przejścia Room i publikacja UI. Restart kończy zgodne przejście; przy brakującym zapisie uwierzytelnienia pozostawia właściciela i przechodzi do recovery/reauth, a nie odtwarza stare tokeny.
- Każdy request i worker przechwytuje niezmienny `SessionContext(ownerId, generation)` oraz jawny `profileId`, gdy potrzebny. Przed zapisem do Room sprawdza właściciela/generację **w tej samej transakcji co zapis**. Tokenowe CAS i publikacja stanu UI mają analogiczną kontrolę. Wynik innego kontekstu jest `Superseded`, bez zapisania, usunięcia kolejki ani powiadomienia.
- Zwykła rotacja refresh nie zmienia generacji; login/reauth, security renewal i logout ją zmieniają. Zmiana profilu nie zmienia właściciela; odpowiedź pozostaje przy profilu przechwyconym na początku, nigdy przy aktualnym profilu odczytanym po `await`.
- Anulowanie OkHttp/WorkManager i coroutine jest dodatkiem do bariery, nie dowodem, że stary serwer/request zakończył pracę. Nie połykamy `CancellationException`.

Aktywny profil ma źródło prawdy w Room; jego dotychczasowe kopie w preferencjach są projekcją odtwarzaną po starcie, nie niezależną decyzją. Motyw i język UI urządzenia nie są usuwane przez ogólne `preferences.clear()`; dane ustawień konta usuwa procedura właściciela.

## 3. Refresh oraz ponawianie mutacji

Jeden refresh w procesie dla aktualnej sesji; kolejni oczekujący używają jego wyniku. Mutex/koordynator wspólny dla interceptora, authenticatora i repozytorium, nie trzy niezależne blokady.

1. Przed HTTP trwale zapisać UUIDv4 `request_id` i wejściowy refresh przy aktualnej parze.
2. Wysłać dokładnie kontrakt [T-001](./T-001-sesje-backendu.md). Przy timeout/restart ponowić ten sam input/ID; nie tworzyć nowej rotacji tylko dlatego, że odpowiedź zaginęła.
3. Walidować kompletność odpowiedzi i zgodność właściciela/sesji; nową parę oraz usunięcie pending zapisać jednym zapisem. Dopiero potem udostępnić token oczekującym.
4. 409 odświeża lokalny snapshot pojedynczego koordynatora; bez spin-loop. Jeśli nadal brak rozwiązania, jawny błąd odzyskania/reauth z zachowanymi danymi. Poza pięciominutowym oknem nie obiecujemy odtworzenia pary.

Rozróżnić transport publicznych login/register/refresh/logout i uwierzytelnionych operacji `/auth/...`; brak wykluczenia całego prefiksu. Mutacje bez uzgodnionej idempotencji nie są automatycznie odtwarzane po timeout. Tokeny, body auth i zaszyfrowane rekordy nie trafiają do logów, analytics ani WorkManager `inputData`.

## 4. Login tego samego/innego konta

- Próba loginu nie wywołuje `clearAll` ani `beginNewSession` na początku. Anulowanie/błędne hasło/Google cancel/awaria pozostawiają poprzednie dane.
- Odpowiedź loginu jest kandydatem; zanim stanie się aktywna, porównujemy serwerowe `user_id` z właścicielem Room. Ten sam ID: reauth i uzgodnienie uprawnień, bez usuwania danych także po zmianie e-maila.
- Inny ID: bez podpięcia starej kolejki. Informacja „To inne konto” i przejście przez jawny logout/zmianę konta; użytkownik rozstrzyga wszystkie niewysłane dane. Odrzucona sesja-kandydat otrzymuje własne zlecenie odwołania, nie zastępuje sesji A.
- Dopiero po zakończonym wyjściu A można ustanowić właściciela B pustej bazy. Weryfikacja B oraz profil/onboarding mają własne wyniki z T-003; nie dziedziczą uprawnień/cache A.
- Link procesu konta A otwarty przy sesji B wykonuje tylko działanie linka A; nie przełącza właściciela, nie synchronizuje i nie usuwa B.

## 5. Logout lokalny i odwołanie serwerowe

Inwentaryzacja wszystkich profili z T-003 obejmuje również operacje zaparkowane i słowa wymagające decyzji. Przy liczbie >0 akcje: **Synchronizuj i wyloguj**, **Anuluj**, **Odrzuć niewysłane zmiany i wyloguj** z ponownym potwierdzeniem strat. Sam błąd/koniec czasu synchronizacji nie jest zgodą na odrzucenie. Podczas finalnego sprawdzania kolejki zakładamy barierę zapisów; nowa ocena w trakcie wcześniejszego sync musi pojawić się w końcowym liczniku.

1. Zapisz zamiar `logging_out`/nową generację w Room, zatrzymaj dopływ operacji, anuluj prace i wycisz przypomnienia konta. Trwale przenieś minimalny materiał odwołania do zaszyfrowanego zlecenia poza danymi aktywnego konta **przed** usunięciem aktywnych poświadczeń.
2. W transakcji usuń dane właściciela po spełnieniu warunku pustej kolejki lub świadomym odrzuceniu, ale nie rekord metadanych/generację (`clearAllTables` nie jest tą procedurą). Znacznik przejścia zachowaj do uzgodnienia DataStore. Wyzeruj aktywne auth/import/profil; nie kasuj niezależnych preferencji urządzenia ani zlecenia odwołania. Zakończ lokalne przejście i pokaż AUTH.
3. Zlecenie: losowe ID, dawne `owner_id/session_id`, ostatni refresh, ewentualny pending refresh input/ID, data utworzenia i stan. Nigdy nie służy do zwykłego sync, nauki ani przywrócenia zalogowania. Restart po dowolnym kroku kontynuuje cleanup; nie pokazuje danych A.
4. Z siecią wyślij `POST /auth/logout` i czekaj na 204, ale awaria nie cofa zakończonego lokalnego logout. UI rozróżnia „Wylogowano na urządzeniu; odwołanie na serwerze oczekuje” i potwierdzone odwołanie. Nowy login B nie jest blokowany pojedynczą awarią odwołania A.
5. Jeśli logout ma nieznany wynik rotacji, odzyskaj refresh przez **ten sam** pending input/request ID. 200 daje parę wyłącznie do trwałego zapisania w zleceniu i logout; `session_revoked` potwierdza odwołanie. Retry po oknie może odwołać sesję według T-001. Samo 401 starego refresh przy `/logout` nie dowodzi odwołania nadal aktywnej sesji; nie oznaczaj sukcesu.
6. Jeden unikalny WorkManager z ograniczeniem CONNECTED obsługuje zlecenia także w SignedOut, bez aktywnego Bearer. Backoff wykładniczy od 30 s, limit WorkManager 5 h; start aplikacji także podejmuje oczekujące zlecenia. Nie dodajemy cyklicznego pollingu. 429 respektuje `Retry-After`, 5xx/transport pozostawia zlecenie.
7. 204 usuwa sekret zlecenia; definitywnie nieważny/niewymienialny dowód kończy jako **niepotwierdzone**, bez udawania unieważnienia. Najpóźniej 30 dni od lokalnego logout usuwamy pozostały sekret, zachowując jedynie stan niepotwierdzenia do pokazania użytkownikowi. Upływ tego terminu nie jest dowodem zakończenia sesji na serwerze. Interfejs wyjaśnia możliwość resetu hasła w celu odwołania wszystkich sesji, bez obietnicy dla Google-only.

Zamiar logout zawiera trwałe `logout_disposition` (`require_empty` lub `discard_confirmed`) oraz fingerprint zaakceptowanego snapshotu kolejek. Zapis bariery i końcowy odczyt kolejki są jedną transakcją. Jeśli przybyła nieobjęta potwierdzeniem praca, nie utrwalamy zgody na jej utratę: aktualizujemy ostrzeżenie i wymagamy ponownej decyzji. Recovery nie wywodzi zgody na discard z samego `logging_out`.

Kolejka odwołań ma limit 32 miejsc łącznie z rezerwacjami; nie usuwa niewysłanych zleceń dla zwolnienia miejsca. Aktywna sesja ma zarezerwowane miejsce na lokalne wyjście, a login tworzący sesję-kandydata rezerwuje własne **przed HTTP**; także odrzucony kandydat może wymagać odwołania. Przy braku miejsca wymagane połączenie i opróżnienie kolejki lub jawny błąd z pomocą. F-007 ujmuje 30 dni w technicznej retencji; test zegara/purge potwierdza fizyczne usunięcie sekretów.

Lokalny logout nie anuluje importu na serwerze ani nie usuwa konta. Aktywny job z serwera jest informacją osobną od liczby niewysłanych operacji.

Podczas siedmiodniowego grace z [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) logout nie cofa usuwania, a zwykły sync jest zablokowany. Można pozostać przy zachowanych danych, najpierw cofnąć usuwanie albo jawnie odrzucić lokalną pracę i wyjść; brak fałszywej obietnicy odzyskania odrzuconych danych po późniejszym anulowaniu.

## 6. Zadania, powiadomienia i stare instalacje

- Sync, lookup, import oraz enrichment otrzymują tag/nazwę i wejście owner+generation, profil/job tam gdzie dotyczy. Kontrola przed startem, po HTTP i przed zapisem/notification. Stare globalne nazwy prac anulowane przy migracji.
- Referencja importu: owner+generation+profile+job, nie sam ID. Po reauth tego samego właściciela odtworzyć obserwację istniejącego joba przez istniejący mechanizm; nie tworzyć nowego importu/LLM. Nowa generacja przejmuje referencję dopiero po sprawdzeniu właściciela.
- Przypomnienia lokalne nie pokazują poprzedniego konta w SignedOut/reauth/weryfikacji. Receivery po reboot sprawdzają trwały stan; odwołanie już wysłanych notyfikacji nie zastępuje zatrzymania kolejnych.
- Migracja Room jest addytywna i nie używa destrukcyjnego fallback dla baz z niewysłaną pracą. Dla wcześniejszych wersji bez sprawdzonej ścieżki migracji jawny recovery, nie automatyczne usunięcie.
- Legacy baza bez wiarygodnego właściciela trafia do `legacy_unclaimed`. Nowy login, e-mail, dekodowany bez weryfikacji JWT ani domyślny profil **nie** przypisują jej automatycznie nowemu kontu. Dane i wszystkie kolejki pozostają nienaruszone, niewysyłane i niewidoczne dla innego właściciela.
- Przed rolloutem istniejące instalacje wymagają osobnej zatwierdzonej procedury: inwentaryzacja wszystkich kolejek, spójna prywatna kopia/odtworzenie i administracyjne potwierdzenie mapowania do stabilnego User.id albo synchronizacja starego klienta przed przełączeniem. Nie implementujemy automatycznej migracji nieznanego właściciela ani publicznego endpointu przenoszenia postępu. Bez dowodu mapowania pozostaje recovery/pomoc lub świadome odrzucenie z informacją o pełnym zakresie strat. Konkretna procedura dla obecnych instalacji jest bramką E-001/F-002/F-008, nie zgodą na operacje teraz.

## 7. Podział wykonania i akceptacja

Kolejne pionowe zmiany w ramach tego samego taska: (a) koordynator/stan i trwały format, (b) refresh i recovery, (c) login/reauth/logout z barierą, (d) worker/import/powiadomienia i nawigacja. Nie oddawać części (c) bez ochrony zapisów z (d); do tego czasu zmiana konta nie może być dostępna. Bez przebudowy całego repozytorium i bez dodatkowych interwałów nauki.

- [ ] Testy jednostkowe stanów: offline/timeout/429/5xx nie są odwołaniem; revocation, weryfikacja i błędny login mają różne przejścia.
- [ ] Wymuszone zakończenie procesu po każdym trwałym kroku refresh, install i logout nie wskrzesza starej sesji ani nie usuwa pracy bez zgody.
- [ ] Współbieżne 401 dają jeden refresh; utrata odpowiedzi przed/po commit oraz restart używają tego samego request ID. Błąd zapisu nie publikuje sukcesu.
- [ ] Kontrolowane bariery HTTP/Room: spóźniony pull/review/lookup/import/refresh A nie zapisuje się ani nie wysyła notyfikacji po zmianie generacji/logowaniu B.
- [ ] Nieudany login B nie kasuje A; reauth A po zmianie adresu zachowuje wszystkie kolejki. Reset/zmiana hasła/dodanie hasła/Google sprawdzają odmienne skutki sesji.
- [ ] Logout offline, nieznany wynik refresh, restart zlecenia i późniejszy login B nie powodują sync danych A jako B ani fałszywego potwierdzenia odwołania.
- [ ] Testy migracji wszystkich wspieranych wersji i legacy bez właściciela nie używają `clearAllTables` jako naprawy. Backup/restore bez klucza nie odsłania cache ani nie kasuje outboxu automatycznie.
- [ ] A-05/A-09…A-13/A-17 na urządzeniu: uprawniony cached home offline interaktywny w 3 s; po 10 s operacji sieciowej dostępny stan/wyjście, nie sam spinner.
- [ ] Nowe teksty/stany dostępne w 17 lokalizacjach, komunikaty nie ujawniają haseł/tokenów ani nie udają sukcesu serwerowego.

**Integracja:** retencja F-007, [istniejące instalacje/nowy pakiet F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md), środowiska/restore F-008/T-002/T-003 i `/me` F-006 mają właścicieli kontraktu. `restore_recovery_required` → ReauthRequired z pomocą bez zwykłej sesji; 426 → aktualizacja bez wipe; 503 backup/budżet → zachowane kolejki i jawna dostępność funkcji, nie logout. Testy runtime są kryterium implementacji.  
**Poza zakresem:** multi-account cache, lista urządzeń, nowe serwerowe push i operacje produkcyjne. **Wynik weryfikacji:** projekt oparty na kodzie, komplet kontraktów i zatwierdzone decyzje produktu; bez implementacji/wyników runtime.
