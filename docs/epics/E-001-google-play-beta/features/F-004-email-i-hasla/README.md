# F-004 · E-mail i hasła

**ID:** `E-001/F-004` · **Status:** `in_progress` · **Epic:** [E-001](../../README.md).

**Wartość:** użytkownik rejestruje się i odzyskuje dostęp samodzielnie, a zaakceptowane hasło jest sprawdzane w całości.

**Decyzja z 21.11.2026:** zmiana i korekta adresu e-mail nie są dostępne. Inny adres wymaga nowego konta; nie przenosimy automatycznie danych ani profili. Historyczne opisy tej funkcji poniżej i w T-004 nie są obowiązującym zakresem.

## Zakres i akceptacja

- Migracja hashowania nie odcina istniejących kont i nie obcina długich/Unicode haseł.
- Weryfikacja e-maila, reset i zmiana hasła działają z prawdziwym dostarczeniem poczty; tokeny jednorazowe i wygasające.
- Potwierdzenie adresu i ustawienie nowego hasła działają także na prostej stronie HTTPS bez aplikacji; link nie daje dostępu do biblioteki ani sesji WWW.
- Uzgodniony próg: nowe i dotychczasowe niezweryfikowane konta e-mail nie korzystają w pełni przed potwierdzeniem adresu; mają resend, wyjście i pomoc. Egzekwowanie także w API, nie tylko przez ukrycie ekranu.
- Konto Google-only nie trafia do pozornego resetu hasła aplikacji.
- Google-only może dodać hasło po ponownym potwierdzeniu tożsamości Google i wymaganym potwierdzeniu adresu aplikacji. Samodzielne odłączanie metod logowania odkładamy poza betę.
- Konflikty, utrata odpowiedzi, limity prób i formularze dają kontrolowane komunikaty; nowe napisy we wszystkich 17 locale.

## Historyczna polityka konta — 17.11.2026

To wspólny kontrakt biznesowy dla F-003/F-004/F-005/F-006. Szczegóły protokołów pozostają do opracowania; poniższych decyzji nie podejmujemy ponownie przy implementacji każdego taska.

### Tożsamość i adres

- Konto aplikacji zachowuje to samo ID, profile, bibliotekę i postęp niezależnie od sposobu logowania lub zmiany adresu.
- Adres aplikacji służy do kontaktu i logowania hasłem, jeśli hasło istnieje. Powiązanie Google jest osobną metodą, identyfikowaną przez zweryfikowane `sub`, nie przez aktualną równość adresów.
- Zmiana adresu aplikacji nie zmienia Gmaila, nie odłącza dotychczasowego Google i nie tworzy drugiego konta.
- Do potwierdzenia nowego adresu aktywny pozostaje stary. Po skutecznym przełączeniu logowanie hasłem używa nowego adresu; hasło nie jest zmieniane przez samą zmianę adresu.
- Login wcześniej podłączonym Google po zmianie adresu wraca do tego samego ID i nie nadpisuje adresu aplikacji adresem otrzymanym od Google.
- Potwierdzony adres Google nie potwierdza automatycznie innego adresu aplikacji. Sam zapis `google_id` także nie dowodzi weryfikacji obecnego adresu.
- Nie scalamy kont tylko po adresie. Dołączenie Google do istniejącego konta wymaga potwierdzenia własności obu tożsamości zgodnie z kontraktem F-005.
- Przy dołączaniu adres Google może różnić się od adresu aplikacji. Powiązanie należące już do innego ID nie jest przenoszone, a adres aplikacji pozostaje bez zmian.
- Bez dodatkowego linku uznajemy tylko wiarygodny dowód Google dla zgodnego adresu: `email_verified=true` i Gmail albo Google Workspace potwierdzony claimem `hd`. Dla niezweryfikowanej zewnętrznej skrzynki potrzebne jest nasze potwierdzenie; już zweryfikowanego adresu aplikacji nie sprawdzamy ponownie.
- Dostęp do starej skrzynki nie jest warunkiem zmiany: potrzebne są ponowne potwierdzenie tożsamości hasłem lub podłączonym Google i potwierdzenie nowej skrzynki. Sama otwarta sesja nie wystarcza. Stary potwierdzony adres dostaje zawiadomienia o rozpoczęciu i zakończeniu, nie prośbę o obowiązkową zgodę; wyjątek korekty poniżej.
- Bez dostępu do żadnej metody ponownego potwierdzenia tożsamości nie ma samoobsługowej zmiany adresu. Nie obiecujemy ręcznego odzyskiwania na podstawie samego zgłoszenia.
- Oczekuje tylko jedna zmiana adresu: nowy poprawnie uwierzytelniony wniosek zastępuje poprzedni i jego linki; resend tej samej zmiany nie unieważnia wcześniejszych linków. Przy korekcie niezweryfikowanego adresu nie wysyłamy zawiadomień na potencjalnie cudzą starą skrzynkę, w odróżnieniu od zwykłej zmiany potwierdzonego adresu.

### Macierz metod

| Stan konta | Zwykłe logowanie | Operacja na haśle | Odłączanie metod w becie |
|---|---|---|---|
| E-mail/hasło | Aktualny adres aplikacji + hasło | Reset lub zmiana istniejącego hasła | Niedostępne |
| Google-only | Wcześniej podłączone Google | Osobne „Dodaj hasło” po ponownej weryfikacji właściwego Google i wymaganej weryfikacji adresu aplikacji; nie zwykły reset | Niedostępne |
| Google + hasło | Dowolna z obu metod do tego samego konta | Reset/zmiana hasła nie odłącza Google | Niedostępne |

Dodanie hasła do Google-only nie rejestruje nowego konta, nie zmienia adresu i nie usuwa danych. Próba wykonania tej operacji, gdy hasło już istnieje, nie może nadpisać go z pominięciem reguł zmiany hasła. Publiczny reset nie staje się obejściem dodania hasła i nie ujawnia rodzaju/istnienia konta w odpowiedzi.

### Hasła i potwierdzanie skrzynki

- Nowe hasło przy rejestracji, resecie, zmianie i dodaniu: 15–128 znaków, bez obowiązkowych klas znaków; Unicode i spacje bez trimowania/obcinania. Wklejanie i menedżery haseł dozwolone. [T-001](./tasks/T-001-haszowanie-hasel.md) proponuje wspólną definicję znaku i kontrakt techniczny.
- Skuteczny reset przez link na bieżący adres potwierdza również ten adres w tej samej transakcji. Bez dodatkowego maila weryfikacyjnego, ale także bez automatycznego loginu: wszystkie sesje zostają odwołane. Link związany ze starym adresem/rewizją nie potwierdza nowego.
- Zmiana istniejącego hasła w ustawieniach wymaga obecnego hasła; zapomniane hasło obsługuje reset przez e-mail. Świeże Google nie zastępuje obecnego hasła przy tej operacji w becie. Nie zmienia to zatwierdzonych zasad dodania pierwszego hasła do Google-only ani potwierdzania zmiany adresu.
- Nieudany login hasłowy ma jednolite 401 `invalid_credentials` i komunikat „Nieprawidłowy e-mail lub hasło”, bez ujawniania istnienia/rodzaju konta. Google i reset dostępne każdemu; awaria/limit/sieć pozostają osobnymi błędami.

### Sesje i migracja

| Operacja | Zatwierdzony rezultat |
|---|---|
| Reset hasła | Odwołanie wszystkich dotychczasowych sesji aplikacji, także na urządzeniu otwierającym link; ponowne uwierzytelnienie |
| Zmiana hasła w ustawieniach | Odwołanie pozostałych sesji; bieżące urządzenie zachowuje dostęp przez bezpieczne odnowienie sesji po sukcesie |
| Dodanie pierwszego hasła do Google-only | Odwołanie pozostałych sesji i bezpieczne odnowienie bieżącej; zawiadomienie na adres aplikacji, Google nadal podłączone |
| Dodanie Google do istniejącego konta | Odwołanie pozostałych sesji i bezpieczne odnowienie bieżącej; zawiadomienie na adres aplikacji, bez zmiany adresu i utraty danych |
| Skuteczna zmiana adresu aplikacji | Odwołanie wszystkich dotychczasowych sesji, także bieżącej; ponowny login nowym adresem/hasłem albo podłączonym Google |
| Wymuszona reautoryzacja | Niewysłana praca pozostaje przypisana do tego samego ID użytkownika; nie wolno jej skasować ani wysłać jako inne konto |
| Dotychczasowe niezweryfikowane konto e-mail | Potwierdzenie adresu przed dalszym pełnym korzystaniem, bez dodatkowego okresu przejściowego i bez utraty danych |
| Przyjęcie usuwania konta | Wszystkie sesje odwołane i konto zablokowane, dane zachowane przez 7 dni odstąpienia; po skutecznym cofnięciu wymagany nowy login |

Odwołanie sesji aplikacji nie oznacza odłączenia Google ani globalnego wylogowania z Google na urządzeniu. Prawidłowe nowe logowanie podłączonym Google pozostaje dostępne. Wymóg weryfikacji obejmuje też starego klienta/API, nie tylko nowy ekran. Zgodne przełączenie opisuje F-002/T-001 z F-003; nie zostawiamy wyjątku legacy omijającego auth.

Wyjątek lifecycle: w pending/deleting zwykły login/refresh, reset/zmiana/dodanie hasła, link Google i zmiana adresu nie reaktywują konta; publiczny reset zachowuje neutralną odpowiedź bez nowego linku. Cofnięcie jest osobną operacją [F-006/T-002](../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md). Hasło/podłączone Google pozwalają rozpocząć usunięcie także przy niezweryfikowanym adresie; mailowy dowód usunięcia/cofnięcia wyłącznie na wcześniej zweryfikowany bieżący adres. Po completed można utworzyć nowe konto z nowym ID.

## Scenariusze akceptacyjne polityki

Identyfikatory S-* są lokalne dla tego feature'a; uzupełniają źródłowe A-01…A-24, nie zastępują ich.

| ID | Przebieg | Wynik do wykazania |
|---|---|---|
| S-01 | Google-only z dwiema sesjami → poprawne ponowne potwierdzenie Google → wymagane potwierdzenie adresu → dodanie hasła | To samo ID/postęp; obie metody działają, bieżąca sesja odnowiona, pozostałe odwołane; zawiadomienie na adres aplikacji |
| S-02 | Dodanie hasła z tokenem innego Google, starą próbą lub równolegle | Brak dopisania cudzej metody i nadpisania już istniejącego hasła |
| S-03 | Publiczny reset dla Google-only | Brak utworzenia hasła, brak ujawnienia rodzaju/istnienia konta w odpowiedzi; dostępna ogólna instrukcja Google |
| S-04 | Konto z Google, adres aplikacji A → potwierdzone B → ponowny login tym samym Google | Wszystkie stare sesje odwołane; to samo ID, adres aplikacji pozostaje B; hasło, jeśli istnieje, działa z B, nie A |
| S-05 | Zmiana na adres zajęty przez inne konto lub dołączenie Google należącego do innego konta | Kontrolowany konflikt, bez przejęcia/scalenia bibliotek |
| S-06 | Reset hasła z dwiema sesjami, również konto z podłączonym Google | Stare sesje odwołane; nowe logowanie hasłem lub właściwym Google nadal możliwe |
| S-07 | Zmiana hasła w ustawieniach przy dwóch sesjach | Bieżące urządzenie ma odnowioną sesję, drugie wymaga ponownego loginu |
| S-08 | Reset/zmiana hasła → utrata odpowiedzi → restart klienta z niewysłaną pracą | Bez utraty outboxu i przywrócenia odwołanej sesji; bezpieczna droga potwierdzenia aktualnego stanu/reauth |
| S-09 | Konto z jedną lub dwiema metodami → „Moje konto” | Widać faktyczne metody i właściwą akcję dodania/zmiany hasła; brak samodzielnego odłączenia |
| S-10 | Aktualizacja istniejącego konta e-mail bez dowodu weryfikacji | Wymagana weryfikacja przed pełnym użyciem; ID, profile, postęp i outbox zachowane, także po restarcie |
| S-11 | Poprawny Google token z adresem różnym od niezweryfikowanego adresu aplikacji | Brak automatycznego uznania adresu aplikacji lub cofnięcia jego zmiany |
| S-12 | Niedostarczona wiadomość, wygasły/użyty link, anulowanie, brak sieci | Czytelny stan i droga ponowienia; brak częściowego przełączenia adresu lub pozornego sukcesu |
| S-13 | Brak dostępu do starej skrzynki, ale poprawne ponowne uwierzytelnienie i potwierdzenie nowej | Zmiana możliwa bez kliknięcia w starej skrzynce; na stary adres zawiadomienia o rozpoczęciu i zakończeniu |
| S-14 | Otwarta sesja, ale brak dostępu do hasła i podłączonego Google | Brak samoobsługowej zmiany adresu przez sam access token lub zgłoszenie do wsparcia |

S-01…S-14 wymagają przypisania konkretnych testów API/PostgreSQL/Android i kontroli dostarczenia linków. To opis oczekiwań, nie wyniki testów.

## Stan kodu sprawdzony przy doprecyzowaniu

- [User](../../../../../backend/app/models/__init__.py#L11) ma stałe ID, unikalny `email`, opcjonalne `password_hash` i `google_id`; brak stanu weryfikacji adresu i osobnych operacji zmiany/dodania hasła.
- [Auth API](../../../../../backend/app/api/v1/auth.py) obsługuje register/login/google/refresh. Google najpierw szuka po `google_id`, ale przy braku dopasowania automatycznie dołącza po e-mailu — ta gałąź wymaga zastąpienia jawnym procesem.
- [UserResponse i żądania auth](../../../../../backend/app/schemas/__init__.py) nie przekazują pełnego stanu weryfikacji/metod ani kontraktów nowych procesów.
- [JWT](../../../../../backend/app/core/security.py) nie ma identyfikatora odwoływalnej sesji; [zależności auth](../../../../../backend/app/core/deps.py) nie realizują wymaganego unieważniania i bramki weryfikacji. Trzeba objąć zarówno ścieżki pobierające użytkownika, jak i korzystające tylko z jego ID, bez nieuzasadnionego N+1.
- [AuthRepository](../../../../../android/app/src/main/java/com/vocabulario/app/data/AuthRepository.kt) czyści tokeny i Room na początku loginu/rejestracji/Google. Takiego zachowania nie wolno użyć do migracji, dodania metody ani reauth.

To ograniczony przegląd punktów integracji, nie pełna specyfikacja protokołów ani test runtime.

## Stan przygotowania i bramki wykonania

### Stan po zbiorczym domknięciu zasad logowania i danych logowania

Poniższa tabela rozdziela opisany kontrakt od formalnej gotowości do implementacji. Nie jest listą nowych decyzji dla właściciela i nie oznacza zaliczenia testów.

| Task | Przygotowany projekt | Integracja / wykonawcza bramka |
|---|---|---|
| T-001 hasła | Argon2id/Unicode, bezpieczny reset legacy z zachowaniem ID, testy i pomiary | Ścieżka przejścia F-002, środowisko F-008; brak cichego rehashu bcrypt |
| T-002 poczta | Dowody/API, outbox, budżety/webhooki i testy | F-007 mapuje Resend/USA/30 dni; właściciel potwierdza DPA/domenę/DNS/sender przed wysyłką |
| T-003 odporność | Limiter/błędy/timeout/retencja i testy | F-008/T-002 sprawdza ingress/zasoby; F-003 rozdziela auth/transient stany |
| T-004 adres | Korekta/zmiana/TTL, zastępowanie/idempotency i testy | Journal/revisions F-003/T-001 + F-008/T-003, sesja Androida i release F-002 |
| T-005 pierwsze hasło | Warunki/endpoint, transakcja/retry/reauth i testy | Wspólne Google/recent-proof, sesje/journal, bez nadpisywania już istniejącego hasła |

**Zasady produktu i projekty tego bloku ustalone.** Nie ponawiamy pytań o reset/Google/adres/sesje. Zależności Androida, usuwania, retencji, restore i wydania są opisane w swoich taskach. Nazwa/domena są odłożonymi bramkami uruchomienia, nie blokadą implementacji hashera/limitera.

Pięć tasków ma status `ready` po przeglądzie kompletności i domknięciu przejścia legacy. Runtime/prawdziwa poczta/Play będą odbiorem implementacji, nie są zaliczone przez opis. Niekupiona domena blokuje publiczną wysyłkę/strony, nie pisanie wspólnych komponentów.

**Wspólne projekty:** [sesje backendu](../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md#proponowany-kontrakt-techniczny-sesji) i [Google/recent-auth](../F-005-google/tasks/T-001-google-i-laczenie.md#proponowany-kontrakt-techniczny-google-i-recent-auth), oprócz pięciu tasków w tabeli. Przy implementacji obowiązują również:

- F-003: trwały zapis sesji, stan Androida, właściciel outboxu, migracja istniejących danych i kolejność zgodnych wydań; serwer nie może wyprzedzić przygotowanego klienta.
- F-006: pola ekranu konta i integracja operacji; osobny proces usunięcia nie może odtwarzać konta przez oczekujący token, job lub stary telefon.
- F-007: ocena retencji i dostawcy/DPA, języków serwisu/maili i konfiguracji rzeczywistej domeny/sendera przed publicznym uruchomieniem.
- F-008: izolowane środowisko, rzeczywisty ingress/proxy, plan pomiarów zasobów/limitów i późniejsze dowody poczty/App Links/Play.

Szczegóły techniczne są zapisane przez wykonawcę po sprawdzeniu kodu. Nowe zmiany doświadczenia/kosztów wymagają zatwierdzenia, ale wykonawcze wartości usług i wyniki testów nie są powodem powtarzania ankiety ani oznaczania projektu jako niewiadomego.

## Taski

| ID | Task | Status |
|---|---|---|
| E-001/F-004/T-001 | [Pełne hashowanie haseł](./tasks/T-001-haszowanie-hasel.md), B-04 | `done` |
| E-001/F-004/T-002 | [Poczta i odzyskiwanie](./tasks/T-002-poczta-i-odzyskiwanie.md), B-05 | `in_progress` |
| E-001/F-004/T-003 | [Odporność auth](./tasks/T-003-odpornosc-auth.md), B-10 | `done` |
| E-001/F-004/T-004 | [Zmiana adresu e-mail](./tasks/T-004-zmiana-emaila.md) | `done` — funkcja wycofana |
| E-001/F-004/T-005 | [Dodanie hasła do Google-only](./tasks/T-005-dodanie-hasla.md) | `in_progress` |

**Zależności:** decyzje E-001/F-001/T-001; sesje E-001/F-003/T-001 dla resetu/rotacji i końcowych testów. Moment wymagania weryfikacji nowych i starych kont uzgodniony, Resend Free wybrany warunkowo; ocena/uruchomienie poczty, konkretne uprawnienia/parametry i techniczna migracja istniejących kont pozostają do domknięcia.

**Poza zakresem:** zmiana dostawcy całego auth, MFA/passkeys, samodzielne odłączanie metod. Dawna propozycja odłożenia zmiany e-maila do P1 została zastąpiona decyzją o pierwszej becie i pełnym kontraktem T-004; nie jest ponownie otwartą decyzją.

**Weryfikacja:** A-01…A-05 i limity; testy z bazą oraz realna skrzynka/deep link. **Dowody:** T-001 etap 1 — testy jednostkowe komponentu haseł (lokalnie); poza tym brak.
