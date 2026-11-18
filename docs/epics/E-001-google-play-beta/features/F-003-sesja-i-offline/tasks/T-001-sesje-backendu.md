# T-001 · Odwoływalne sesje backendu

**ID:** `E-001/F-003/T-001` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Sesja i offline](../README.md). **Źródło:** B-02; F-06/F-16 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Wprowadzić serwerowy cykl życia sesji: bezpieczne przechowywanie sekretów refresh, rotacja, odwołanie bieżącej/wszystkich sesji i jednoznaczne zachowanie access tokenów. Uzgodnić retry i równoległy refresh przed wyborem mechanizmu. Startup produkcji odrzuca niebezpieczną konfigurację, zamiast osłabiać auth.

**Warunek startu:** [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md); ustalona zgodność ze starszym klientem.

## Zatwierdzona polityka haseł i sesji

Wspólny kontrakt: [F-004 — polityka konta](../../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026).

- Reset hasła odwołuje wszystkie dotychczasowe sesje aplikacji, także na urządzeniu otwierającym link; ponowne uwierzytelnienie nie kasuje niewysłanej pracy.
- Zmiana hasła w ustawieniach odwołuje pozostałe sesje. Bieżące urządzenie zachowuje dostęp dopiero przez bezpieczne odnowienie po skutecznej zmianie; wybór bieżącej sesji nie może opierać się na dowolnym ID przesłanym przez klienta.
- Odwołanie dotyczy autoryzacji aplikacji, nie odłączenia Google. Po resecie nadal można ponownie zalogować się właściwym podłączonym Google.
- Odwołana sesja nie uprawnia do nowych żądań chronionych. UI wykrywa to przy kontakcie z API/refresh; bez serwerowego push nie obiecujemy natychmiastowej zmiany ekranu na drugim telefonie offline.
- Przed `ready` opisać atomowość zmiany hasła i sesji, równoległy refresh, rozpoczęte już żądania/zadania, utratę odpowiedzi oraz aktualizację tokenów bieżącego klienta. Samo czekanie na wygaśnięcie starego refresh nie spełnia odwołania.

- Skuteczna zmiana adresu aplikacji odwołuje wszystkie sesje, także bieżącą; ponowny login używa nowego adresu/hasła lub podłączonego Google.
- Dodanie pierwszego hasła do Google-only odwołuje pozostałe sesje i odnawia bieżącą, bez odłączenia Google.

## Proponowany kontrakt techniczny sesji

**Stan:** projekt wykonawcy po przeglądzie kodu z 17.11.2026, do uzgodnienia z zależnymi taskami. To nie wynik implementacji ani status `ready`. Zatwierdzone reguły biznesowe powyżej nie są propozycją.

### 1. Stan obecny i miejsca integracji

- [Auth API](../../../../../../backend/app/api/v1/auth.py) wydaje tokeny bez rekordu sesji; refresh sprawdza JWT i użytkownika, nie poprzednią rotację. Nie ma endpointu logout.
- [Security](../../../../../../backend/app/core/security.py) zapisuje tylko `sub/type/exp`. [Konfiguracja](../../../../../../backend/app/core/config.py) ma 30 minut access i 30 dni refresh; nowy refresh ponownie dostaje pełne 30 dni. Nie zmieniamy tych domyślnych okresów w tym tasku.
- [Deps](../../../../../../backend/app/core/deps.py) ma dwie ścieżki autoryzacji; jedna zwraca samo ID bez odczytu użytkownika. Nowy wspólny kontekst sesji musi obsłużyć obie.
- Chronione routery wymagające kontroli integracji: [auth/me/profiles](../../../../../../backend/app/api/v1/auth.py), [learning](../../../../../../backend/app/api/v1/learning.py), [imports](../../../../../../backend/app/api/v1/imports.py), [sync](../../../../../../backend/app/api/v1/sync.py), [devices](../../../../../../backend/app/api/v1/devices.py), [admin logs](../../../../../../backend/app/api/v1/admin_logs.py). Publiczne health/meta nie dostają przypadkiem obowiązku logowania. Panel administracyjny ma osobny zakres, nie przebudowujemy jego sesji.
- Migracje realizuje [apply_schema](../../../../../../backend/app/db/migrations.py), z idempotentnym DDL i blokadą replik. Nie zakładamy nowej infrastruktury migracyjnej tylko dlatego, że pakiet Alembic jest w zależnościach.
- Android ma już [blokadę refresh](../../../../../../android/app/src/main/java/com/vocabulario/app/data/api/TokenRefresher.kt), ale czyści pamięć także po błędach przejściowych i używa asynchronicznego [zapisu tokenów](../../../../../../android/app/src/main/java/com/vocabulario/app/data/local/TokenStore.kt). To integracja T-002, nie powód do drugiego niezależnego klienta auth.

### 2. Dane i format tokenów

Jedna sesja oznacza jedno skuteczne logowanie na instalacji, nie profil językowy i nie adres e-mail. Kolejne logowanie może utworzyć nową sesję. Stałym właścicielem jest `users.id`.

**Nowa tabela `auth_sessions`:**

| Pole | Typ / reguła |
|---|---|
| `id` | UUID, PK, losowane po stronie serwera |
| `user_id` | UUID, wymagany FK do `users.id`, `ON DELETE CASCADE`, indeks |
| `version` | BIGINT, wymagane, początkowo 1; zwiększane przy odnowieniu po operacji bezpieczeństwa, nie przy zwykłym refresh |
| `refresh_token_hash` | 64 znaki hex SHA-256 dokładnego refresh tokena; wymagane, porównanie odporne na różnice czasu |
| `created_at`, `refreshed_at` | TIMESTAMPTZ, UTC; utworzenie i ostatni skuteczny refresh/odnowienie |
| `expires_at` | TIMESTAMPTZ, UTC; zgodne z końcem aktualnego refresh, przesuwane przy jego rotacji |
| `revoked_at` | TIMESTAMPTZ nullable; ustawienie jest nieodwracalne dla danego rekordu |
| `revocation_reason` | VARCHAR(32) nullable; `logout`, `password_reset`, `password_change`, `password_added`, `email_changed`, `refresh_reuse`, `account_deleted`; bez swobodnego tekstu |

Indeksy: `user_id`, `expires_at` i częściowy `user_id WHERE revoked_at IS NULL`. Nie zbieramy IP, modelu telefonu ani fingerprintu na zapas. Hasło użytkownika nie służy do hashowania tokenów.

Access i refresh pozostają podpisanymi JWT, ale dostają wymagane `v=2`, UUID `sub`, UUID `sid`, dodatni `sv` równy wersji sesji, losowy UUID `jti`, `iat`, `exp`, `type`. Access i refresh mają różne `jti`; nie mogą ponownie wyjść identyczne przy logowaniu w tej samej sekundzie. Dozwolony algorytm pochodzi wyłącznie z konfiguracji serwera, nie z dowolnej deklaracji klienta. `iss=vocabulario-api`, `aud=vocabulario-android`; walidacja obu. Każde środowisko ma osobne sekrety.

`sub` nie zmienia się po zmianie adresu. JWT nie jest źródłem aktualnego e-maila, roli ani stanu weryfikacji. Nie zapisujemy surowego refresh w tabeli sesji ani logach. Krótkotrwały szyfrowany wyjątek dla ponowienia opisuje punkt 4.

### 3. API sesji

Prefiks wszystkich ścieżek: `/api/v1`. Istniejące register/login/google zachowują swoje nazwy; po prawidłowym uwierzytelnieniu tworzą rekord sesji i wydają nowy format w jednej transakcji. Zasady weryfikacji i łączenia kont należą do F-004/F-005; samo wdrożenie tej tabeli nie naprawia automatycznego łączenia po adresie.

**Wspólna odpowiedź `TokenResponse`, HTTP 200:**

```json
{
  "access_token": "<access JWT>",
  "refresh_token": "<refresh JWT>",
  "token_type": "bearer",
  "user_id": "<UUID>",
  "session_id": "<UUID>",
  "expires_in": 1800
}
```

`expires_in` to pozostały czas access w sekundach, wyliczony z konfiguracji/wystawionego tokena, nie niezależna stała; także przy zwrocie poprzedniej pary w retry. Klient używa `user_id` do kontroli właściciela, nigdy do nadawania sobie uprawnień. Odpowiedzi zawierające tokeny: `Cache-Control: no-store`; brak tokenów w URL.

| Endpoint | Wejście | Sukces / skutek |
|---|---|---|
| `POST /auth/refresh` | JSON: `refresh_token: string`, `request_id: UUIDv4` | 200 z `TokenResponse`; rotacja tylko jednej sesji, zachowane `sid` i `sv` |
| `POST /auth/logout` | JSON: `refresh_token: string`; access nie jest wymagany, bo mógł wygasnąć | 204 bez treści; odwołanie wyłącznie sesji udowodnionej refresh tokenem |
| `GET /me` | Bearer access | Zachowane dotychczasowe dane użytkownika; sprawdzenie aktywnej sesji. Dodatkowe pola konta/weryfikacji określa F-004/F-006 |

Logout aktywnej sesji wymaga aktualnego, poprawnego refresh (hash, właściciel, wersja, podpis i terminy). Ponowienie podpisanym, niewygasłym tokenem tej samej już odwołanej sesji zwraca 204 bez ponownego skutku. Stary token z poprzedniej rotacji nie może odwołać nadal aktywnej sesji. Brak rekordu dla poprawnie podpisanego tokena można zakończyć 204 — nie ma już sesji do odwołania. Niepoprawny podpis/typ/format/wygaśnięcie daje 401, a brak wymaganych pól 422.

Nie dodajemy publicznego endpointu listy urządzeń ani „logout all” w UI. Operacje zbiorcze są wewnętrznym kontraktem dla procesów konta.

Zatwierdzony lokalny logout offline nie oznacza odwołania na serwerze. [T-002](./T-002-sesja-androida.md) trwale oddziela zakończenie dostępu na telefonie od zaszyfrowanego zlecenia odwołania. Worker może użyć wyłącznie dowodu zapisanej sesji A, bez Bearer później zalogowanego B. Przy utraconej odpowiedzi refresh stosuje ten sam retry input/ID, a odzyskaną parę wyłącznie do logout. 401 starego refresh w logout nie jest automatycznie potwierdzeniem odwołania; nie luzujemy sprawdzania hash ani nie dodajemy odwołania po samym `session_id`.

**Błędy:** zachować format [api_error](../../../../../../backend/app/core/http_errors.py): `{"detail":{"code":"...","message":"..."}}`. UI mapuje `code`, nie wyświetla technicznego tekstu jako lokalizacji.

| Status / code | Znaczenie / zachowanie klienta |
|---|---|
| 401 `not_authenticated` / `invalid_token` | Brak/poprawność access; bez pętli ponawiania tego samego żądania |
| 401 `session_upgrade_required` | Poprawny stary JWT bez protokołu v2; ponowne logowanie, nigdy czyszczenie outboxu |
| 401 `session_revoked` / `session_expired` | Definitywna utrata tej sesji; reauth tego samego właściciela |
| 401 `invalid_refresh_token` | Błędny refresh; brak nowych tokenów, reauth |
| 409 `refresh_conflict` | Niezgodne ponowienie/równoległość; odczytaj najnowszy stan lokalnego pojedynczego refresh, nie wylogowuj wszystkich kont |
| 403 `email_verification_required` | Uwierzytelnienie działa, uprawnienie do pełnego użycia nie; przejście do weryfikacji, nie do destrukcyjnego logout |
| 403 `terms_acceptance_required` | Ważna sesja, brak wymaganego dowodu warunków/18+ z F-007/T-003; legal gate bez refresh-loop, odwołania sesji i kasowania pracy |
| 403 `restore_recovery_required` | Cofnięty/niejednoznaczny stan po restore F-008/T-003; brak zwykłej sesji/nauki, świeży nadal zaufany dowód lub wsparcie. Nie reset do potencjalnie starej skrzynki |
| 403 `account_deletion_pending` | Potwierdzona tożsamość w procesie F-006; blokada nauki/sync, stan procesu/cofnięcie, bez kasowania danych grace |
| 401 `account_deleted` | Wyłącznie poprawny stary dowód i marker z F-006; dotyczy tego samego owner, nie generic brak User i nie dane innego konta |
| 422 | Niepoprawne pola; brak zmiany sesji |
| 429 | Limit z F-004/T-003, `Retry-After`; nie kasuj tokenów |
| 426 `app_update_required` | Minimalna zgodna wersja F-002/T-001; aktualizacja/pomoc, bez wymazania Room |
| 503 `backup_protection_active` / `ai_budget_exhausted` / `ai_budget_unavailable` | Przejściowa ochrona F-008, nie odwołanie sesji; retry według wskazówek, zachowane kolejki. Brak AI nie blokuje niezależnej nauki |
| 5xx / timeout / błąd sieci | Stan przejściowy; zachowaj dane/tokeny i identyfikator ponowienia, bez pozornego sukcesu |

Awaria PostgreSQL nie jest 401 ani zgodą na pominięcie sprawdzenia sesji; jawny 5xx i standardowy log techniczny bez poświadczeń.

### 4. Rotacja i bezpieczne ponowienie

Projekt: trwały identyfikator operacji po stronie klienta i krótki, szyfrowany wynik po stronie PostgreSQL. Nie wystarcza sam mutex w jednym procesie Androida, bo proces może umrzeć po zapisie serwera, ale przed zapisaniem odpowiedzi.

1. T-002 trwale zapisuje losowy `request_id` powiązany z aktualną parą tokenów **przed** wysłaniem refresh. Ponowienie po timeout/restart używa tego samego ID i tokena. Nie generuje kolejnego ID po każdym błędzie sieci.
2. Serwer waliduje podpis/typ/v2/terminy. W transakcji blokuje najpierw wiersz użytkownika, potem sesję; ponownie sprawdza właściciela, wersję, odwołanie i termin.
3. Dla aktualnego refresh generuje nową parę, aktualizuje hash/terminy i zapisuje wynik retry atomowo. Odpowiedź dopiero po commit.
4. Dla identycznego retry może zwrócić dokładnie poprzednią parę przez **maksymalnie 5 minut od pierwszego sukcesu**, ale tylko jeśli sesja nadal jest aktywna, ma tę samą wersję i hash wynikowego refresh nadal jest aktualny. Termin wyniku to minimum z 5 minut, `exp` wynikowego access i refresh; nigdy nie odtwarzamy wygasłego access.
5. To samo `request_id` z innym wejściem, albo wynik retry, który został już zastąpiony nowszą rotacją, daje 409 bez wystawienia kolejnej pary. Niedawno zużyty token z innym ID także daje 409, bez automatycznego kasowania legalnej sesji.
6. Poprawnie podpisany, niewygasły refresh tej samej wersji, który nie jest aktualny i nie mieści się już w znanym oknie retry, oznacza replay: odwołanie **tej** sesji, 401 `session_revoked`, bez globalnego logout innych urządzeń. Błędny podpis/wersja nie jest podstawą do odwołania cudzej aktywnej sesji.
7. Jeśli odpowiedź przepadła i klient nie odzyska jej w oknie 5 minut, ma jawną drogę reauth bez utraty danych. Nie obiecujemy nieograniczonego w czasie odtworzenia sekretu.

Sprawdzenie zajętości `(session_id, request_id)` i zgodności wejścia następuje przed nową rotacją. Nie wolno najpierw wygenerować/zapisać nowej pary, a dopiero po naruszeniu unikalności wykrywać ponownego użycia ID.

**Tabela `auth_refresh_retries`:** `session_id` FK CASCADE + `request_id` UUID jako złożony PK; `session_version` BIGINT, `input_token_hash` CHAR(64), `output_token_hash` CHAR(64), `response_ciphertext` BYTEA, `created_at`/`expires_at` TIMESTAMPTZ. Wszystkie wymagane; indeks `expires_at` oraz indeks `(session_id, input_token_hash)` do wykrycia niedawnego zużycia.

Szyfrowanie gotową biblioteką: Fernet z `cryptography`, osobny `AUTH_REFRESH_RETRY_KEY`, nigdy klucz JWT ani hasło użytkownika. Zależność jest obecnie przechodnia przez `python-jose[cryptography]`; przy bezpośrednim użyciu trzeba zadeklarować ją wprost w istniejącym manifeście, nie pisać własnej kryptografii. Wszystkie repliki używają tego samego klucza danego środowiska; jego brak/błąd blokuje start, bez losowania innego na każdy restart.

Przed zwróceniem odszyfrowanego wyniku ponownie sprawdzić jego `sub/sid/sv`, typy/terminy i zgodność wynikowego refresh z zapisanym hashem. Błąd odszyfrowania lub niespójny rekord to jawny 5xx i log bez sekretów, nie wydanie innej pary ani wyłączenie walidacji.

Po 5 minutach wynik nie jest wydawany niezależnie od tego, czy fizyczne sprzątanie już nastąpiło. Odwołanie/odnowienie bezpieczeństwa usuwa retry danej sesji w tej samej transakcji. Proponowaną retencję i częstotliwość cleanup opisuje [F-004/T-003](../../F-004-email-i-hasla/tasks/T-003-odpornosc-auth.md#4-techniczna-retencja-auth-i-kolejność-prac); wymagają wspólnego przeglądu z F-007, nie ponownego projektowania w tym tasku. Nie uruchamiamy nowej usługi ani pollingu Androida.

### 5. Autoryzacja każdego żądania

- Jeden request-scoped kontekst FastAPI: poprawny JWT access + join aktywnej sesji z istniejącym użytkownikiem. `sub/sid/sv`, `revoked_at`, `expires_at` i access `exp` muszą pasować. Nie ufać roli ani adresowi z tokena.
- Obie istniejące zależności korzystają ze wspólnego wyniku; najwyżej jeden odczyt sesja/użytkownik na żądanie, niezależnie od liczby kart. Bez cache między żądaniami, który opóźniałby odwołanie. Sam kontekst JWT w middleware logów nie jest autoryzacją.
- Oddzielić uwierzytelnienie od zgody na pełne użycie. `/me`, logout i uzgodnione operacje weryfikacji/odzyskiwania muszą działać dla niezweryfikowanej tożsamości. Chronione operacje nauki/importu/sync wymagają dodatkowej bramki F-004. Dokładna allowlista i własność jej pól są warunkiem integracji, nie dowolnym wyjątkiem w każdym routerze.
- Dodatkowy legal gate [F-007/T-003](../../F-007-prywatnosc-i-wsparcie/tasks/T-003-warunki-i-informacje-prawne.md): register zapisuje potwierdzenia atomowo z User, stare konto wymaga ich jawnie. `/me` i `/me/legal-acceptance` dostępne przy ważnej sesji także bez weryfikacji/warunków; pomoc/prawa/usuwanie zachowują własne dowody. Lifecycle i ważność sesji mają pierwszeństwo, potem bramka adresu i warunków; żadna akceptacja nie nadaje brakującego uprawnienia.
- Centralna allowlista `require_identity` bez dostępu do nauki: `/me`, refresh/logout, status/resend weryfikacji, legal/current/acceptance oraz własne endpointy korekty/zmiany adresu, resetu/zmiany/dodania hasła i Google challenge/recent-auth/link **z ich właściwymi dodatkowymi dowodami**. Pozostałe account/privacy/delete/support WWW mają własny kontrakt publicznego dowodu. `require_study_access` dodaje email+legal dla profili, biblioteki, sync, practice i jobs; brak wyjątków w każdym callerze. Brak weryfikacji nie uprawnia do nauki po samym Google linku.
- Dodatkowo egzekwować lifecycle z [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md): pending/deleting nie otrzymują zwykłej sesji ani nauki/sync; dedykowany dowód usunięcia/cofnięcia nie jest obejściem weryfikacji. Po poprawnym dowodzie można zwrócić ograniczony `account_deletion_pending`; `account_deleted` wymaga wiarygodnego markera, nie samego braku User.
- Po commit odwołania nowa autoryzacja odrzuca stare access **i** refresh, bez czekania 30 minut. Żądanie autoryzowane przed commit może zakończyć już przyjętą pracę; nie deklarujemy cofania wykonanych zapisów ani anulowania wszystkich zadań AI po zmianie hasła.
- Nowe operacje bezpieczeństwa muszą ponownie sprawdzić kontekst pod blokadą użytkownika, aby równoległy reset nie został pominięty. Zadania już przyjęte zachowują właściciela `user_id`; usunięcie konta i anulowanie jego pracy definiuje F-006/T-002.

### 6. Atomowość i wspólny kontrakt operacji konta

Nowy kod usług sesji powinien korzystać z istniejącego `AsyncSession`; helper nie wykonuje samodzielnego commit w środku większej operacji. Stała kolejność blokad: użytkownik → jego sesje w kolejności ID → powiązany stan retry. Login/Google/refresh i operacje bezpieczeństwa stosują tę samą kolejność; ponownie sprawdzają dowód uwierzytelnienia po uzyskaniu blokady.

| Operacja właścicielska | Ta sama transakcja co zmiana danych konta |
|---|---|
| Zwykły login / Google | Nowa sesja, po ponownej walidacji aktualnego stanu konta |
| Reset hasła — F-004/T-002 | Zużycie dowodu resetu, zapis hasła, odwołanie wszystkich istniejących sesji i usunięcie ich retry; bez automatycznego `TokenResponse` |
| Zmiana hasła — F-004/T-002 | Zapis hasła, odwołanie innych sesji, zwiększenie wersji bieżącej, wymiana jej refresh i usunięcie starego retry; zwrot nowej pary |
| Dodanie hasła — F-004/T-005 | Jak odnowienie powyżej, ale tylko przy braku hasła i właściwym dowodzie Google; Google pozostaje |
| Dodanie Google — F-005/T-001 | Dowód obu tożsamości i zużycie challenge/recent-auth, przypięcie Google, zwiększenie rewizji poświadczeń, odwołanie pozostałych sesji i odnowienie bieżącej; adres aplikacji pozostaje |
| Potwierdzona zmiana adresu — F-004/T-004 | Zużycie dowodu, przełączenie adresu/weryfikacji i odwołanie wszystkich sesji/retry; wynik zmiany prowadzi do nowego loginu |
| Przyjęcie usuwania — F-006/T-002 | Odwołanie wszystkich sesji/retry, lifecycle revision i blokada grace w jednej transakcji; dane zachowane 7 dni |
| Cofnięcie usuwania — F-006/T-002 | Poprawny intent zarezerwowany przed granicą; active dopiero po trwałym journal F-008/T-003, nowa lifecycle revision; stare sesje odwołane, potrzebny nowy login |
| Fizyczne usunięcie — F-006/T-002 | Po grace dane aktywne do kolejnych 7 dni, sesje/retry podlegają CASCADE; brak nowego konta pod starym ID |

Przy odnowieniu bieżąca sesja pochodzi ze zweryfikowanego kontekstu/recent-auth, nie z dowolnego `session_id` w JSON klienta. Stare access tej sesji są nieważne po zwiększeniu wersji. Równoległy refresh/login ze starym dowodem nie może odtworzyć dostępu po operacji.

Wspólny projekt [Google/recent-auth](../../F-005-google/tasks/T-001-google-i-laczenie.md#proponowany-kontrakt-techniczny-google-i-recent-auth) rozszerza kolejność blokad o recent-proof → challenge Google → zmiana adresu → proces usunięcia konta, jeśli dotyczy → tokeny akcji → buckety limitów zlecenia mailowego → outbox, zawsze po użytkowniku i sesjach/retry. Nieobecne w danej operacji rodzaje pomijamy; w obrębie rodzaju stały porządek ID. Dowody są związane z wersją sesji i rewizjami konta; nie stanowią zamiennika access/refresh ani automatycznego uprawnienia po zwykłym loginie. Rezerwacje limitów prób z T-003 są osobną krótką transakcją przed tymi blokadami.

Zapis zlecenia zawiadomienia i mechanizm jego ponawiania należą do kontraktu poczty F-004/T-002. Wysyłka sieciowa nie może być wykonywana pod blokadą DB ani udawać rollbacku już zatwierdzonego hasła/adresu.

**Nadrzędna integracja odtwarzania:** [F-008/T-003](../../F-008-jakosc-i-operacje/tasks/T-003-backup-rejestr-i-odtwarzanie.md) dodaje niezależny intent/revisions **przed** finalnym commit resetu/zmiany/dodania hasła, link Google i potwierdzonej zmiany adresu. Obejmuje wszystkie odpowiednie ścieżki F-004/T-002/T-004/T-005 i F-005/T-001, nie sam panel konta. Publikacja poza blokadami; powrót z HTTP ponownie sprawdza dowody/revisions/pending intent, finalne zużycie dowodu i zmiana/sesje/mail/terminalny outbox pozostają atomowe. Jeśli magazyn nie potwierdził intentu, jawny błąd, brak zmiany poświadczenia/sukcesu. Bramka nie wykonuje dodatkowego LLM.

`security_change_pending` blokuje tylko konkurencyjne zmiany bezpieczeństwa tego User; nie jest nowym prawem dostępu. Docelowy PHC hasła może być przechowany wyłącznie w krótkim lokalnym rekordzie intentu do 10 min (ten sam Argon2, bez plaintext), nigdy w S3/logu; replay body sprawdza się bez utrwalania szybkiego SHA hasła. Przy wznowieniu dowody nadal muszą być ważne. `security_applied/aborted` domyka proces według F-008.

Po utracie odpowiedzi zmiany/dodania hasła klient może wymagać reauth nowym hasłem lub podłączonym Google; nie wskrzesza starej pary i nie ponawia w ciemno operacji mutującej. Dane offline zostają. Dokładny komunikat i odtworzenie procesu należą do T-002 Androida i właściwego taska F-004.

### 7. Migracja i zgodne wydanie

1. Przygotować i zweryfikować kopię/odtworzenie na izolowanej bazie syntetycznej; żadnych testowych TRUNCATE na danych użytkowników.
2. Migracja addytywna w istniejącym `apply_schema`: nowe modele/tabele/indeksy, bez przepisywania `users.id`, postępu i bez „odtwarzania” sesji z nieznanych starych JWT. Wielokrotne wykonanie i dwa równoczesne starty muszą być bezpieczne.
3. **Przed egzekwowaniem** nowego auth dostarczyć kompatybilnego Androida: trwały właściciel outboxu, reauth bez czyszczenia Room, nowe pola refresh/odpowiedzi i rozpoznawanie wymaganej weryfikacji/aktualizacji. Odbiór wersji i przygotowanie starych instalacji wymagają dowodu, nie założenia.
4. Przełączenie produkcji jest osobnym zleceniem: obsługa JWT v2 na wszystkich replikach, następnie spójne egzekwowanie. Bez mieszanki akceptacji legacy/v2. Procedurę bridge/stary debug/nowy pakiet i minimum określa [F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md), środowiska/maintenance [F-008/T-002](../../F-008-jakosc-i-operacje/tasks/T-002-srodowiska-i-konfiguracja.md). Nie wymaga to drugiej migracji sesji.
5. Stare poprawnie podpisane, niewygasłe JWT bez v2 dostają `session_upgrade_required`; nie są automatycznie wymieniane na nową sesję, bo obchodziłoby to odwołanie. Rozpoznanie starego formatu sprawdza jego podpis/typ/terminy, ale nie wymaga nieistniejących w nim `aud/iss`; nigdy nie daje autoryzacji. Token deklarujący v2 musi spełniać cały nowy kontrakt. Błędny token nadal jest `invalid_token`. Starszy klient nie omija reguły po stronie serwera.
6. Wycofanie wdrożenia nie może polegać na powrocie do bezwarunkowej akceptacji starych JWT. Zatrzymanie wydania/poprawka zachowuje nowe ograniczenia i dane.

Produkcja/staging: niebezpieczny lub niewprowadzony jawnie `jwt_secret`, algorytm inny niż zatwierdzony HS256, niepoprawne okresy i brak klucza retry blokują start przed uruchomieniem zadań w tle. Walidacja ma obejmować rozpoznany tryb środowiska, tak aby literówka nie wyłączała ochrony. Sekret JWT: co najmniej 32 losowe bajty; testy używają jawnych oddzielnych wartości testowych, nie konfiguracji operatora.

### 8. Testy wykonawcze i mierzalne wyniki

Backend: nowy skupiony moduł testów sesji pod istniejącym [backend/tests](../../../../../../backend/tests/), z [pg_client/pg](../../../../../../backend/tests/conftest.py). Obecne [fabryki auth](../../../../../../backend/tests/pg_factories.py) tworzą access bez sesji — dostosować je i bezpośrednich zależnych użytkowników; nie osłabiać produkcyjnej autoryzacji dla wygody starych testów.

| Przypadek | Wymagany wynik |
|---|---|
| Login dwa razy w tej samej sekundzie | Różne sesje i `jti`, poprawny właściciel |
| Jeden refresh | Stary refresh nie rozpoczyna nowej rotacji; nowy działa, `sid` stałe |
| Dwa refresh równolegle, ten sam ID | Jeden commit rotacji, obie odpowiedzi zawierają tę samą parę |
| Utrata odpowiedzi/restart, retry w 5 minut | Ta sama para bez dodatkowej rotacji i wydłużenia okna retry |
| Retry z innym wejściem/ID lub po kolejnej rotacji | Właściwy 409, brak ujawnienia aktualnych tokenów i niezamierzonego globalnego logout |
| Retry na granicy 5 minut / replay po oknie | Kontrolowany zegar; brak wydania wygasłego wyniku, odwołanie tylko właściwej sesji przy replay |
| Logout i ponowienie | 204; stare access/refresh odrzucone w nowym żądaniu |
| Reset / zmiana adresu przy dwóch sesjach | Obie odwołane, także access; nowe normalne logowanie nadal działa |
| Zmiana / dodanie hasła przy dwóch sesjach | Bieżące nowe tokeny działają, stare tej sesji i druga sesja nie; Google pozostaje |
| Refresh/login kontra reset lub odnowienie bezpieczeństwa | Kontrolowane bariery transakcyjne PostgreSQL; żaden stary dowód nie odtwarza unieważnionego dostępu |
| Rollback zmiany hasła/adresu lub zapisu retry | Brak połowicznej zmiany sesji i brak wydania niezatwierdzonych tokenów |
| Obie zależności auth oraz admin | Odwołanie działa niezależnie od ścieżki; pomiar jednego odczytu kontekstu na request, nie na kartę |
| Stary JWT, zły typ/podpis/`aud`/`iss`/UUID/wersja, brak użytkownika | Ustalony 401 bez nieobsłużonego 500 i bez odwołania cudzej sesji |
| Timeout/5xx/429 i niespójny zapis klienta | Brak utraty outboxu; testy T-002 Androida, bez atrapowego sukcesu |
| Migracja i konfiguracja | Powtórne DDL i równoczesny start bez utraty danych; niebezpieczna konfiguracja nie uruchamia zadań |
| Logi | Brak surowych/szyfrowanych poświadczeń, haseł, tokenów Google, nagłówka Authorization i body auth; zdarzenia opisują kod i żądanie |

Po implementacji najpierw wybrany moduł testów sesji, potem testy dotkniętych fabryk/routerów oraz istniejące `python scripts/ci_check.py`. PostgreSQL wyłącznie lokalny `TEST_DATABASE_URL` zakończony `_test` zgodnie z guardem repo. Brak PostgreSQL i `skip` nie stanowią dowodu zaliczenia wyścigów.

### 9. Przegląd kompletności projektu

- [x] F-004/F-005 definiują API recent-auth, dowody, zużycie/unieważnianie i własność pól; F-008/T-003 dodaje journal przed finalnym commit.
- [x] Allowlista identity/study powyżej, odpowiedzi i limity F-004/T-003, dodatkowe kody F-008 jawnie rozdzielone od logout.
- [x] T-002 Androida opisuje trwałego właściciela, refresh/retry/atomowy zapis, reauth i logout bez sieci oraz barierę opóźnionych wyników. To sprawdzenie kompletności projektu, nie zaliczenie implementacji.
- [x] Retencja F-004/T-003 i F-007, konfiguracja F-008/T-002 oraz ochrona przy restore T-003 zapisane.
- [x] Kolejność starych instalacji/replik i minimum F-002/T-001, bez przywracania legacy JWT.
- [x] Spójność projektu z offline/kontem/legal i operacjami ma wspólne kontrakty; wykonane testy pozostają poniżej.

## Kryteria i weryfikacja

- [ ] Refresh/rotacja/logout/reset mają testy endpointów z izolowanym PostgreSQL.
- [ ] Ponowienia i równoległe żądania nie zostawiają przypadkowo ważnego starego refresh ani nie blokują legalnego klienta poza ustalonym kontraktem.
- [ ] Logout odwołuje bieżącą sesję; reset i usunięcie konta wszystkie odpowiednie sesje, a zmiana hasła pozostałe z odnowieniem bieżącej. Odwołane access/refresh nie pozwalają na nowe żądania zgodnie z kontraktem.
- [ ] Dwie sesje i kontrolowany równoległy refresh sprawdzają różnicę reset vs zmiana hasła; utrata odpowiedzi nie przywraca odwołanych sesji.
- [ ] Stare tokeny odrzucane zgodnie z kontraktem; niebezpieczny sekret/brak wymaganej konfiguracji blokuje start produkcji.

**Poza zakresem:** lista urządzeń w UI, migracja całego dostawcy auth, nowe funkcje nauki i wdrożenie bez osobnego zlecenia.  
**Wynik weryfikacji:** sprawdzono punkty kodu i kompletność projektu/integracji. Nie ma implementacji, testów runtime ani zaliczenia kryteriów produktu.
