# T-001 · Google i bezpieczne łączenie kont

**ID:** `E-001/F-005/T-001` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Google](../README.md). **Źródło:** B-06; F-07 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Pełna walidacja tokena Google i wymaganej konfiguracji audience, właściwe traktowanie tożsamości/verified email, jawna polityka dołączania metody logowania. Dopracować dedykowany przycisk Credential Manager, anulowanie, awarię dostawcy i clearCredentialState przy świadomym logout.

**Start:** [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md), [E-001/F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md). **Akceptacja końcowa:** po [E-001/F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md) i [E-001/F-003/T-002](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md), z OAuth skonfigurowanym dla podpisu Play.

## Uzgodnione zachowanie i granice

- Obowiązuje [polityka konta F-004](../../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026): zmiana adresu aplikacji nie odłącza Google. Wcześniej podłączone `sub` nadal prowadzi do tego samego ID i nie nadpisuje adresu aplikacji.
- Przy braku powiązania `sub` sama równość e-maili nie wystarcza do dołączenia Google. Potrzebne jawne potwierdzenie własności istniejącego konta i nowej metody, bez scalenia dwóch istniejących kont.
- Nie potwierdzać obecnego adresu aplikacji dowodem dotyczącym innej skrzynki Google.
- Dostarczany tutaj wspólny mechanizm ponownej weryfikacji Google jest wykorzystywany przez [E-001/F-004/T-005](../../F-004-email-i-hasla/tasks/T-005-dodanie-hasla.md); tam jest właściciel dodania hasła, tutaj walidacji Google. Nie tworzyć dwóch konkurencyjnych procesów.
- Samodzielne odłączanie metod jest poza betą. Reset hasła odwołuje sesje aplikacji, nie usuwa powiązania Google; właściwe ponowne logowanie Google nadal działa.

### Dalsze decyzje zatwierdzone 17.11.2026

- Dołączane Google może mieć inny adres niż konto aplikacji, po potwierdzeniu obu tożsamości. Nie zmieniamy adresu aplikacji, nie scalamy bibliotek i nie przepinamy Google należącego już do innego konta.
- Skuteczne dodanie Google odwołuje pozostałe sesje, bezpiecznie odnawia bieżącą i wysyła zawiadomienie na adres aplikacji. Zwykły login wcześniej podłączonym Google nie wykonuje tej operacji bezpieczeństwa.
- Google nie musi aktualnie zarządzać skrzynką używaną jako adres konta Google. Niezweryfikowany adres aplikacji spoza wiarygodnego Gmail/Workspace wymaga naszego linku; samo `email_verified=true` dla zewnętrznej skrzynki nie wystarcza. Już potwierdzonego adresu aplikacji nie weryfikujemy ponownie.
- Zmiana istniejącego hasła nadal wymaga obecnego hasła albo osobnego resetu przez e-mail. Dowód Google z tego taska nie jest alternatywą dla tej operacji.

## Stan kodu i miejsca integracji

- [Auth API](../../../../../../backend/app/api/v1/auth.py) szuka po `google_id`, a potem automatycznie dołącza po e-mailu. Druga gałąź wymaga zastąpienia kontrolowanym konfliktem i osobnym procesem dołączenia.
- [Obecny walidator](../../../../../../backend/app/services/llm.py#L1567) wykonuje request do `tokeninfo` i sprawdza audience tylko przy niepustej liście konfiguracji. Walidację produkcyjną wydzielić z usług LLM do wspólnego komponentu auth; bez wywołań modelu i bez refaktoryzacji pozostałego LLM.
- [Konfiguracja](../../../../../../backend/app/core/config.py) zbiera Web i Android client ID w jedną listę. Docelowe `aud` wynika z Web client ID przekazanego do Credential Manager; Android client ID/podpis konfigurują uprawnioną aplikację, nie stanowią automatycznie dodatkowego audience backendu.
- [User](../../../../../../backend/app/models/__init__.py#L11) ma unikalne `google_id`, ale nie ma dowodów recent-auth, nonce ani informacji o weryfikacji adresu. Współdzielimy rewizje i weryfikację z F-004.
- [GoogleAuthHelper](../../../../../../android/app/src/main/java/com/vocabulario/app/auth/GoogleAuthHelper.kt) używa `GetGoogleIdOption` bez nonce. [AuthRepository](../../../../../../android/app/src/main/java/com/vocabulario/app/data/AuthRepository.kt) rozpoczyna Google login od czyszczenia danych; tego nie wolno użyć do dołączania ani recent-auth.
- [AuthViewModel](../../../../../../android/app/src/main/java/com/vocabulario/app/ui/auth/AuthViewModel.kt) traktuje wyjątek anulowania jak błąd. [Zależności Androida](../../../../../../android/app/build.gradle.kts) zawierają Credential Manager i googleid; nie zakładamy potrzeby wymiany stosu ani aktualizacji do wersji alpha z przykładu dokumentacji.

## Proponowany kontrakt techniczny Google i recent-auth

Projekt wymaga przeglądu integracji i domknięcia poniższych blokad; nie oznacza implementacji ani statusu `ready`.

### 1. Walidacja i zaufanie do adresu

- Propozycja: produkcyjna biblioteka `google-auth`, walidacja podpisu kluczami Google, `RS256`, `iss` wyłącznie `accounts.google.com` / `https://accounts.google.com`, `aud` dokładnie zgodne z skonfigurowanym Web client ID, niepusty tekstowy `sub` mieszczący się w kolumnie, wymagane poprawne `iat/exp` oraz nonce. Tolerancja zegara maksymalnie 60 s nie wydłuża TTL naszego challenge.
- Produkcyjny/stagingowy brak wymaganego Web client ID blokuje start, nie pomija audience. Android `GOOGLE_WEB_CLIENT_ID` musi wskazywać ten sam projekt/klienta. ID nie jest sekretem; client secret ani token dostępu do Google API nie są potrzebne do tego logowania.
- Weryfikacja kryptograficzna odbywa się lokalnie, bez requestu `tokeninfo` przy każdym loginie. Transport kluczy ma cache respektujący ważność odpowiedzi Google, współdzielony na proces, oraz timeout 5 s; nie blokuje event loop. Rotacja kluczy wymaga kontrolowanego odświeżenia, bez nieograniczonego pobierania na każdy nieznany `kid`. Konkretny wariant transportu poniżej; stabilne kompatybilne wersje wykonawca zapisuje w manifestach przy implementacji i sprawdza istniejącym build/test, nie pyta właściciela o numery wydań bibliotek.
- Konkretny proponowany transport według dokumentacji biblioteki: `google.oauth2.id_token.verify_oauth2_token`, `google.auth.transport.requests.Request`, Requests i CacheControl z pamięciowym cache certyfikatów. Wywołanie w ograniczonym wątku, nie na event loop; osobne sesje transportu na wątek i jeden bezpieczny współbieżnie cache procesu, limit 4 równoległych walidacji. Adapter wymusza timeout 5 s. Zmiana klucza wymaga co najwyżej jednego wymuszonego odświeżenia na proces / 30 s, z synchronizacją, potem 401 dla nadal nieznanego klucza albo 503 przy błędzie pobrania. Nie pobieramy adresów kluczy podanych przez token.
- Brak możliwości uzyskania potrzebnego klucza przy awarii transportu to kontrolowane 503, nie „złe hasło”. Nie akceptujemy tokena bez sprawdzenia podpisu ani z kluczem poza okresem zaufania cache. Token błędny po udanym odczycie kluczy jest odrzucany.
- Dla nowego konta wymagany jest poprawny adres Google. Przed ustawieniem weryfikacji wymagamy `email_verified` jako prawdziwej wartości logicznej oraz: domeny adresu dokładnie `gmail.com` albo niepustego zweryfikowanego claimu `hd` (Workspace). Nie rozpoznajemy Workspace po samym sufiksie e-maila. Zewnętrzny adres bez tego dowodu pozostaje `pending` weryfikacji F-004.
- Powracającego użytkownika identyfikuje wyłącznie `sub`. Potwierdzenie bieżącego adresu Google może potwierdzić adres aplikacji tylko przy dokładnej zgodności po wspólnej normalizacji F-004 i sprawdzeniu aktualnej rewizji adresu. Inny/brakujący adres Google nie nadpisuje ani nie potwierdza adresu aplikacji.
- Opcjonalny obraz/nazwa profilu nie są wymagane ani zapisywane. Do wyświetlenia rozróżnienia metod proponujemy `User.google_email` i `google_email_observed_at` jako nullable snapshot adresu z poprawnie zweryfikowanego tokena podłączonego `sub`. `/me` przekazuje je jako ostatnio otrzymany adres konta Google, nie jako aktualizację `User.email` ani dowód dostępu do skrzynki. Brak snapshotu w starej bazie nie odłącza Google.

### 2. Challenge i jednorazowy dowód

Wspólne modele w bazie PostgreSQL, bez nowej usługi:

| Model | Pola i reguły |
|---|---|
| `auth_google_challenges` | UUID `id`, unikalny SHA-256 nonce, `purpose` (`login`, `link`, `recent_auth`, `account_deletion`), opcjonalne `action`, właściciel/sesja/wersja sesji i rewizje konta dla operacji zalogowanych, oczekiwane `google_id` dla recent-auth, powiązany dowód hasła dla link, UTC created/expires/consumed. Powiązania właściciela/sesji CASCADE |
| `auth_recent_proofs` | UUID `id`, unikalny SHA-256 losowego tokena, `user_id`, `session_id`, wersja sesji, `email_revision`, `credentials_revision`, metoda (`password`, `google`), dokładnie jedna `action`, UTC created/expires/consumed; CASCADE użytkownika/sesji |

- Nonce i token recent-auth: osobne 32 losowe bajty base64url, w bazie tylko hashe. TTL obu wynosi 5 minut; challenge do linkowania nie może żyć dłużej niż związany dowód hasła. Warunki celu/pól nie są dowolnym JSON: publiczny `login` nie może przenieść cudzej sesji/akcji.
- Serwer tworzy nonce, Android przekazuje dokładnie zwróconą wartość do `setNonce`, backend porównuje claim nonce z jego hashem w challenge. Token z poprzedniego logowania bez właściwego nonce nie jest dowodem nowej operacji.
- Recent-auth jest ograniczonym jednorazowym dowodem, nie access/refresh tokenem. Nie daje dostępu do nauki ani samodzielnego loginu. Trzymany tylko w pamięci klienta; restart/cofnięcie wymaga ponownego potwierdzenia, ale nie kasowania Room/outboxu.
- Dowód hasła: dla `link_google` i `change_email`, tylko gdy hasło istnieje. Dowód podłączonego Google: dla `change_email` i `add_password`, przy tym `add_password` tylko przy braku hasła. `change_password` nie jest dozwoloną akcją tego protokołu — T-002 sprawdza obecne hasło bezpośrednio.
- Przy poprawnym recent-auth Google wiarygodny Gmail/Workspace zgodny z bieżącym adresem może w tej samej transakcji potwierdzić ten adres, bez dodatkowego maila i bez zmiany jego rewizji. Inny/zewnętrzny adres nie zyskuje tego skutku; samo wydanie recent-proof nie omija weryfikacji.
- Recent-auth Google wymaga `sub` równego aktualnie podłączonemu Google, nie zgodności e-maila. Challenge wiąże go z konkretną sesją/akcją. Nie obiecujemy wymuszenia ponownego wpisania hasła Google lub biometrii: potwierdzamy świeżą odpowiedź Credential Manager na nowy nonce, nie czas ostatniego wpisania hasła u dostawcy.
- Zwykłe wydanie nowego access/refresh nie zastępuje recent-auth. Po odwołaniu/odnowieniu sesji bezpieczeństwa lub zmianie rewizji wcześniejszy dowód jest nieważny; zwykły refresh bez zmiany wersji sesji nie przedłuża TTL dowodu.
- TTL egzekwujemy przy użyciu, niezależnie od sprzątania. Wspólny cleanup/retencja opisane są w F-004/T-003; nie uruchamiamy nowej usługi ani pollingu Androida.
- Konkretny projekt limitów i cleanup jest teraz w [F-004/T-003](../../F-004-email-i-hasla/tasks/T-003-odpornosc-auth.md#proponowany-wspólny-kontrakt); nie tworzymy drugiego limitera i harmonogramu w tym tasku.

Osobny purpose `account_deletion` ma wyłącznie router [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md), action request/cancel i TTL 5 min. Używa tego samego walidatora/nonce, lecz wydaje token **akcji**, nie TokenResponse/recent-proof sesji. Zwykłe `/auth/google` odrzuca ten challenge, a dedykowany dowód nigdy nie rejestruje/nie łączy kont po adresie. Dzięki temu cofnięcie bez aplikacji nie tworzy nowego konta po jego skasowaniu.

### 3. API

Prefiks `/api/v1`; schematy walidowane, błędy przez istniejący `api_error`. Tokenów Google, nonce i dowodów recent-auth nie zapisujemy w logach, telemetryce ani URL.

| Endpoint | Dostęp i body | Sukces |
|---|---|---|
| `POST /auth/google/challenge` | Publiczny tylko dla `{"purpose":"login"}`. Dla `link`: aktywna sesja i `recent_auth_token`; dla `recent_auth`: aktywna sesja i `action` | 200 `{"challenge_id":"UUID","nonce":"...","expires_at":"UTC"}` |
| `POST /auth/google` | Publiczny, `{"challenge_id":"UUID","id_token":"..."}` dla challenge `login`; `legal_acceptance` z F-007/T-003 przy tworzeniu nowego konta | `TokenResponse` z F-003; nowe albo istniejące konto według reguł poniżej |
| `POST /auth/recent-auth/password` | Aktywna sesja, `{"password":"...","action":"link_google lub change_email"}` | 200 `{"recent_auth_token":"...","action":"...","expires_at":"UTC"}` |
| `POST /auth/recent-auth/google` | Aktywna sesja, `{"challenge_id":"UUID","id_token":"...","action":"change_email lub add_password"}` | Taki sam ograniczony dowód recent-auth; challenge zużyty atomowo z jego utworzeniem |
| `POST /auth/google/link` | Aktywna sesja, `{"challenge_id":"UUID","id_token":"...","recent_auth_token":"..."}` | `TokenResponse`: Google dodane, inne sesje odwołane, bieżąca odnowiona, trwałe zawiadomienie |

Dowody obsługują także zalogowane konto bez potwierdzonego adresu, ale nie nadają mu dostępu do nauki. Finalne dodanie Google wymaga zweryfikowanego adresu aplikacji albo pasującego wiarygodnego dowodu Gmail/Workspace, który potwierdza go w tej samej transakcji. Przy innym/zewnętrznym adresie najpierw weryfikacja F-004, potem nowa próba dołączenia. Dodanie hasła ma swój warunek weryfikacji z T-005.

Reguły `POST /auth/google` po pełnej walidacji:

1. `sub` już podłączone: to samo ID, nowa sesja, bez nadpisania adresu aplikacji.
2. `sub` niepodłączone, adres zajęty: 409 `google_sign_in_conflict`. Bez automatycznego dołączenia, scalenia i ujawnienia metod/cudzego ID. Komunikat kieruje do loginu istniejącą metodą lub odzyskania, a następnie „Moje konto → Dodaj Google”.
3. `sub` i adres wolne: nowe Google-only, `UserSettings`, stan weryfikacji według pkt 1 kontraktu, dowód warunków/18+ z [F-007/T-003](../../F-007-prywatnosc-i-wsparcie/tasks/T-003-warunki-i-informacje-prawne.md) i nowa sesja w jednej transakcji. Brak/zmiana wymaganej wersji nie tworzy częściowego konta i nie zużywa challenge do skutecznego loginu; klient po poprawieniu zgód uzyskuje świeży challenge/Google proof, bez przechowywania tokena do trwałego retry. Istniejące konto ma osobny legal gate, bez automatycznego tworzenia/łączenia nowego. Zewnętrzna niezweryfikowana skrzynka trafia do istniejącego procesu F-004.
4. Równoległe żądania nie tworzą duplikatu. Unikalność `google_id/email` i ponowna ocena stanu po konkretnym konflikcie DB rozstrzygają wynik, nie ogólny catch i 500. Dwa różne challenge dla tego samego nowego `sub` mogą zakończyć się sesjami jednego konta, nie dwoma kontami.

Reguły `link`: potwierdzone hasłem obecne konto + nowy dowód wybranego Google. `google_id` już przypisane do innego ID daje 409 `google_link_unavailable`, bez przełączania konta. Obecne konto z innym Google daje 409 `google_method_already_present`; brak podmiany/odłączenia w becie. Już to samo powiązanie daje jawne 409 `google_already_linked`, bez ponownego odwoływania sesji i maila. Sam adres Google zajęty przez inne konto z hasłem nie oznacza własności tego konta: w tej ścieżce nie wyszukujemy celu przeniesienia po e-mailu.

Pozostałe kody:

- 401 `invalid_google_token`: podpis/audience/issuer/czas/nonce niepoprawne; 403 `google_account_mismatch`: inne Google przy recent-auth zalogowanego konta.
- 410 `auth_challenge_expired`, 409 `auth_challenge_used`, 400 `auth_challenge_invalid`: wygasły, zużyty lub obcy/złym celem challenge.
- 403 `recent_auth_required`: brak, wygaśnięcie, zły cel/właściciel/sesja/rewizje dowodu; 409 `recent_auth_used` dla zużytego dowodu; 403 `current_password_invalid` dla nieudanego dowodu hasła.
- 403 `email_verification_required`: wymagany dowód skrzynki; 401 sesji według F-003; 422 nieprawidłowe pola bez odbijania sekretów.
- 429 z `Retry-After` dla przekroczonych limitów oraz 503 `google_temporarily_unavailable` dla awarii weryfikacji u dostawcy. Nie klasyfikujemy anulowania Credential Manager jako odpowiedzi API.

Brak nonce/pól u starego klienta nie może przełączać na słabszy walidator. Kolejność wydania/minimalna wersja z F-003 musi uwzględniać zmianę kontraktu Google.

### 4. Atomowość i skutki

- Walidacja kryptograficzna/hasła poza blokadami DB, potem ponowne sprawdzenie uprawnień, czasu i rewizji pod blokadą. Kolejność zgodna z F-003: użytkownik → sesje/retry → recent-proof → challenge Google → zmiana adresu → proces usunięcia, jeśli dotyczy → tokeny akcji → limity zlecenia mailowego → outbox, z pominięciem nieobecnych rodzajów. Każdy punkt użycia musi stosować wspólną kolejność.
- Challenge jest zużywany w tej samej transakcji co wydanie sesji lub dowodu; link zużywa challenge i recent-proof razem z przypięciem Google. Rollback nie zostawia połowy połączenia. Nieudana walidacja nie tworzy metody, sesji ani potwierdzenia adresu.
- Dołączenie zwiększa `credentials_revision`, unieważniając stare dowody związane z poświadczeniami, odwołuje pozostałe sesje/retry i zwiększa wersję bieżącej z wymianą refresh zgodnie z F-003. Nie zmienia `User.id`, hasła ani adresu aplikacji. Zawiadomienie trafia do trwałego outboxu w tej transakcji; wysyłka poza nią.
- Constraint `google_id` rozstrzyga równoległe próby na różnych kontach; obsługa konkretnego naruszenia unikalności wymaga rollback/savepoint, nie dalszego używania uszkodzonej transakcji.
- Utrata odpowiedzi po linkowaniu mogła nastąpić po sukcesie. Klient nie ponawia mutacji w ciemno: reauth dotychczasową metodą albo właśnie dołączonym Google i odczyt `/me`. Dane offline zachowują właściciela. Nie przechowujemy ponownie tokena Google tylko dla retry.
- Limity challenge/login/recent-auth/link, ochrona przed masowym tworzeniem rekordów, wspólny magazyn, timeouty i retencja są zależnością [F-004/T-003](../../F-004-email-i-hasla/tasks/T-003-odpornosc-auth.md). Bez ich konkretnego kontraktu ten task nie jest `ready`.

### 5. Android, UX i wydanie

- Dedykowany przycisk korzysta z `GetSignInWithGoogleOption` i nonce od serwera; bottom sheet pozostaje opcjonalny, nie dodajemy automatycznego logowania przy wejściu na ekran. Link i recent-auth są wyłącznie świadomą akcją, bez automatycznego wyboru konta.
- Przed dołączeniem UI podaje adres konta aplikacji, wyjaśnia dodanie metody bez zmiany adresu, odwołanie innych sesji i brak scalenia. Użytkownik potwierdza obecne hasło, wybiera Google. Inne Google w recent-auth daje możliwość wybrania właściwego, nie zmianę konta aplikacji.
- Stany: początek → wymagane potwierdzenie adresu/hasła → wybór Google → oczekiwanie API → sukces/konflikt/reauth/awaria. Wygaśnięcie challenge/dowodu prowadzi do nowej próby; nie ma pętli automatycznych prób.
- Anulowanie selektora wraca neutralnie do poprzedniego ekranu. Brak kont/konieczność uwierzytelnienia obsługuje dedykowany flow Google. Brak sieci/awaria usług pokazują ponowienie; nie udają złego hasła. Nie wykonujemy żądania końcowego po anulowaniu.
- Oddzielne operacje repozytorium dla login/link/recent-auth. Żadna próba link/recent-auth ani jej błąd nie wywołuje `beginNewSession()` / `clearAll()`. Nową parę tokenów bieżącego właściciela zapisujemy atomowo według F-003, bez czyszczenia profili/kolejki.
- `clearCredentialState()` przy świadomym zakończonym logout po rozstrzygnięciu niewysłanej pracy z F-003. Nie przy anulowaniu, błędzie link/recent-auth ani odnowieniu sesji; nie oznacza odłączenia Google. Awaria czyszczenia ma jawne raportowanie i nie unieważnia już wykonanego logout serwera.
- Wszystkie komunikaty w 17 locale; autofill/menedżer haseł, czytnik ekranu, fokus i duży tekst. Bez hardkodowanych adresów/kont operatora w przykładach i fixture.
- Przed wymuszeniem nonce/recent-auth: addytywne modele/migracja, zgodny Android, komplet sesji/weryfikacji oraz kontrolowane przełączenie wszystkich replik. Stare `google_id` zachowujemy; brak historycznego dowodu adresu nie staje się automatycznie verified.
- OAuth: Web client ID plus Android client z właściwym application ID i podpisem debug / release / Play App Signing; upload key nie zastępuje podpisu dostarczanego testerom. Ostateczny dowód to instalacja/aktualizacja z Play na rzeczywistych urządzeniach, nie sam sideload.

### 6. Testy i blokady ready

- Izolowane testy bez prawdziwych tokenów operatora: podpis/algorytm/audience/issuer/sub/iat/exp/nonce, granice TTL, brak konfiguracji, rotacja/cache kluczy i awaria transportu. Atrapy HTTP/klucze syntetyczne, bez produkcyjnego `tokeninfo`.
- PostgreSQL: dwie konsumpcje challenge/proof (jeden sukces), rollback, równoległe nowe konta i linkowanie tego samego `sub` do różnych ID; link kontra reset/zmiana adresu/refresh. Brak przywrócenia odwołanej sesji i brak częściowego zawiadomienia.
- Gmail/Workspace/zewnętrzna skrzynka, prawdziwe/fałszywe `email_verified`, zgodny/różny adres aplikacji, zmiana adresu u Google. `sub` wygrywa nad adresem; nie przejmuje innego ID przez kolizję e-maila.
- Link z różnym adresem zachowuje bibliotekę i adres aplikacji, odnawia bieżącą sesję, odwołuje drugą i zleca jeden mail. Już istniejące powiązanie/Google zajęte nie zmieniają danych ani sesji.
- Macierz dowodów: hasło nie dodaje hasła Google-only, Google nie zmienia istniejącego hasła, dowód jednej akcji/sesji nie działa dla innej; brak aktualnego dostępu do starej skrzynki nie blokuje zatwierdzonej zmiany adresu z poprawnym dowodem tożsamości.
- Android: brak/wiele kont, anulowanie, błędna tożsamość, timeout, utrata odpowiedzi po commit i restart z niewysłanym outboxem. Weryfikacja wywołań API i braku kasowania danych, nie tylko screenshot.
- Integracja: limiter/cleanup F-004/T-003, recent-proof T-004/T-005, sesja i ekran F-003/F-006, nowy ID/certyfikat i migracja F-002/T-001. [Commit/journal F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#6-atomowość-i-wspólny-kontrakt-operacji-konta) wymaga trwałego minimalnego intentu `google_linked`/revisions przed finalnym powiązaniem; nie wysyła Google sub/tokena do dziennika. Restore recovery nie wydaje zwykłej sesji na cofniętym powiązaniu.
- Przed ukończeniem implementacji: powyższe testy, UI strings przez istniejące CI, rzeczywiste powiadomienie i scenariusze na podpisie Play. Brak realnego testu Play oznacza brak końcowej akceptacji.

### Źródła techniczne

- [Google — weryfikacja ID tokena i wiarygodność adresu](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
- [Android — Credential Manager / Sign in with Google](https://developer.android.com/identity/sign-in/credential-manager-siwg-implementation): osobny button flow, nonce i logout.
- [google-auth — walidacja i cache certyfikatów](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html).

## Kryteria i weryfikacja

- [ ] Nieprawidłowy token/audience/issuer/czas odrzucany; brak wymaganej konfiguracji nie osłabia weryfikacji.
- [ ] Równość e-maili nie wystarcza do nieuprawnionego połączenia istniejących kont.
- [ ] Po zmianie adresu aplikacji stare podłączone Google loguje do tego samego ID, nie nadpisuje adresu i nie potwierdza innej skrzynki; kolizja powiązań jest kontrolowanym konfliktem.
- [ ] A-06/A-07: nowe/powracające/Google-only/e-mail, kolizja adresów, brak/wiele kont, anulowanie, sieć i awaria dostawcy.
- [ ] Anulowanie wraca do formularza bez czerwonego błędu; właściwa biblioteka weryfikacji produkcyjnej i testy API/klienta.
- [ ] Końcowa macierz przeszła na rzeczywistym buildzie z Play, nie tylko debug.

**Poza zakresem:** zastępowanie Credential Manager bez potrzeby, samodzielne odłączanie/podmiana metod, scalenie dwóch istniejących kont i zmiana istniejącego hasła dowodem Google. **Wynik weryfikacji:** przegląd kodu/dokumentacji i kompletny projekt wspólnych kontraktów; bez implementacji, runtime, konfiguracji OAuth i operacji na produkcji.

## Postęp

- Reguła zaufania do adresu Google (Gmail albo `hd`, `email_verified`, zgodny bieżący adres) działa już w `/auth/google` jako część bramki F-004/T-002 (krok 4). Ustawia weryfikację tylko dla nowego konta i powracającego `sub`; zewnętrzny adres dostaje mail weryfikacyjny.
- Reszta tego taska jest nadal otwarta: `google-auth` zamiast tokeninfo, wymagane `aud`/nonce, 409 zamiast automatycznego łączenia po adresie.
