# T-002 · Poczta, weryfikacja i odzyskiwanie hasła

**ID:** `E-001/F-004/T-002` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [E-mail i hasła](../README.md). **Źródło:** B-05; F-01/F-10 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Dostarczyć weryfikację adresu, ponowienie, „Nie pamiętam hasła”, reset i zmianę hasła: API, wiadomość, link i Android. Tokeny jednorazowe, wygasające, bezpiecznie przechowywane; limity i neutralne odpowiedzi bez ujawniania istnienia adresu. Google-only ma zrozumiałą ścieżkę, nie fikcyjne hasło lokalne.

**Decyzja z 17.11.2026:** nowe konto e-mail potwierdza adres przed pełnym korzystaniem. Przedtem są dostępne ponowienie wiadomości, korekta adresu, wyjście, pomoc i dokumenty. Google nie dostaje dodatkowego maila, gdy prawidłowo zweryfikowane dane dostawcy pozwalają uznać adres.

**Dalsze decyzje z 17.11.2026:** dotychczasowe konta e-mail bez dowodu weryfikacji także potwierdzają adres przed dalszym pełnym użyciem, bez dodatkowego okresu przejściowego. Reset hasła odwołuje wszystkie sesje aplikacji; zmiana hasła w ustawieniach odwołuje pozostałe i odnawia bieżącą. Żaden z tych procesów nie kasuje postępu/outboxu.

**Dalsza decyzja:** link działa także na komputerze/telefonie bez aplikacji — potwierdzenie adresu i ustawienie nowego hasła mają prostą stronę HTTPS. Na telefonie z aplikacją może otworzyć się właściwy ekran Androida. To obsługa jednorazowych operacji, nie portal konta WWW; link nie loguje do biblioteki.

Korekta literówki przed pierwszą weryfikacją oraz zmiana już potwierdzonego adresu to różne operacje i muszą mieć oddzielne warunki. Sam formularz nie może być jedyną blokadą korzystania z usług przez niezweryfikowane konto.

Wspólna [polityka i S-01…S-14](../README.md#scenariusze-akceptacyjne-polityki) rozróżnia reset, zmianę i dodanie pierwszego hasła. Google-only otrzymuje osobny proces [T-005](./T-005-dodanie-hasla.md), nie hasło nadawane przez anonimowy reset. Dla transakcji odwołania/odnowienia obowiązuje proponowany [kontrakt sesji](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#proponowany-kontrakt-techniczny-sesji); tutaj doprecyzować dowody jednorazowe i trwałe zlecenia zawiadomień.

**Warunki startu:** [E-001/F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md), [E-001/F-004/T-001](./T-001-haszowanie-hasel.md) oraz decyzje o poczcie/momencie weryfikacji z [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md).

## Proponowany kontrakt techniczny poczty i odzyskiwania

Projekt wykonawczy z 17.11.2026, do uzgodnienia z zależnymi taskami. Parametry techniczne są propozycją, nie dowodem działania ani zmianą statusu na `ready`. Kierunek dostawcy został zaakceptowany warunkowo w punkcie 8; nie oznacza zgody na płatne usługi lub zakup domeny.

### 1. Stan kodu i odpowiedzialność

- [Auth API](../../../../../../backend/app/api/v1/auth.py), [schematy](../../../../../../backend/app/schemas/__init__.py) i [User](../../../../../../backend/app/models/__init__.py) nie mają obecnie procesów weryfikacji/resetu, dowodów jednorazowych ani stanu potwierdzenia adresu.
- Wyszukanie istniejącego kodu SMTP/wysyłki/weryfikacji w backendzie nie znalazło mechanizmu do ponownego użycia. Korzystamy z PostgreSQL, istniejącego HTTPX i obecnej ścieżki [migracji](../../../../../../backend/app/db/migrations.py), nie wymieniamy całego auth.
- [spawn_background](../../../../../../backend/app/services/background.py) może pominąć zadanie przy przeciążeniu i nie jest trwałą kolejką. Nie może być jedynym miejscem przechowania wiadomości bezpieczeństwa.
- [Manifest Androida](../../../../../../android/app/src/main/AndroidManifest.xml) nie ma obsługi App Links. Dodanie obsługi linku nie może wywoływać destrukcyjnego początku sesji z [AuthRepository](../../../../../../android/app/src/main/java/com/vocabulario/app/data/AuthRepository.kt).
- Tutaj jest właściciel: dowody e-mail/reset, transport i kolejka wiadomości, weryfikacja adresu, reset oraz zmiana istniejącego hasła. T-004 definiuje zmianę/korektę adresu; T-005 dodanie hasła; F-005 dowód Google/recent-auth; F-007 publiczne strony, a F-003 cykl sesji i trwałe dane Androida.

### 2. Dane i dowody jednorazowe

**Rozszerzenie `users`:**

| Pole | Kontrakt |
|---|---|
| `email_verified_at` | Nullable TIMESTAMPTZ, UTC; dotyczy wyłącznie bieżącego adresu aplikacji |
| `email_revision` | BIGINT NOT NULL DEFAULT 1; zwiększany przy skutecznym przełączeniu adresu, także w uzgodnionym wariancie korekty |
| `credentials_revision` | BIGINT NOT NULL DEFAULT 1; zwiększany przy resecie, zmianie/dodaniu hasła i dołączeniu Google; unieważnia wcześniej wydane dowody zależne od poświadczeń |

Brak dowodu migracyjnego oznacza `email_verified_at=NULL`, nie dzisiejszą datę. `google_id` ani wiek konta nie są dowodem. Uznanie aktualnego adresu z Google wymaga walidacji F-005 i dokładnego dopasowania bieżącego adresu, nie nadpisania go.

**Nowa tabela `account_action_tokens`:** UUID `id` PK, UUID `user_id` FK CASCADE, `purpose` VARCHAR(32), unikalny `token_hash` CHAR(64), BIGINT `email_revision`, BIGINT `credentials_revision`, TIMESTAMPTZ `created_at`, `expires_at`, nullable `consumed_at`/`invalidated_at`. Purpose w tym tasku: `verify_email`, `reset_password`; T-004 korzysta z mechanizmu dla osobnego celu, nie podmienia przeznaczenia istniejącego tokena. Indeksy: `(user_id, purpose)`, `expires_at`.

- Token: 32 kryptograficznie losowe bajty zakodowane base64url, bez danych osobowych. Baza dowodów zawiera tylko SHA-256 tokena; porównanie odporne na różnice czasu. To nie access/refresh JWT.
- Proponowane TTL od utworzenia: weryfikacja **24 godziny**, reset **30 minut**. Wysyłka/ponowienie tego samego maila nie przesuwa terminu.
- Konsumpcja sprawdza cel, bieżące rewizje, czas, brak zużycia/unieważnienia i istnienie użytkownika. Nie używa adresu ani `user_id` podanego przez klienta jako właściciela dowodu.
- Nowe żądanie resetu/resend nie unieważnia samo wcześniejszych poprawnych linków: nie pozwalamy anonimowemu żądaniu stale psuć linku ofiary. Dopiero skuteczny reset/zmiana danych unieważnia stare dowody przez rewizje lub jawne zużycie.
- Reset dotyczy tylko kont z istniejącym hasłem. Google-only nie dostaje hasła przez ten endpoint.
- Zatwierdzone 17.11.2026: skuteczny reset dowodzi posiadania bieżącej skrzynki i w tej samej transakcji ustawia `email_verified_at`, jeśli adres nie był zweryfikowany; nie wysyłamy kolejnego potwierdzenia. Dowód musi odpowiadać bieżącemu adresowi i jego rewizji — stary link po zmianie adresu nie weryfikuje nowej skrzynki. Reset nadal odwołuje wszystkie sesje i nie loguje automatycznie.

Przed mutacją: nieblokujący lookup hasha do ustalenia właściciela, potem kolejność blokad użytkownik → sesje/retry według F-003 → dowody → outbox. Ponowna walidacja dowodu pod blokadą. Helper poczty nie robi niezależnego commit.

### 3. API i odpowiedzi

Prefiks `/api/v1`. Wszystkie błędy w istniejącym formacie `detail.code/message`, bez zwracania tokenów w URL odpowiedzi lub logach.

| Endpoint | Dostęp i body | Sukces |
|---|---|---|
| `POST /auth/email-verification/request` | Aktywna sesja danego konta, JSON `{}` | 202 `{"status":"accepted","retry_after_seconds":60}`; trwałe zlecenie maila dla bieżącego niezweryfikowanego adresu |
| `GET /auth/email-verification/status` | Aktywna sesja, także niezweryfikowana | 200: `email_verified: boolean`, `delivery_status: not_requested/queued/provider_accepted/delivered/failed/unknown`, `delivery_delayed: boolean`, `resend_available_at: ISO-8601 UTC lub null` |
| `POST /auth/email-verification/confirm` | Publiczny; `{"token":"..."}` | 200 `{"status":"email_verified"}`; bez tokenów sesji i automatycznego loginu |
| `POST /auth/password-reset/request` | Publiczny; `{"email":"...","locale":"..."}` | Zawsze taki sam 202 `{"status":"accepted","retry_after_seconds":60}` dla istniejącego/nieznanego/Google-only adresu i limitu adresata |
| `POST /auth/password-reset/confirm` | Publiczny; `{"token":"...","new_password":"..."}` | 200 `{"status":"password_reset","requires_login":true}`; nowe hasło i odwołanie wszystkich sesji atomowo |
| `POST /auth/password/change` | Aktywna sesja; `{"current_password":"...","new_password":"..."}` | 200 `TokenResponse` z F-003; nowe hasło, odwołanie innych sesji i odnowienie bieżącej atomowo |

Weryfikacja już potwierdzonego adresu przy uwierzytelnionym request daje 200 `{"status":"already_verified"}`, bez nowego maila. Publiczny reset nigdy nie zwraca `email_not_found`, `google_only`, flagi `sent` ani stanu dostarczenia konkretnego adresata. Neutralna odpowiedź oznacza przyjęcie żądania, nie gwarancję wysyłki/dostarczenia.

Link resetu wysyłamy tylko dla konta z istniejącym hasłem. Dla nieznanego/Google-only adresu nie wysyłamy fikcyjnego resetu. Każdy publiczny formularz żądania pokazuje tę samą ogólną informację o zakresie resetu i alternatywę „Kontynuuj z Google”, bez wykrywania rodzaju konta.

`email` normalizujemy wspólnie z loginem/rejestracją i T-004; nie usuwamy kropek, `+tag` ani nie utożsamiamy domen dostawców. Hasła podlegają jednemu kontraktowi T-001, bez trimowania i obcinania. `locale` pochodzi z dozwolonego katalogu UI, nie jest dowolną nazwą pliku ani adresem do renderowania. Dla maila uwierzytelnionego język wynika z jawnej preferencji UI, nie z języka nauki.

Zatwierdzone 17.11.2026: zmiana istniejącego hasła w ustawieniach wymaga obecnego hasła i nowego hasła. Zapomniane hasło prowadzi do resetu przez e-mail; świeży dowód Google nie zastępuje obecnego hasła w tej operacji w becie. Konto bez hasła korzysta z osobnego T-005 po wymaganym potwierdzeniu Google i adresu. Nie wolno użyć dodania pierwszego hasła do nadpisania już istniejącego.

| Błąd | Zachowanie |
|---|---|
| 400 `action_token_invalid` | Brak/pomyłka celu/nieważna rewizja; brak zmiany konta |
| 410 `action_token_expired` | Link wygasł; wyjście do nowego żądania |
| 409 `action_token_used` | Brak ponownej mutacji; jasne „link został już wykorzystany”, droga do loginu/statusu |
| 401 z F-003 | Reauth bez kasowania danych; nie dotyczy potwierdzenia publicznym dowodem |
| 403 `current_password_invalid` / `password_not_set` | Dotyczy zalogowanej zmiany hasła, nie ujawnia rodzaju konta anonimowemu żądaniu resetu |
| 422 | Błąd pól/kontraktu hasła, bez zużycia poprawnego dowodu |
| 429 + `Retry-After` | Limit IP lub uwierzytelnionej akcji; brak permanentnej blokady konta |
| 503 `mail_temporarily_unavailable` | Globalnie niedostępne przyjmowanie żądań poczty; dla publicznego resetu decyzja niezależna od istnienia adresu |

Rollback zapisu nowego hasła nie zużywa dowodu i nie odwołuje połowy sesji. Po utracie odpowiedzi sukces mógł już nastąpić: ponowienie może dać `action_token_used`, a użytkownik ma drogę logowania nowym hasłem/Google. Nie generujemy mu drugiego konta.

Pierwsza wiadomość weryfikacji jest automatycznie zlecana wraz z rejestracją e-mail w jednej transakcji z kontem/settings i ograniczoną sesją. Przed zapisem globalna niedostępność skonfigurowanej poczty daje jawne 503, bez częściowego konta. Sukces `TokenResponse` oznacza utworzenie konta i zlecenie maila, nie dostarczenie. Utrata odpowiedzi nie uzasadnia drugiej rejestracji: login/reset odzyskują to samo konto. Przy pierwszym utworzeniu Google-only z zewnętrznym niezweryfikowanym adresem stosujemy tę samą kolejkę/bramkę; wiarygodny Gmail/Workspace zgodny z adresem nie dostaje zbędnego maila. Kolejne logowanie istniejącego konta nie zleca nowego maila automatycznie i nie zależy od dostępności poczty; resend pozostaje osobną akcją.

### 4. Uprawnienia i migracja istniejących kont

Sam access potwierdza tożsamość sesji, nie adres. Wspólny kontekst F-003 pobiera także pola weryfikacji z `User`; nie dodajemy osobnego odczytu na kartę.

- Bez aktywnej sesji: register/login/Google/refresh według swoich dowodów, publiczny reset i potwierdzanie jednorazowego linku, publiczne dokumenty/pomoc. Link nie daje uprawnień do `/me`, nauki ani sync.
- Aktywna niezweryfikowana tożsamość: `/me`, request/status weryfikacji, logout, wymagane operacje potwierdzenia/korekty z T-004, zmiana hasła z dowodem obecnego hasła, dodanie metody z dowodami T-005/F-005, żądanie usunięcia własnego konta z F-006. Żadna z tych operacji nie omija weryfikacji adresu dla pełnego korzystania.
- Profile nauki, biblioteka, nowe wyszukiwanie/AI, importy, praktyka i push/pull danych nauki: 403 `email_verification_required`, dopóki bieżący adres nie ma dowodu. Publiczne meta/health nie zostają zamknięte.
- Administracyjne wyjątki i osobny panel nie mogą przypadkiem stać się ścieżką pełnego użycia zwykłego niezweryfikowanego konta.

Schemat `/me` uzupełnić o `email_verified: boolean` oraz faktyczne `login_methods` (`password`, `google`), wspólnie z F-006/F-005. Nie zwracamy hashy, tokenów i nieudowodnionego adresu Google jako adresu aplikacji. Stan dostarczenia ma osobny endpoint, nie dodatkowy lookup przy każdym chronionym żądaniu.

Pełny kontrakt tożsamości i cache określa [F-006/T-001](../../F-006-zarzadzanie-kontem/tasks/T-001-moje-konto.md). [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) korzysta z tej samej tabeli tokenów/outbox dla request/cancel usunięcia, z osobnymi purpose, lifecycle revision i target deletion ID. TTL dowodu e-mail 30 min, hasła/Google 5 min; cofnięcie nie wykracza poza cancel_until. Worker dopuszcza w grace wyłącznie właściwe linki cofnięcia i zawiadomienia procesu, nie zwykłe stare verify/reset/change-email. Przyjęcie usuwania unieważnia stare linki; cofnięcie ich nie reaktywuje. Wiadomości na niezweryfikowany adres nie są wysyłane.

W istniejącej bazie zachować ID, profile i postęp. Po uzgodnionym przełączeniu brak dowodu wymaga potwierdzenia przed pełnym API. Kolejność wydania bierze się z F-003: najpierw Android z trwałym właścicielem/outboxem i ścieżką weryfikacji, dopiero potem bramka. Weryfikacja na komputerze nie przepisuje lokalnych danych telefonu.

### 5. Linki, przeglądarka i Android

Docelowe ścieżki pod zatwierdzonym `PUBLIC_APP_ORIGIN`:

- `/account/verify-email#token=...`
- `/account/reset-password#token=...`
- `/account/change-email#token=...` — finalny kontrakt zmiany/korekty z T-004; nie używa celu `verify_email`.

Wiadomość zawiera jeden właściwy URL HTTPS i termin ważności, HTML + zwykły tekst, bez skracacza/tracking redirectu. Host pochodzi wyłącznie z konfiguracji, nigdy z `Host`/`redirect_url` dostarczonego przez klienta. Brak dowolnych przekierowań po sukcesie.

GET wyświetla stronę, **nie zużywa dowodu** i nie zmienia hasła/adresu — skanery poczty nie mogą wykonać operacji. Dopiero jawny przycisk wysyła POST. Formularz resetu ma nowe hasło i potwierdzenie, wspiera wklejanie/menedżer haseł; potwierdzenie hasła to walidacja klienta, nie drugi sekret w API.

Token we fragmencie nie trafia do żądania GET/proxy logów. Skrypt własnej strony odczytuje go do pamięci, usuwa fragment przez `history.replaceState` i nie zapisuje w localStorage/analityce. Odświeżenie strony może wymagać ponownego otwarcia maila. POST i body auth nie trafiają do logów. Strona ma `no-store`, `Referrer-Policy: no-referrer`, zakaz ramek i restrykcyjne CSP bez obcych skryptów, fontów i pikseli; brak automatycznego linkowania bibliotek do śledzenia.

Android: Verified App Links tylko dla uzgodnionych hostów/ścieżek, `assetlinks.json` z właściwym podpisem Play (osobno debug/test). Odmowa otwarcia aplikacji i brak instalacji zostawiają działający formularz WWW. Sprawdzić fragment URL w realnym kliencie poczty/App Links; nie zakładać, że dowolny redirect go zachowa.

| Sytuacja | Oczekiwany stan |
|---|---|
| Potwierdzenie na tym samym telefonie | Sukces, odczyt `/me`/statusu przy powrocie lub przyciskiem; bez cyklicznego pollingu |
| Potwierdzenie na komputerze | Adres potwierdzony; jasny powrót do aplikacji. Nie tworzymy sesji WWW ani nowego konta |
| Reset na komputerze | Hasło zmienione, stare sesje odwołane; instrukcja ponownego loginu w aplikacji |
| Link konta A przy otwartym koncie B | Operacja dotyczy wyłącznie właściciela dowodu A; bez przełączania konta/sync/kasowania danych B |
| Link uszkodzony/wygasły/użyty | Czytelny stan, nowe żądanie/pomoc/powrót; bez surowego tracebacku |
| Brak sieci przy POST | Formularz nie udaje sukcesu; po niepewnym resecie ścieżka logowania nowym hasłem, bez nieskończonego submit |
| Brak wiadomości | Sprawdź spam/poprawność adresu, resend po terminie, korekta/pomoc; nie obiecujemy „dostarczono” po samym 202 |

Teksty Androida we wszystkich 17 locale. Proponowany wspólny katalog maili/stron obejmuje te same locale UI; języki dokumentów prawnych pozostają osobnym zatwierdzeniem F-007. Nie kopiować angielskiego jako gotowego tłumaczenia; rzeczywisty przegląd tekstów i dostępności jest warunkiem odbioru.

### 6. Trwałe wysyłanie, retry i zawiadomienia

Nowa tabela `mail_outbox`: UUID PK `id`, nullable UUID `user_id` FK CASCADE dla wiadomości konta, `kind`, opcjonalny FK `action_token_id`, `payload_ciphertext` BYTEA, `dispatch_state` (`queued/leased/accepted/failed/cancelled`), `delivery_state` (`unknown/delivered/bounced/complained`), `attempts`, `next_attempt_at`, nullable `lease_until`, nullable unikalny `provider_message_id`, bezpieczny `last_error_code`, `created_at`/`expires_at`. Indeksy kolejki `(dispatch_state, next_attempt_at)` i `(user_id, kind, created_at)`.

Snapshot zaszyfrowanego payloadu obejmuje odbiorcę, sender/reply-to, język, wersję szablonu i wyrenderowaną treść/link. Inaczej nie da się trwale ponawiać po restarcie mając tylko hash dowodu. Gotowa biblioteka Fernet, odrębny `MAIL_OUTBOX_KEY`, bez sekretu JWT i bez plaintext w kolumnie JSON. Brak/zmiana klucza wymaga kontrolowanej procedury, nie cichego porzucenia wiadomości.

Zapis użytkownika/dowodu i outboxu następuje w jednej transakcji; odpowiedź 202 dopiero po commit. Zawiadomienia o skutecznym resecie/zmianie hasła, dodaniu hasła i rozpoczęciu/zakończeniu zmiany potwierdzonego adresu używają tej samej kolejki. Dla zmiany adresu zachować snapshot starego odbiorcy — nie odczytywać go dopiero po przełączeniu konta. Korekta niezweryfikowanego adresu ma zatwierdzony wyjątek bez zawiadomień na stary adres z T-004.

Dołączenie Google z [F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md) także zleca zawiadomienie na bieżący adres aplikacji w transakcji mutacji; nie tworzy drugiego transportu poczty.

Proponowany worker w istniejącym backendzie, bez Redis/Celery i nowej usługi:

1. Jedna kontrolowana pętla dostarczania na proces, do 5 pozycji na przebieg, budzenie co najwyżej co 30 s i sygnałem nowego zlecenia. To serwerowa obsługa outboxu, nie przywrócenie pollingu nauki/importów lub Androida.
2. Krótki claim PostgreSQL `FOR UPDATE SKIP LOCKED`, lease 60 s; wywołanie HTTP poza transakcją/blokadami użytkownika, limit czasu 12 s. Claim jednej pozycji bez rezerwowania dużej paczki, której lease wygaśnie w oczekiwaniu.
3. Stały klucz dostawcy `auth-mail/<outbox UUID>`, nie nowe ID przy każdej próbie. Payload pozostaje identyczny. Restart/utrata odpowiedzi nie tworzy nowego maila na ślepo.
4. Maksymalnie 6 prób, proponowane terminy od pierwszej: 0/30/120/300/600/1200 s. Dla 429 uwzględnić późniejszy `Retry-After`; nigdy nie wysyłać po wygaśnięciu dowodu. Permanentny błąd konfiguracji/odbiorcy nie ma nieograniczonego retry.
5. Przed wysyłką tokenowego maila sprawdzić, czy dowód/adres/rewizje są nadal aktualne; anulować nieaktualny link w kolejce. Zawiadomienia o poprzednim adresie/haśle nie są anulowane tylko dlatego, że dane właśnie zmieniono.
6. `accepted` oznacza przyjęcie przez dostawcę, nie odbiór w skrzynce. Nie ponawiać maila tylko dlatego, że brak webhooka. Błąd wysyłki nie cofa już zmienionego hasła/adresu; jawny stan, standardowy log i zawiadomienie operatora o awarii.

Dla proponowanego Resend retry z tym samym kluczem działa do 24 h według dokumentacji; nasze próby mieszczą się w tym oknie. Nie obiecujemy ogólnego „exactly once” dla dowolnego dostawcy/SMTP. Zmiana dostawcy wymaga dowodu równoważnej deduplikacji, nie tylko innego URL.

Jeden endpoint `POST /api/v1/auth/mail-events` dla zdarzeń dostawcy, bez sesji użytkownika, ale z weryfikacją podpisu/timestampu **surowego** body przez utrzymywaną bibliotekę Svix; standardowa tolerancja timestampu 5 minut. Błędny podpis/czas daje 400, bez mutacji. Webhook nigdy nie potwierdza adresu ani hasła.

`mail_provider_events`: unikalne `svix-id`, `provider_message_id`, typ zdarzenia i UTC occurred/received; bez body, odbiorcy i linku. Zapis zdarzenia i aktualizacja outboxu w jednej transakcji, odpowiedź 204 po commit; dokładny duplikat to 204 bez ponownego skutku. Gdy webhook wyprzedzi zapis `provider_message_id` po wysyłce, zdarzenie pozostaje do powiązania przy tym zapisie; nie gubimy go przez przedwczesne 204 bez trwałego śladu.

| Resend event | Efekt |
|---|---|
| `email.sent` | dispatch accepted, nigdy sam dowód delivered |
| `email.delivered` | delivery delivered, chyba że jest silniejszy terminalny sygnał |
| `email.delivery_delayed` | delivery delayed; brak ponownej wysyłki przyjętego maila tylko z tego powodu |
| `email.failed`, `email.suppressed` | delivery failed/suppressed; jawna porażka, nie fałszywe delivered |
| `email.bounced`, `email.complained` | delivery bounced/complained; brak automatycznych prób ominięcia blokady odbiorcy u dostawcy |

Rozszerzyć enum delivery o `delayed/failed/suppressed`. Agregacja dla jednego maila jest monotoniczna: complained > bounced > suppressed > failed > delivered > delayed > unknown; spóźniony słabszy event nie wymazuje silniejszego. Nieznany poprawnie podpisany typ jest ignorowany jako jawnie nierozpoznany typ z bezpieczną metryką/logiem, nie jako błąd hasła. Open/click tracking jest wyłączony i zdarzenia te nie mają skutku. Status dla właściciela mapuje terminalne błędy do `failed`, delayed do `provider_accepted` z informacją o opóźnieniu, a delivered nadal nie oznacza kliknięcia ani odczytania.

TTL dowodu nie jest retencją danych dostawcy. Proponowane kasowanie lokalnych payloadów/metadanych określa [wspólna retencja T-003](./T-003-odpornosc-auth.md#4-techniczna-retencja-auth-i-kolejność-prac). `action_token_id` w outboxie ma `ON DELETE SET NULL`; usunięcie sekretnej treści nie może blokować sprzątania dowodu. Los wiadomości już przyjętej przy usunięciu konta i retencja dostawcy należą do F-006/F-007. Token nie może być dopisywany do ogólnego logu na potrzeby diagnostyki.

### 7. Limity i odporność

Reset/zmiana hasła stosuje nadrzędną [kolejność commit/journal F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#6-atomowość-i-wspólny-kontrakt-operacji-konta) oraz F-008/T-003: zdarzenie `account_journal` z revisions w tej samej transakcji co zmiana, bez surowych sekretów w dzienniku i logach. Restore recovery nie wysyła resetu na potencjalnie stary adres. To rozszerzenie wspólnej usługi, nie osobny reset/mail flow.

Proponowane parametry do wspólnego kontraktu T-003, nie trzy osobne mechanizmy w endpointach:

| Ograniczenie | Propozycja |
|---|---|
| Resend weryfikacji | 60 s przerwy, do 3 wiadomości/60 minut na adres, także pierwsza wiadomość rejestracji |
| Publiczny reset | 60 s przerwy, do 3 wiadomości/60 minut na znormalizowany adres |
| Żądania publicznego resetu | 20/15 minut na IP; ten limit może dać 429 |
| Potwierdzenia publicznych dowodów | 30/15 minut na IP; nie odwołuje poprawnych tokenów po zgadywaniu przypadkowych wartości |
| Globalna wysyłka | Proponowany budżet aplikacji: 90 prób API wysyłki / przesuwne 24 h i 2700 / przesuwne 31 dni, dodatkowe ograniczenie zwykłych linków do 70 / 24 h i 2100 / 31 dni; pozostały zapas dla zawiadomień bezpieczeństwa |

Uwierzytelniony resend po przekroczeniu własnego limitu może dostać 429 i rzeczywisty termin ponowienia zgodny ze `status.resend_available_at`. Publiczny reset zachowuje opisany neutralny kontrakt 202 dla limitu adresata; stałe 60 s w odpowiedzi nie jest obietnicą, że wysłano kolejną wiadomość.

Liczniki adresata powstają według tej samej reguły także dla nieznanych/Google-only adresów, przed decyzją o wysyłce. Przekroczenie limitu adresata publicznego resetu daje ten sam 202 i treść, nie sygnał istnienia konta. Nie zapisujemy surowego adresu w kluczu logu ani trwałej listy nieznanych kont. T-003 określa magazyn/retencję liczników, HMAC identyfikatora oraz zaufane proxy/IP; brak zaufania do dowolnego `X-Forwarded-For`.

Publiczna odpowiedź i rozkład czasu nie mogą zależeć od sieci dostawcy: wysyłka jest asynchroniczna. Sprawdzić różnice czasu lookup/zapisu i ujednolicić ścieżkę bez kosztownego hashowania każdego nieznanego adresu; brak twardej obietnicy identycznych nanosekund.

Budżet korzysta z atomowych globalnych bucketów T-003. Konserwatywnie liczymy każdą próbę HTTP wysyłki, również retry i niepewny wynik, choć dostawca może liczyć jedynie nowe wiadomości. Rezerwacja miejsca następuje po claim i zwolnieniu blokady outboxu, tuż przed próbą; nie utrzymujemy blokad DB podczas HTTP. Pozwala to uniknąć przekroczenia bez znajomości kalendarzowego resetu dostawcy i nie udaje bezpłatnej nieskończonej liczby retry.

Przy wyczerpaniu zwykłego budżetu nowe żądania wysyłki dostają globalne 503 `mail_temporarily_unavailable`, niezależnie od istnienia adresu w publicznym resecie. Już przyjęta kolejka czeka do miejsca w budżecie, ale tokenowy mail nigdy nie jest wysłany po TTL. Operacji odzyskania/zmiany hasła nie cofamy z powodu wyczerpania budżetu zawiadomień: zawiadomienie zapisane trwale czeka, ma 24 h TTL i przechodzi w jawne failed/alert, jeśli nie da się go wysłać. Czekanie na budżet nie jest wykonaną próbą HTTP i nie zużywa limitu sześciu prób.

Alert operatora przy 80% każdego globalnego progu i przy wyczerpaniu/terminalnym failure; bez wysyłania lawiny alertów tą samą zablokowaną pocztą. Kanał alertów i konto dostawcy (inne aplikacje także mogą zużyć jego limit) potwierdza F-008/F-007 przed uruchomieniem. Bez automatycznego płatnego planu.

### 8. Dostawca i koszty

**Decyzja właściciela z 17.11.2026:** warunkowo akceptuje Resend Free, jeśli będzie działać z własną domeną, którą dopiero kupi. Warunek jest zgodny z [dokumentacją własnych domen Resend](https://resend.com/docs/dashboard/domains/introduction): domenę można kupić później, a przed rzeczywistą wysyłką trzeba ją dodać i zweryfikować kontrolę przez DNS. Nie trzeba wybierać innego dostawcy tylko dlatego, że domeny jeszcze nie ma.

Kolejność: właściciel wybiera i osobno zatwierdza zakup domeny → konfiguracja DNS/weryfikacja domeny lub subdomeny wysyłkowej → sender i testy dostarczenia. Rekomendowana subdomena do transakcyjnej poczty, np. `auth.example.com`, izoluje cel/reputację od przyszłego marketingu; to przykład, nie wybrana domena. Resend nie rejestruje automatycznie domeny i sam wybór planu nie potwierdza nadawcy.

Konkretną nazwę właściciel poda później; dotychczasowe propozycje nie zostały wybrane. DPA/transfery, konfiguracja limitów i testy pozostają warunkami uruchomienia. Płatny plan nadal wymaga oddzielnej zgody.

Stan sprawdzony **17.11.2026**, źródła poniżej. Ceny w USD z publicznych cenników; waluta rozliczenia, podatki i ostateczne warunki wymagają sprawdzenia przy aktywacji.

| Wariant | Publiczny limit/cena | Ocena dla 5–30 testerów |
|---|---|---|
| **Resend Free — kierunek zaakceptowany warunkowo** | 0 USD/mies., 3000 maili/mies., do 100/dzień; HTTP API, własne domeny, klucze idempotencji | Mały zakres integracji i zwykle wystarczający wolumen; limit dobowy jest realną bramką przy testach/retry/atakach |
| Resend Pro, wyłącznie po osobnej zgodzie | Od 20 USD/mies. za 50 000 maili; nadwyżki według cennika | Nie uruchamiać „na zapas”; opcja, jeśli testy/dobowy ruch przekroczą Free |
| Brevo Free — alternatywa | 0 USD, 300/dzień; oficjalny opis Free wskazuje branding dostawcy i kolejkę po przekroczeniu limitu | Większy limit dobowy, ale trzeba ocenić branding, obsługę opóźnionych linków i deduplikację transportu; nie implementujemy dwóch adapterów |

Przykład budżetu, nie prognoza: 30 osób × 10 wiadomości = 300/miesiąc. Jednego dnia 30 rejestracji + po jednym resecie i po jednym zawiadomieniu o resecie to już 90 maili; resend i pozostałe zmiany mogą przekroczyć 100. QA etapami albo osobno zatwierdzony plan, nie obietnica nieograniczonej darmowej poczty.

Rekomendowana integracja Resend po akceptacji: jeden adapter HTTPX do Send Email, bez zbędnego SDK do samej wysyłki; osobna gotowa biblioteka walidacji webhooków, jeśli potrzebna. Sender z uwierzytelnionej domeny/subdomeny, SPF/DKIM/DMARC, wyłączony open/click tracking, monitorowany reply-to; brak newsletterów/kontaktów marketingowych w tym tasku.

Resend publikuje DPA, a cennik wskazuje domyślną 30-dniową retencję danych usługi. Nie oznacza to przetwarzania wyłącznie w UE ani automatycznej zgodności. F-007 musi sprawdzić umowę, podprocesorów/transfery i faktyczne ustawienia przed zatwierdzeniem. Nie zakładamy konta dostawcy i nie wysyłamy danych testerów podczas przygotowania specyfikacji.

[Weryfikacja F-007](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md) potwierdziła storage USA, wiadomości/logi 30 dni, backupy 7 dni i brak API usuwania pojedynczego maila. Region wysyłki EU nie zmienia lokalizacji storage. Właściciel dopuścił takie usługi poza EOG warunkowo po wymaganej weryfikacji; nie stanowi to akceptacji każdej klauzuli ani automatycznej gwarancji usunięcia poczty w 7+7 dni. Oddzielny monitorowany reply-to/pomoc ma cel pierwszej odpowiedzi człowieka do 2 dni roboczych i wymaga wyboru dostawcy skrzynki.

Źródła:
- [Resend — ceny i ograniczenia](https://resend.com/pricing).
- [Resend — idempotencja, okno 24 h](https://resend.com/docs/dashboard/emails/idempotency-keys).
- [Resend — Send Email](https://resend.com/docs/api-reference/emails/send-email).
- [Resend — weryfikacja webhooków](https://resend.com/docs/webhooks/verify-webhooks-requests).
- [Resend — typy zdarzeń](https://resend.com/docs/webhooks/event-types).
- [Resend — DPA](https://resend.com/legal/dpa).
- [Resend — własne domeny i subdomeny](https://resend.com/docs/dashboard/domains/introduction).
- [Brevo — ograniczenia Free](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan).

### 9. Testy i braki do ready

Konfiguracja wykonawcza: `PUBLIC_APP_ORIGIN` to HTTPS origin bez userinfo/query/fragment/path, a `MAIL_FROM` i `MAIL_REPLY_TO` to poprawne adresy z uzgodnionego nadawcy/kontaktu. Resend: `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`; lokalny payload: osobny `MAIL_OUTBOX_KEY`; limiter: `AUTH_RATE_LIMIT_KEY`. Klucze są niezależne od JWT/refresh-retry i nie trafiają do repo. W trybie produkcyjnym/staging wymagane wartości i klucze muszą przejść walidację startową; w testach izolowane wartości i atrapy. Właściwe DNS/domena, monitoring reply-to i klucze dostawcy są warunkiem uruchomienia, nie wyboru logiki hashowania.

Backend, z izolowanym PostgreSQL i zamrożonym zegarem: poprawny/cudzy cel/wygasły/użyty token, granice TTL, dwie równoczesne konsumpcje (jeden sukces), rollback, reset kontra zmiana adresu/hasła, oba rodzaje kont i rewizje. Ponowienie resetu nie nadaje hasła Google-only, nie tworzy konta, nie wskrzesza sesji.

Dla zatwierdzonych reguł sprawdzić dodatkowo: reset niezweryfikowanego bieżącego adresu jednocześnie ustawia nowe hasło, potwierdza adres i odwołuje wszystkie sesje, bez kolejnego maila weryfikacyjnego ani automatycznego loginu. Reset zweryfikowanego adresu nie zmienia pierwotnego czasu jego potwierdzenia. Rollback lub link sprzed zmiany adresu nie wykonują żadnej z tych mutacji. Konto Google + hasło nie może zmienić istniejącego hasła samym świeżym tokenem Google; poprawne obecne hasło działa, a jego brak prowadzi do resetu, nie do T-005.

Outbox: restart po commit/przed wysyłką, restart po akceptacji przez dostawcę/przed zapisem, dwie repliki i lease, identyczny payload/klucz retry, brak klucza szyfrowania, 429/5xx/permanent failure, limit budżetu, wygaśnięcie przed wysyłką, bezpieczne webhooki/duplikaty/kolejność. Równoległe żądania i ponowienie po utracie 202 nie mogą obchodzić atomowych limitów adresata. Testy automatyczne używają atrap HTTP, nie płatnej/prawdziwej poczty.

Android/WWW: wszystkie stany z tabeli, inny właściciel lokalny, śmierć procesu, cofnięcie/ponowne otwarcie, brak aplikacji, czytnik ekranu/duży tekst, autofill, 17 locale UI. GET ze skanera niczego nie zużywa, fragment/token nie trafiają do URL logów/Referer/analityki.

Osobny smoke przed betą na syntetycznym koncie i rzeczywistych skrzynkach: sender/DKIM/SPF/DMARC, spam, HTML/text, klik na Androidzie z podpisem Play i komputerze, ważność starej sesji po resecie, zawiadomienia i zgłoszenie niedostarczenia. Sam mock i samo API `accepted` nie wystarczają.

- [ ] Domknięte warunki zaakceptowanego kierunku Resend Free: domena/weryfikacja, budżet dzienny/miesięczny i alerty; DPA/transfery/retencja mają właściciela.
- [ ] Spójność opisanej konfiguracji i mapy URL z F-007; języki i hosting uzgodnione. Konkretna domena, sender/reply-to/DNS i klucze to osobna bramka publicznego uruchomienia; brak rzeczywistych sekretów w repo.
- [ ] T-001 hashowania zamyka politykę haseł/migracji; kontrakty recent-auth i T-005 respektują brak zmiany istniejącego hasła samym dowodem Google.
- [ ] Przegląd opisanego T-004 potwierdza jeden mechanizm korekty/zmiany i osobny cel dowodu, bez dwóch sprzecznych procesów.
- [ ] Schematy odpowiedzi/rewizje i allowlista sprawdzone z sesjami, F-005 i ekranem konta; uwzględnione zatwierdzone potwierdzenie bieżącego adresu przez skuteczny reset, bez akceptowania linku sprzed zmiany adresu.
- [ ] Przegląd opisanych webhooków, cleanup/retencji i liczników z T-003/F-007; plan wydania starym klientom nie powoduje utraty postępu/outboxu.
- [ ] Projekt ma przegląd spójności i komplet testów do wykonania; późniejsza implementacja wyłącznie na osobne zlecenie.

## Kryteria i weryfikacja

- [ ] A-01/A-04/A-05: prawdziwe dostarczenie wiadomości i otwarcie linku na urządzeniu.
- [ ] Nieznany/istniejący/Google-only adres, wygasły/użyty/stary link i resend zachowują ustalony kontrakt.
- [ ] Reset odwołuje wszystkie sesje; zmiana hasła odwołuje pozostałe i odnawia bieżącą; reauth nie traci outboxu, powtórne użycie tokena odrzucone.
- [ ] Stare konto bez dowodu weryfikacji przechodzi wymagane potwierdzenie bez utraty ID/profili/postępu/outboxu; bramka obejmuje także starszego klienta/API, bez automatycznego oznaczania jako verified.
- [ ] Brak poczty nie kończy się ślepą uliczką; komunikaty i napisy obejmują 17 locale.
- [ ] Testy API z izolowanym PostgreSQL i kontrolowanym czasem; testy klienta oraz realna skrzynka, nie tylko atrapa.

**Poza zakresem tego taska:** zmiana adresu e-mail jest osobnym [E-001/F-004/T-004](./T-004-zmiana-emaila.md), wymaganym w pierwszej becie. Wspólne mechanizmy poczty/tokenów współdzielimy, nie implementujemy dwa razy. Zakres L podzielić przed kodowaniem w razie potrzeby.  
**Wynik weryfikacji:** przegląd kodu/źródeł dostawców i kompletny projekt z retencją/rollout/journal; brak implementacji, dostarczenia maila i runtime.

## Postęp

**Krok 1 — fundament backendu (zrobiony):**

- Model: `users.email_verified_at` (NULL = brak dowodu; istniejące konta **nie** są automatycznie oznaczane jako zweryfikowane), `email_revision`, `credentials_revision` (domyślnie 1) oraz tabele `account_action_tokens` i `mail_outbox`. Migracja jest addytywna. Sprawdzona dwukrotnie na kopii lokalnej bazy z danymi: rekordy bez zmian.
- [action_tokens.py](../../../../../../backend/app/services/action_tokens.py): 32 losowe bajty; w bazie zapisywany jest tylko SHA-256. TTL: `verify_email` 24 h (wiązany z `email_revision`), `reset_password` 30 min (wiązany także z `credentials_revision`). Zużycie z blokadą wiersza i kodami 400/409/410.
- [mail_outbox.py](../../../../../../backend/app/services/mail_outbox.py): treść szyfrowana Fernetem (`MAIL_OUTBOX_KEY`), claim przez `SKIP LOCKED` z dzierżawą 60 s i maksymalnie 6 prób w oknie ważności. Nieaktualny link jest anulowany przed wysyłką. Klucz idempotencji `auth-mail/<id>`. Worker jest uruchamiany w `lifespan`.
- [mail_transport.py](../../../../../../backend/app/services/mail_transport.py): transport `log` (tylko development/test) i `resend` (`Idempotency-Key`, mapowanie 429/5xx/409/timeout na retry, pozostałe 4xx jako trwały błąd).
- Konfiguracja: `PUBLIC_APP_ORIGIN`, `MAIL_TRANSPORT`, `MAIL_FROM`, `MAIL_REPLY_TO`, `RESEND_API_KEY`, `MAIL_OUTBOX_KEY`. Poza development/test brak lub błąd tych ustawień daje 503 w `/health/ready`, więc **wdrożenie tej zmiany wymaga domeny, konta Resend i zmiennych na Railway**.
- Testy: `test_action_tokens.py`, `test_mail_outbox.py` (m.in. dwa workery nie wysyłają tego samego maila), `test_mail_transport.py`, `test_readiness.py`. Zielone na lokalnym PostgreSQL.

**Krok 2a — reset i zmiana hasła (zrobiony):**

- [mail_templates.py](../../../../../../backend/app/services/mail_templates.py): maile `verify_email`, `reset_password` i `password_changed` w 16 językach interfejsu Androida (tekst + HTML z escapowaniem, `dir="rtl"` dla `ar`). Tag języka normalizowany (`pt-rBR`→`pt-BR`, `de-AT`→`de`, nieznany→`en`).
- [account_recovery.py](../../../../../../backend/app/services/account_recovery.py) i trasy w `auth.py`:
  - `POST /auth/password-reset/request` zawsze zwraca 202. Mail dostaje tylko konto z hasłem, z limitem 60 s przerwy i maksymalnie 3 maili na 60 minut dla adresata. Limity IP i globalne przyjdą w T-003.
  - `POST /auth/password-reset/confirm` jest atomowy: ustawia Argon2id, podbija `credentials_revision` (starsze linki resetu przestają działać), odwołuje wszystkie sesje (`password_reset`) i ustawia `email_verified_at` tylko wtedy, gdy był NULL. Wysyła też mail `password_changed`.
  - `POST /auth/password/change` sprawdza obecne hasło (`current_password_invalid`/`password_not_set` → 403), odwołuje pozostałe sesje (`password_change`), odnawia bieżącą i zwraca nowe tokeny.
  - Język maila: `locale` z żądania resetu, w pozostałych przypadkach `app_lang` aktywnego profilu.
- **Okres przejściowy bcrypt:** `passwords.verify_current_password` sprawdza Argon2 oraz rozpoznany bcrypt (stary weryfikator, w puli wątków). Login i zmiana hasła działają więc dla starych i nowych hashy. Rejestracja nadal zapisuje bcrypt z minimum 8 znaków, dopóki T-001 nie przełączy jej razem z Androidem. Odcięcie bcrypt nastąpi w kroku 7 T-001.
- Testy: `test_mail_templates.py`, `test_account_recovery.py` (neutralne 202, limit, 410/409/400, słabe hasło bez zużycia tokenu, odwołanie sesji, zachowanie `email_verified_at`, zmiana hasła). Zielone na lokalnym PostgreSQL.

**Krok 2b — weryfikacja adresu (zrobiony):**

- Rejestracja e-mail w jednej transakcji tworzy konto, sesję i zlecenie maila `verify_email`. Opcjonalne pole `locale` w `RegisterRequest` określa język maila. Gdy wdrożona poczta jest źle skonfigurowana, rejestracja i publiczny reset dostają 503 `mail_temporarily_unavailable` przed zapisem (`Settings.mail_ready`). Budżet globalny dojdzie w T-003.
- `POST /auth/email-verification/request`:
  - 202, gdy mail został zlecony;
  - 200 `already_verified`, gdy adres jest już potwierdzony;
  - 429 `mail_rate_limited` z `Retry-After` po przekroczeniu limitu adresata (ten sam limit co przy resecie, liczony razem z mailem z rejestracji).
- `GET /auth/email-verification/status` zwraca `email_verified`, `delivery_status` (`not_requested/queued/provider_accepted/delivered/failed/unknown`), `delivery_delayed` i `resend_available_at`. Uwzględnia tylko maile dla bieżącego `email_revision` i robi jeden odczyt z indeksu.
- `POST /auth/email-verification/confirm` jest publiczny, ustawia `email_verified_at` i nie tworzy sesji. Ponowne wysłanie maila nie unieważnia wcześniejszego linku.
- `/me` zwraca dodatkowo `email_verified` i `login_methods` (`password`, `google`). Android ignoruje nieznane pola.
- Konto Google nadal nie dostaje maila ani nie jest uznawane za zweryfikowane. Ocena adresu z Google należy do F-005 i musi być gotowa przed bramką z kroku 4.
- Testy (`test_account_recovery.py`):
  - mail po rejestracji w wybranym języku;
  - 429 z `Retry-After`;
  - potwierdzenie, 409 dla użytego linku i 410 dla wygasłego;
  - `already_verified`;
  - mapowanie stanów dostarczenia;
  - 503 bez zapisu konta.

**Krok 3 — strony WWW linków (zrobiony):**

- Pakiet `backend/app/public_web/`: `GET /account/verify-email` i `GET /account/reset-password` (szablon `account_action.html`, pliki `/account/assets/account.js` i `account.css`). GET tylko wyświetla stronę. Token zużywa dopiero jawny POST z przycisku do istniejących endpointów API. Strona nie tworzy sesji WWW.
- Token jest tylko we fragmencie `#token=`. JS odczytuje go i od razu usuwa z adresu (`history.replaceState`), więc nie trafia do logów, historii ani nagłówka `Referer`. Po odświeżeniu strona prosi o ponowne otwarcie linku z maila.
- Nagłówki: `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `nosniff`, ścisły CSP bez `unsafe-inline` (teksty dla JS jako JSON w `<script type="application/json">`), `noindex`.
- Język: `?lang=` z linku w mailu (linki mają teraz `?lang=<locale>` tego samego maila), potem `Accept-Language`, na końcu angielski. 16 języków w tej samej formie zwracania się co maile; `ar` ma `dir="rtl"`.
- Reset: dwa pola `autocomplete="new-password"`, „pokaż hasła”, sprawdzenie długości (punkty kodowe, jak serwer) i zgodności przed wysłaniem; błąd hasła z serwera (422) zostawia token ważny. Stany: gotowe, 400 nieważny, 409 użyty, 410 wygasły, 429, błąd sieci lub timeout 15 s (przycisk znów aktywny), brak tokenu, brak JS (`<noscript>`). Komunikaty w regionie `aria-live` z fokusem.
- Testy: `test_public_web.py` (nagłówki, brak skryptu inline, wybór języka, RTL, komplet tekstów, pliki statyczne, tylko GET) i asercje `?lang=` w `test_account_recovery.py`. Sprawdzone też w przeglądarce na lokalnym serwerze z `vocabulario_test`: weryfikacja, reset, logowanie nowym hasłem, użyty i nieważny link, błąd sieci, odświeżenie, arabski na ekranie telefonu, brak naruszeń CSP.

**Zostało:** bramka `email_verification_required` (krok 4); Android (krok 5); limity T-003 i webhooki Svix z `mail_provider_events` (krok 6); domena `PUBLIC_APP_ORIGIN` (F-007/T-004), prawdziwa skrzynka i urządzenie.