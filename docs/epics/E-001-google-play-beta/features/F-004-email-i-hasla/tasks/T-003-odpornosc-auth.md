# T-003 · Odporne formularze i API auth

**ID:** `E-001/F-004/T-003` · **Status:** `ready` · **Priorytet / rozmiar:** P0 z UX P1 / M.  
**Feature:** [E-mail i hasła](../README.md). **Źródło:** B-10; F-10 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zakres

Obsłużyć konflikt równoległej rejestracji, utratę odpowiedzi po zapisie, spójne kody błędów i ograniczenia prób bez trwałej blokady wywoływanej przez napastnika. Uzupełnić błędy pól, autofill, menedżery haseł, krótsze timeouty i ochronę przed podwójnym submit.

**Start:** [E-001/F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md) i [E-001/F-004/T-001](./T-001-haszowanie-hasel.md). **Integracja:** rozszerzyć o [E-001/F-004/T-002](./T-002-poczta-i-odzyskiwanie.md) i [E-001/F-005/T-001](../../F-005-google/tasks/T-001-google-i-laczenie.md).

Kontrakt bazowy dla poczty: [proponowane limity i odporność T-002](./T-002-poczta-i-odzyskiwanie.md#7-limity-i-odporność). Tutaj zamknąć wspólny magazyn/retencję liczników, interpretację proxy/IP, timing i próby login/register/recent-auth, bez rozbieżnych limitów i bez ujawniania istnienia konta statusem publicznego resetu.

## Proponowany wspólny kontrakt

### 1. Stan kodu i błędy

- [Auth API](../../../../../../backend/app/api/v1/auth.py) rozróżnia publicznie `email_not_found`, `google_login_required` i `wrong_password`; nie ma wspólnego limitera auth. `IntegrityError` jest już używany w tym module, ale rejestracja polega na sprawdzeniu przed insertem.
- [Format błędów](../../../../../../backend/app/core/http_errors.py) zachowujemy: HTTP status i `detail.code/message`. Nie zamieniamy awarii DB/Google/poczty w błędne hasło ani pusty sukces.
- Zatwierdzone 17.11.2026: login hasłowy dla nieznanego adresu, Google-only i złego hasła daje jednolite 401 `invalid_credentials`. Ogólna alternatywa Google i „Nie pamiętam hasła” są widoczne każdemu, bez wykrywania rodzaju konta.
- Dla nieznanego/Google-only wykonujemy w ograniczonej bramce jeden verify z przygotowanym poprawnym hashem syntetycznym tego samego docelowego algorytmu; nie generujemy hasha przy każdym nieudanym loginie. Pomiar timing obejmuje lookup i verify; nie obiecujemy identycznych nanosekund.
- Rejestracja ma kontrolowane 409 `email_unavailable` także dla wyścigu na unikalnym adresie. Obsługa dotyczy nazwanego constraintu i prawidłowego rollback/savepoint, a nie ukrycia każdego `IntegrityError`.
- Błędy walidacji auth nie zawierają pól `input` z sekretami, całego request body, tokenów ani tracebacku. Handler musi objąć także standardowy błąd schematu Pydantic; lokalizowane UI opiera się na kodach/polach, nie surowym komunikacie biblioteki.
- Rejestracja e-mail/Google ma dowód warunków/18+ z [F-007/T-003](../../F-007-prywatnosc-i-wsparcie/tasks/T-003-warunki-i-informacje-prawne.md), atomowo z nowym User. Nieaktualna wersja daje 409 `legal_version_changed`, brak wymaganego potwierdzenia 422; dotychczasowe konto z prawidłowym loginem może wymagać osobnej akceptacji, nigdy błędnego hasła ani utraty danych.

### 2. Magazyn i dokładne limity

PostgreSQL współdzielony przez repliki, bez nowego Redis i bez słownika w pamięci jako jedynej ochrony. Jedna tabela `auth_rate_buckets`: `(scope, subject_hash)` PK, tablica TIMESTAMPTZ udanych rezerwacji miejsca w oknie, `expires_at`. Długość tablicy ograniczona limitem danej reguły; nie budujemy historii wszystkich prób.

- Klucz to HMAC-SHA-256 kanonicznego identyfikatora/IP z osobnym losowym `AUTH_RATE_LIMIT_KEY` co najmniej 32 bajty, z separacją scope. Nie przechowujemy raw adresów/IP w bucketach ani logach. Wszystkie repliki mają tę samą konfigurację i klucz; jego zmiana wymaga kontrolowanego przełączenia, bo zerowanie kluczy nie może być sposobem obchodzenia limitów.
- Przy każdej regule: utworzenie bucketa `ON CONFLICT DO NOTHING`, blokada wiersza, usunięcie próbek o czasie `<= now-window`, sprawdzenie liczby i atomowe dopisanie czasu. Reguły wielokluczowe blokowane w stałym porządku `(scope, subject_hash)`. Zegar UTC bazy; okno przesuwne, nie podwojenie limitu na granicy godziny.
- Rezerwacja limitu żądania jest krótką oddzielną transakcją przed kosztownym verify i nie znika przy rollbacku błędnego loginu. Limity zleceń mailowych zapisujemy razem z tokenem/outboxem i trwałym idempotency requestu, aby retry nie zużywał ich dwa razy; blokady według wspólnej kolejności F-003, po użytkowniku/sesjach/dowodach, przed outboxem. Budżet wywołań dostawcy worker rezerwuje dopiero po zwolnieniu blokady claim outboxu.
- Awaria magazynu daje jawne 503 `auth_temporarily_unavailable`, nie pomijanie limitów. Ograniczenia są czasowe, bez trwałego blokowania konta po nieudanych próbach z obcego IP.

| Zakres | Limit okna przesuwnego |
|---|---|
| Wszystkie publiczne POST auth łącznie, poza webhookiem | 120 / 15 min / IP |
| Login hasłem i zakończenie Google loginu łącznie | 20 / 15 min / IP |
| Login hasłem dla pary IP + znormalizowany adres | 5 / 5 min; nie globalna blokada adresu ze wszystkich IP |
| Rejestracja e-mail | 30 / 60 min / IP |
| Utworzenie challenge Google | 30 / 15 min / IP; również dla zalogowanego klienta |
| Próba recent-auth, obie metody łącznie | 5 / 5 min / sesję; dodatkowo wspólny limit IP kosztownych prób 20 / 15 min |
| Link Google / dodanie hasła / zmiana hasła | 5 / 60 min / użytkownika dla każdej akcji |
| Rozpoczęcie zmiany/korekty adresu | 3 / 60 min / użytkownika; resend dodatkowo według adresata |
| Anulowanie oczekującej zmiany adresu | 10 / 60 min / użytkownika; dokładny retry nie zużywa ponownie limitu mutacji |
| Refresh | 60 / 15 min / sesję; sprawdzony kryptograficznie token, bez hashowania nieograniczonego wejścia |
| Request publicznego resetu / confirm dowodu e-mail | Odpowiednio 20 / 15 min / IP i 30 / 15 min / IP według T-002 |
| Wysyłka linków verify/reset/change-email | 60 s cooldown i 3 / 60 min na adres i cel, w tym pierwsza wiadomość; dla zmiany dodatkowo 3 / 60 min / właściciela łącznie request/resend |

`Retry-After` dla 429 wynika z najpóźniejszego czasu zwolnienia wszystkich blokujących okien/cooldownu, zaokrąglony w górę do sekund, minimum 1. Publiczny reset dla limitu adresata nadal zwraca neutralne 202 i stałe 60 s; nie ujawnia rzeczywistego stanu adresu. `/status.resend_available_at` dla właściciela uwzględnia wszystkie jego blokujące limity.

IP bierze się z peer socket, chyba że peer należy do jawnie zaufanych proxy środowiska. Wówczas parsujemy zweryfikowany łańcuch od prawej, odrzucając jedynie znane zaufane hop-y; nie ufamy pierwszemu dowolnemu `X-Forwarded-For`. IPv4/IPv6 normalizujemy biblioteką adresów. Konkretny kontrakt ingress Railway trzeba potwierdzić przy środowisku testowym F-008, bez zaufania całemu Internetowi lub przypadkowej prywatnej podsieci.

### 3. Formularze, timeouty i retry

- Jedna aktywna operacja submit na formularz; blokada przycisku i submit IME, anulowanie/cofnięcie dostępne. Wpisany e-mail i komunikat zostają; hasło/dowody tylko w pamięci, bez trwałego save-state, logów i crash reportów.
- Proponowany limit całego pojedynczego wywołania auth klienta: 15 s, połączenie 5 s; bez automatycznego powtarzania POST mutujących. Wyjątkiem jest jawny retry z idempotency requestu/refresh z ich kontraktów. Timeout oznacza niepewny wynik, nie potwierdzoną porażkę.
- Po niepewnej rejestracji: próba loginu tym samym adresem i hasłem albo reset, bez tworzenia konta innym adresem automatycznie. Po niepewnej mutacji sesji: reauth/status według F-003. Po niepewnym żądaniu e-mail-change: GET status albo dokładne ponowienie z tym samym request_id.
- Publiczny reset zachowuje neutralną treść także dla nieznanego/Google-only adresu i recipient limitu. Brak sieci i globalne 503 są jawnym błędem operacji, nie „wysłaliśmy wiadomość”.
- Anulowanie Credential Manager nie generuje czerwonego błędu i nie rozpoczyna końcowego POST; awaria parsera/Google jest osobnym stanem. Powrót z WWW nie tworzy nowej sesji automatycznie.
- Minimalne etykiety, opis 15–128 dla nowego hasła, błędy przy polach i sensowny fokus, autofill i wklejanie, dostępny przełącznik widoczności. Wszystkie nowe/zmienione komunikaty Androida w 17 locale; bez redesignu całego ekranu.

### 4. Techniczna retencja auth i kolejność prac

Proponowane maksima przechowywania technicznych rekordów, do sprawdzenia z manifestem [F-007/T-001](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md). F-007 zatwierdził brak raw diagnostyki, logi 7/metryki 30 dni i backupy do około 30 dni; poniższe to osobne krótkie rekordy funkcjonalne, nie wyjątek od purge konta:

| Dane | Proponowana retencja |
|---|---|
| Challenge Google i recent-proofs | TTL 5 min; fizyczne usunięcie najpóźniej w 24 h po wygaśnięciu/zużyciu |
| Access/refresh retry ciphertext | Twardy TTL 5 min z F-003; usunięcie najpóźniej w 24 h, wcześniej przy odwołaniu/odnowieniu bezpieczeństwa |
| Dowody verify/reset/change-email i zakończone zmiany adresu | Do 7 dni od wygaśnięcia/zakończenia; weryfikacja nigdy nie respektuje tokena po TTL |
| Rate buckets | Do 24 h po końcu ostatniego okna; bez zachowywania surowych identyfikatorów |
| Zaszyfrowany payload maila | Do 24 h od przyjęcia przez dostawcę lub terminalnego failure/cancel/expiry; treść i token wyzerowane, metadane mogą zostać |
| Metadane outboxu i ID webhooków bez body/odbiorcy | 7 dni od terminalnego stanu; deduplikacja/retry dostawcy nie może wymagać dłuższego okresu bez jawnej zmiany kontraktu |
| Odwołane/wygasłe sesje bez tokenów | 7 dni od końca ważności/odwołania; zdarzenia bezpieczeństwa i backupy mają osobny kontrakt F-007 |

Cleanup wspólny dla auth, ograniczone paczki do 100 rekordów/tabelę co 15 min w istniejącym procesie backendu; współbieżne repliki nie blokują się wzajemnie (`SKIP LOCKED`), błędy mają log/alert i bezpieczne ponowienie. To porządkowanie technicznych danych, nie nowy polling Androida/nauki. Granice TTL zawsze sprawdzane w API/workerze niezależnie od wykonania cleanup.

Router [F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) jest publiczny technicznie, lecz włączony do tych samych IP/cost/mail bucketów. Tam zapisano dodatkowe limity request/cancel/status, żeby poza `/auth` nie powstało obejście kosztu weryfikacji. Challenge i dowody hasła/Google usuwania mają TTL 5 min, e-mail 30 min, fizyczny cleanup tokenów akcji do 7 dni po końcu. Receipt/marker usunięcia mają odrębną retencję F-006/F-007, nie są czyszczone jak krótkie recent-proofs.

Implementację dzielimy w ramach istniejących tasków: wspólny limiter i błędy → integracja wszystkich tras → UI/mapowanie → testy konkurencji. Nie czekamy z testami na upload Play. F-008 odpowiada za rzeczywisty ingress, zasoby i dowody środowiskowe, F-007 za ocenę retencji/dostawcy.

### 5. Testy odbioru

- Zamrożony zegar: dokładne granice cooldownu/okien, odblokowanie bez ręcznej ingerencji, poprawne `Retry-After`, IPv4/IPv6 i sfałszowane nagłówki niezaufanego klienta.
- Dwie repliki na izolowanym PostgreSQL: limit N daje najwyżej N rezerwacji, również przy wyścigu pierwszego inserta; odmowa/rollback hasła nie cofa limitu prób. Retry tego samego mailowego requestu nie tworzy kolejnego zlecenia.
- Równoległe register: jeden właściciel adresu, kontrolowany konflikt dla drugiego. Timeout po commit umożliwia powrót do właściwego konta.
- Neutralny login: te same status/code/treść dla nieznanego/Google-only/złego hasła; test kontroluje wspólny verify, bez kruchego porównania nanosekund.
- Awarie DB/Google/poczty dają właściwe 503, nigdy sukces-shaped fallback; test przechwytuje odpowiedzi i logi dla syntetycznych sekretów, także błędy walidacji schematu.
- Testy klienta: podwójny tap/IME, back, timeout, restart, 429/503 i właściwe zachowanie po niepewnym wyniku. Nie wolno wyczyścić niewysłanej pracy przy samej próbie ponownego loginu.

## Kryteria i weryfikacja

- [ ] A-02: dwa register nie powodują nieobsłużonego 500; ponowienie po utracie odpowiedzi pozwala odzyskać dostęp.
- [ ] Limity login/register/reset/resend sprawdzone bez łatwego blokowania cudzego konta.
- [ ] Awaria dostawcy/sieci nie jest komunikowana jako błędne hasło.
- [ ] Formularz ma wyjście z oczekiwania, właściwy fokus/błędy, zachowuje adres i obsługuje wklejanie/menedżer haseł.
- [ ] Testy konkurencji z bazą, mapowania błędów i stanów klienta; A-03/A-20/A-21 w zakresie formularzy.

**Integracja:** F-007 ujmuje powyższą retencję, F-008/T-002 definiuje sprawdzenie rzeczywistego proxy i zasobów, T-004 niezależny alert, F-003 typowane stany klienta. Parametry są projektem do wykonania, nie wynikami pomiaru. Neutralny login obejmuje również rozpoznany bcrypt kierowany do resetu według T-001; bez ujawniania formatu konta.

**Poza zakresem:** kosmetyczny redesign całego logowania i nowa usługa limitera. **Wynik weryfikacji:** przegląd kodu auth i projekt wspólnego kontraktu; bez implementacji/testów runtime i bez udowodnionej konfiguracji proxy.
