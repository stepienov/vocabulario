# T-004 · Zmiana adresu e-mail

**ID:** `E-001/F-004/T-004` · **Status:** `done` · **Priorytet:** P0 przed pierwszą zewnętrzną betą.  
**Feature:** [E-mail i hasła](../README.md). **Źródło:** [decyzje z 17.11.2026](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md); rozszerzenie pierwotnego zakresu, nie nowy numer B-*.

**Zmiana decyzji 21.11.2026:** funkcję wycofano z aplikacji i publicznych endpointów. Zmiana adresu wymaga utworzenia nowego konta. Poniższy opis zachowano wyłącznie jako historię wcześniejszej implementacji.

## Uzgodniony rezultat

Użytkownik sam zmienia adres konta już w pierwszej becie, po potwierdzeniu tożsamości i nowego adresu. Nie traci ID konta, postępu, profili ani biblioteki.

**Decyzja z 17.11.2026:** zmieniamy adres aplikacji, nie Google. Podłączone Google pozostaje i loguje do tego samego ID, również dla Google-only. Jeśli hasło istnieje, po zakończeniu zmiany używa nowego adresu. Późniejsze logowanie Google nie nadpisuje adresu aplikacji ani nie potwierdza automatycznie innej skrzynki. Wspólny kontrakt i S-04/S-05/S-11/S-12: [polityka konta](../README.md#zatwierdzona-polityka-konta--17112026).

**Dalsze zatwierdzone reguły:** po skutecznym przełączeniu adresu odwołujemy wszystkie sesje aplikacji, także bieżącą; użytkownik loguje się ponownie, bez utraty outboxu. Dostęp do starej skrzynki nie jest wymagany, jeżeli użytkownik ponownie potwierdzi tożsamość hasłem lub podłączonym Google oraz potwierdzi nową skrzynkę. Przy zmianie potwierdzonego adresu na stary adres wysyłamy zawiadomienia o rozpoczęciu i zakończeniu; nie wymagamy kliknięcia. Przy korekcie niezweryfikowanego adresu ich nie wysyłamy. Sama otwarta sesja ani kontakt ze wsparciem nie zastępują dowodu tożsamości.

## Proponowany kontrakt zmiany i korekty adresu

Projekt wykonawczy; decyzje produktu dla tego przebiegu zatwierdzone zbiorczo 17.11.2026 w rejestrze F-001. Pozostaje przegląd techniczny i zależności, nie ponowny wybór zachowania produktu.

### 1. Warunki i dane

- Jedna wspólna normalizacja adresów dla register/login/reset/Google/zmiany: walidacja `EmailStr`, usunięcie białych znaków wyłącznie na brzegach adresu i lowercase całego zwalidowanego adresu, zgodnie z obecnym loginem. Nie usuwamy kropek/`+tag`, nie scalamy domen ani aliasów. Hasła nie są trimowane.
- Przed migracją sprawdzić istniejące adresy pod kątem konfliktów po normalizacji. Konflikt blokuje automatyczne przepisanie danego zestawu; bez scalania i bez usuwania kont. Unikalność w bazie musi dotyczyć tego samego klucza co walidacja, również dla równoległych register/Google/zmian.
- `account_email_changes`: UUID PK, `user_id` FK CASCADE, `request_id` UUID, `request_fingerprint` CHAR(64) obejmujący cel i hash użytego dowodu, `mode` (`change`, `correction`), `new_email` VARCHAR(320), związane `email_revision`/`credentials_revision`, `state` (`pending`, `confirmed`, `cancelled`, `replaced`, `expired`), UTC created/expires/finished. Unikalne `(user_id, request_id)`; częściowy unikalny indeks jednego `pending` na użytkownika.
- `mode` ustala serwer: `correction` tylko gdy bieżący adres nie ma dowodu weryfikacji, w pozostałych przypadkach `change`. Obie operacje wymagają świeżego dowodu tożsamości i potwierdzenia nowej skrzynki; korekta nie jest niezabezpieczonym `PATCH /me`.
- `account_action_tokens` otrzymuje nullable FK `email_change_id` CASCADE; purpose `change_email` wymaga tego powiązania. Token to wspólne 32 losowe bajty/hash z T-002. Dowód jest związany z konkretną zmianą, celem i rewizjami, nie tylko adresem z JSON.
- TTL zmiany i jej pierwszego linku: 24 h. Kolejny link resend nie żyje dłużej niż sama zmiana; nie przedłuża jej terminu. Cel nie jest rezerwowany globalnie — ostateczna unikalność jest sprawdzana przy potwierdzeniu.
- Do potwierdzenia aktywny pozostaje dotychczasowy adres, hasło i Google. Zweryfikowane konto może normalnie korzystać; niezweryfikowane pozostaje ograniczone do allowlisty F-004. Sam request nie zmienia `User.email`, statusu weryfikacji ani sesji.
- Zatwierdzone: nowy poprawnie uwierzytelniony request zastępuje wcześniejszy `pending` i unieważnia wyłącznie jego linki/maile. Resend tej samej zmiany nie unieważnia wcześniejszych linków; nieważne/błędne żądanie niczego nie zastępuje.

### 2. Wspólny recent-auth

[F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md#proponowany-kontrakt-techniczny-google-i-recent-auth) proponuje jednorazowy dowód `change_email` ważny 5 minut, związany z właścicielem, sesją i rewizjami. Hasło albo świeża odpowiedź aktualnie podłączonego Google na serwerowy nonce; nie zwykły access token ani równość adresów. Dowód zużyć atomowo przy rozpoczęciu zatwierdzonej zmiany adresu. Osobny link potwierdzający nową skrzynkę ma własny czas życia i rewizje określone tutaj; nie przedłużamy recent-auth przez resend ani nie używamy go ponownie.

Przy finalnym potwierdzeniu linkiem nie wymagamy wciąż aktywnej sesji ani ważności 5-minutowego recent-auth zużytego na starcie; inaczej nie działałoby potwierdzenie na komputerze. Wymagamy niezmienionych rewizji, istnienia konta i aktywnej zmiany. Reset/zmiana/dodanie hasła lub dołączenie Google unieważniają oczekującą zmianę przez rewizję poświadczeń. Usunięcie konta uniemożliwia zakończenie; zwykły logout nie jest anulowaniem rozpoczętej zmiany.

### 3. API

Prefiks `/api/v1`; dostęp zalogowany obejmuje też niezweryfikowane konto.

| Endpoint | Body / dostęp | Wynik |
|---|---|---|
| `POST /auth/email-change/request` | Aktywna sesja, `new_email`, `recent_auth_token`, UUID `request_id` | 202: `change_id`, `status=pending`, `new_email`, UTC `expires_at`, `resend_available_at`; zapis zmiany i outboxu |
| `GET /auth/email-change` | Aktywna sesja | 200 `{"change":null}` lub ostatnia zmiana: ID, mode, new_email, status, expires_at, resend_available_at, delivery_status i delivery_delayed według T-002 |
| `POST /auth/email-change/{id}/resend` | Aktywna sesja właściciela, `{}` | 202 z aktualnym terminem ponowienia; nowy dowód tego samego celu/zmiany, bez nowego recent-auth i bez zmiany adresata |
| `POST /auth/email-change/{id}/cancel` | Aktywna sesja właściciela, `{}` | 200 `{"status":"cancelled"}`; pending → cancelled, unieważnienie linków i niewysłanych maili potwierdzających |
| `POST /auth/email-change/confirm` | Publiczny, `{"token":"..."}` | 200 `{"status":"email_changed","requires_login":true}`; bez tokenów sesji i bez logowania WWW |

- Dokładne ponowienie requestu z tym samym `request_id`, właścicielem i wejściem zwraca tę samą zmianę i jej aktualny stan, bez ponownego maila/zużycia dowodu. Powiązać zapis z hashem wejścia i użytym dowodem; zmienione wejście z tym samym ID daje 409 `request_id_conflict`. Najpierw sprawdzić aktywną sesję. Po restarcie klient odczytuje status, nie zapisuje sekretu recent-auth tylko dla retry.
- Cancel już anulowanego/zastąpionego/wygasłego żądania jest bezpiecznym no-op z rzeczywistym statusem. Potwierdzonego adresu nie cofa: 409 `email_change_completed`. Obcy/nieistniejący ID: 404 `email_change_not_found`. Anulowanie wymaga sesji właściciela, ale nie ponownego hasła; nie zmienia poświadczeń i nie odwołuje sesji.
- 409 `email_unchanged` dla tego samego znormalizowanego adresu; 409 `email_unavailable` dla zajętego, bez informacji o właścicielu/metodach; 410 `email_change_expired`; 409 `email_change_inactive` dla zastąpionego/anulowanego procesu.
- Błędy tokena i recent-auth jak T-002/F-005; walidacja adresu 422 bez sekretów w odpowiedzi. Konflikt/limit/błąd nie zużywa poprawnego recent-auth ani nie zastępuje poprzedniej zmiany.
- Limity i wyliczenie terminów są wspólne z T-003, nie trzy różne implementacje dla request/resend/weryfikacji.

### 4. Atomowość i zawiadomienia

- Request: rewalidacja sesji/dowodu i rewizji pod wspólną blokadą użytkownika, sprawdzenie celu i limitów, zastąpienie poprzedniego pending według wybranej polityki, zużycie recent-auth, zapis nowego procesu/tokena/outboxu w jednej transakcji. Sieciowa wysyłka poza nią.
- Wygasły lub niezgodny z rewizjami `pending` przy nowym żądaniu zostaje najpierw zakończony jako expired/cancelled pod tą samą blokadą. GET może wyliczyć taki rzeczywisty stan bez mutacji; nie pokazuje nieaktualnego linku jako aktywnego i nie wymaga czekania na cleanup dla nowego żądania.
- Confirm: lookup właściciela po hashu tokena, potem użytkownik → sesje/retry → zmiana → tokeny → outbox. Ponownie sprawdzić rewizje, czas, pending, cel i unikalność adresu. Atomowo zapisać `User.email`, zwiększyć `email_revision`, ustawić `email_verified_at`, oznaczyć proces/token jako zakończone, unieważnić pozostałe linki starego adresu i odwołać wszystkie sesje/retry.
- Równoległy konflikt unikalności na nowym adresie daje kontrolowane `email_unavailable` po właściwym rollback/savepoint, nigdy scalenie, częściową zmianę albo nieobsłużone 500. Równoległe confirm/cancel/request rozstrzyga ta sama blokada użytkownika.
- Zmiana nie przepisuje `user_id`, profili, postępu, hasła i `google_id`. Samo potwierdzenie nowej skrzynki nie tworzy metody hasłowej dla Google-only.
- Dla zwykłej zmiany potwierdzonego adresu zawiadomienia na stary adres przy starcie i ukończeniu pozostają zatwierdzone. Nie zawierają pełnego nowego adresu, kodów, hasła ani linku pozwalającego przejąć/cofnąć konto; kierują do pomocy i istniejącego bezpiecznego odzyskiwania.
- Zatwierdzony wyjątek: przy korekcie niezweryfikowanego adresu nie wysyłamy tych zawiadomień na potencjalnie cudzą skrzynkę z literówką. Potwierdzenie trafia wyłącznie na nowy adres. To nie zwalnia z dowodu tożsamości.
- Brak dostarczenia zawiadomienia nie cofa już zatwierdzonej zmiany i nie wymaga dostępu do starej skrzynki. Stan dostarczenia/alerty operatora obsługuje trwały outbox T-002.

### 5. Android, WWW i testy

- UI: adres bieżący → nowy adres → dowód hasła/Google → ekran oczekiwania z dokładnym celem i terminem, resend/anuluj/pomoc. Korekta dostępna także na bramce weryfikacji. Przed wysłaniem jasno pokazujemy, że adres zmieni się dopiero po kliknięciu i konieczny będzie ponowny login.
- WWW/App Link `/account/change-email#token=...`: najpierw ekran jawnego potwierdzenia, potem POST; bez mutacji GET, sesji WWW, trackingu i zapisu tokena w historii/logach według T-002. Wynik nie musi pokazywać adresu konta.
- Link A otwarty przy sesji B wykonuje wyłącznie operację A po jawnej zgodzie; nie przełącza B, nie czyści jego danych i nie wysyła jego outboxu. Powrót A wymaga loginu do tego samego ID. Po utracie odpowiedzi klient odczytuje stan lub próbuje loginu nowym adresem/Google, nie zakłada porażki.
- Status odczytujemy przy wejściu/powrocie do ekranu i po przycisku, bez nowego pollingu. Brak sieci nie usuwa oczekującego procesu ani lokalnych danych. Użyty/wygasły/zastąpiony link ma osobny komunikat i drogę do aktualnego stanu.
- Testy PostgreSQL: dwa cele walczące o ten sam adres, dwa potwierdzenia, confirm kontra cancel/nowy request/reset, rollback outboxu, idempotency requestu, obcy ID, granice TTL i rewizji. Porażka nie zużywa niewłaściwego dowodu ani nie gubi danych.
- Testy Android/WWW: literówka, zewnętrzne Google z innym adresem, brak starej skrzynki, niedostarczone zawiadomienie, restart, drugi telefon/komputer, inne lokalne konto, autofill, duży tekst/czytnik i wszystkie 17 locale.

## Zależności i integracja

- [E-001/F-003/T-001 · Sesje backendu](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md).
- [E-001/F-004/T-002 · Poczta/tokeny](./T-002-poczta-i-odzyskiwanie.md).
- [E-001/F-005/T-001 · Google](../../F-005-google/tasks/T-001-google-i-laczenie.md) — wspólny kontrakt tożsamości, bez cyklu końcowych akceptacji.
- [E-001/F-003/T-002 · Sesja Androida](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md) i [E-001/F-006/T-001 · Moje konto](../../F-006-zarzadzanie-kontem/tasks/T-001-moje-konto.md) — wspólna integracja, ekran może powstawać wcześniej.

## Kryteria do rozwinięcia w konkretne testy

- [ ] Żaden niepotwierdzony nowy adres nie zastępuje starego; dwa równoczesne potwierdzenia nie obchodzą unikalności.
- [ ] Stary/użyty/wygasły link ma kontrolowany wynik, ponowienie nie uszkadza konta.
- [ ] Zmiana nie tworzy drugiego konta, nie gubi danych ani uprawnień i nie przejmuje innego konta.
- [ ] Po zmianie adresu działają hasło z nowym adresem i dotychczasowe Google; Google nie przywraca starego adresu aplikacji. Zweryfikowany inny adres Google nie weryfikuje nowego adresu aplikacji.
- [ ] Po potwierdzeniu nowego adresu wszystkie stare access/refresh są odwołane. Brak dostępu do starej skrzynki nie blokuje poprawnie uwierzytelnionej zmiany; sama sesja bez ponownego uwierzytelnienia nie wystarcza.
- [ ] Zawiadomienia o rozpoczęciu i zakończeniu trafiają na stary potwierdzony adres; przy korekcie niezweryfikowanego nie są wysyłane. Brak potwierdzenia ze starego adresu nie jest warunkiem anulującym zmianę.
- [ ] Każdy wariant metod logowania i sesji ma zatwierdzoną macierz, testy z PostgreSQL, klienta i realnego dostarczenia/otwarcia linku.

**Integracja:** limiter/retencja T-003, sesja i [commit/journal F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#6-atomowość-i-wspólny-kontrakt-operacji-konta), release F-002/T-001. Finalne przełączenie adresu dopiero po trwałym intent/revisions F-008/T-003; po restore stara skrzynka nie staje się automatycznie zaufana. Reguły zastępowania/powiadomień pozostają. **Wynik weryfikacji:** kompletny projekt przebiegów/API/integracji; bez implementacji, dostarczenia poczty i runtime.
