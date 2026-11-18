# T-001 · Automatyczne bramki jakości i gotowość operacyjna

**ID:** `E-001/F-008/T-001` · **Status:** `in_progress` · **Priorytet / rozmiar:** P0/P1 / M.  
**Feature:** [Jakość i operacje](../README.md). **Źródło:** B-13; F-16 i [A-01…A-24](../../../sources/analiza-2026-11-17.md#10-macierz-testów-akceptacyjnych).

## Cel i zakres

Rozbudować istniejące bramki o realne testy auth/sync/DB i Androida, finalny release/device oraz miary produktu. Zacząć testy przy każdym feature, nie dopiero przed uploadem. B-13 podzielono bez zmiany tego ID: [T-002 środowiska](./T-002-srodowiska-i-konfiguracja.md), [T-003 backup/rejestr/restore](./T-003-backup-rejestr-i-odtwarzanie.md), [T-004 monitoring/koszty/incydenty](./T-004-monitoring-koszty-i-incydenty.md) są właścicielami tych kontraktów; T-001 je integracyjnie weryfikuje.

**Start:** brak wymogu ukończenia funkcji; najpierw izolowany PostgreSQL/CI według T-002 i planu niżej. **Akceptacja końcowa:** po wymaganym P0 z features E-001/F-002…F-007, przed [E-001/F-001/T-002](../../F-001-prowadzenie-bety/tasks/T-002-uruchomienie-bety.md). Nie tworzyć cyklu zależności publikacji.

### Zależności przyjęte z procesu usuwania

[F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) wymaga niezależnego rejestru usunięć/cofnięć; konkretny projekt jest w [T-003](./T-003-backup-rejestr-i-odtwarzanie.md): miejsce/wersje/szyfrowanie, trwałość i zatrzymanie restore przy niejednoznaczności. Odbiór wymaga wykonanej próby, bez samowolnego zakupu usług. Sam rekord z tej samej starej kopii nie spełnia celu.

Test restore musi obejmować grace, skuteczne cofnięcie, rozpoczęty purge i completed: bez wskrzeszenia sesji/kont, z nowym db_epoch sync i bez blokowania nowego User.id pod tym samym adresem. Sprawdzić ograniczenia worker lease/restart/alertów oraz właściciela reakcji, aby 7 dni na odstąpienie + do 7 dni purge było wykonywalnym SLA, nie wyłącznie tekstem.

### Wejście z zatwierdzonego F-007

- Raw diagnostyka wyłączona we wszystkich kanałach, nie tylko LlmCallPayload. Minimalne własne logi 7 dni, metryki bez treści 30 dni; [T-001 prywatności](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md) oddziela to od danych funkcjonalnych, procesorów i krótkich sekretów.
- Historia dzienna/tygodniowa do 27 dni, bez miesięcznych 89 dni. T-003 konkretyzuje kopie co 30 min dla RPO i retencję 24 h/6/27 dni; rzeczywisty plan/koszt oraz fizyczne kopie Railway/ręczne/wolumeny trzeba objąć tym samym inwentarzem. Bez zakupu usługi podczas specyfikacji.
- Faktyczny plan Railway może trzymać stdout dłużej niż własna tabela: ustalić skuteczne ograniczenie albo jawnie uzgodniony wyjątek, nie obiecywać 7 dni na podstawie SQL. Brak nowego third-party log drain i SDK analityki bez osobnej decyzji.
- Projekt markerów/rejestru: 45 dni od terminalnego stanu, receipt 30 dni; zweryfikować wobec wszystkich restorable kopii i czasu starych dowodów. Brak możliwości dotrzymania wymaga nowej konkretnej decyzji, nie cichego trzymania bez końca.
- Wskazać imienną rolę operatora (bez prywatnych danych w publicznym repo), monitorowany kanał oraz miarę pierwszej odpowiedzi **człowieka do 2 dni roboczych**. Incydenty bezpieczeństwa/prywatności mają osobne priorytety/terminy prawne i drogę eskalacji; nie deklarować dyżuru 24/7.
- Raport treści wymaga rozszerzenia istniejącego panelu/obsługi, nie osobnego helpdesku/LLM. Test obejmuje offline/ACK, przekroczenie celu odpowiedzi, kontrolę dostępu i wcześniejszy purge konta.

Decyzje końcowe: dodatkowa infrastruktura możliwie darmowa, projekt do 50 EUR/miesiąc; RPO 1 h/RTO 24 h od wykrycia, operator-właściciel/e-mail; kwoty WARN/HARD AI obowiązkowe dopiero przed startem, ręczne dokupienie nie przekracza HARD. Konkretne projekty mechanizmów są w T-002/T-003/T-004, nie wymagają kolejnej ankiety o parametry techniczne.

## Stan kodu i najmniejsza rozbudowa CI

[Workflow](../../../../../../.github/workflows/ci.yml) wykonuje [ci_check](../../../../../../scripts/ci_check.py): 17 locale, LSP sync i backend pytest. Brakuje jobu Android i usługi PostgreSQL. [Conftest](../../../../../../backend/tests/conftest.py) świadomie dopuszcza tylko localhost i nazwę `_test`, a przy braku bazy skipuje `pg`; zielony obecny job nie dowodzi wykonania tych testów.

1. Zachować `python scripts\ci_check.py` jako wejście, nie zastępować własnym nowym runnerem. W CI dołożyć PostgreSQL service, healthcheck oraz jawne `TEST_DATABASE_URL` wskazujące wyłącznie localhost/`vocabulario_ci_test`; ustawić przed importem app. Nie pobierać go z secretu bety.
2. Do CI dodać kontrolę, że wymagane testy `pg` zostały zebrane i **nie są skipped**; błędny/brakujący test DB ma przerwać wymagany job. Testy z fixture TRUNCATE nie są wykonywane równolegle na tej samej bazie (`xdist` bez izolacji niedozwolony).
3. Atrapy na granicy transportu AI/poczty/Google/S3: brak realnego Internetu/kluczy dla testów PR, ale prawdziwe transakcje, constraints, SAVEPOINT i zegar. Osobny ręczny smoke integracji na staging z zatwierdzonymi kluczami i limitem.
4. Android job z JDK 17 i właściwym SDK/Gradle F-002: unit/compile i lint. Najpierw istniejące testy, następnie kilka celowanych przypadków dla zmienionych zachowań; żadnych testów samych stałych albo sukces-shaped mocków.
5. Signed release/Play/device to ręczny gate, nie pobieranie upload key do workflow z PR/forka. Build bez produkcyjnego sekretu może wykonywać unit/compile; nie może udawać podpisanego AAB.
6. Backend fresh schema oraz upgrade z syntetycznego poprzedniego schematu; istniejące konta bez dowodu nie dostają weryfikacji/warunków. Nie używać dumpu rzeczywistych użytkowników jako fixture.

## Macierz testów wykonawczych

| Obszar | Wymagany test i dowód |
|---|---|
| Auth/password/mail/Google | Neutralne błędy, Unicode/hasła, tokeny/nonce/replay, rotacja lost-response, podwójny reset/zmiana/łączenie, błędy DB/dostawcy i brak sekretów |
| Owner/offline/sync | Room atomic mutation+intent/ACK, A→B i callback po logout, wszystkie profile/kolejki w tym raport, brak onboarding z błędu, konflikt profilu, snapshot/cursor z długą transakcją i SAVEPOINT, undo po nowszej ocenie |
| Lifecycle i journal | Request/cancel na granicy 168 h pod blokadą, pauza zadań, commit/PUT/timeout/restart w każdej granicy, purge 14 dni, konto B/publiczny cache nienaruszone, restore po utracie zmian bezpieczeństwa |
| Budżet i regresja E-002 | Dwie repliki/rezerwacje/nieznany usage, brak dodatkowego LLM na raport/monitor i brak `import_verify`, `waiting_budget` bez duplikacji/awansu gotowości, 25/job i 25/profil/UTC |
| UI/konto/WWW | Raport bez wychodzenia, wersja warunków/wiek/stare konto, skaner GET, komputer bez aplikacji, timeout/back/restart, powiadomienia i odmowa dostępu |
| Migracja i wydanie | Nowy ID vs aktualny debug, restore/backup/transfer, Play→update z outboxem, podpis Play a nie upload/debug, HTTPS-only i 16 KB finalnego artefaktu |

Wielowątkowe testy z kontrolowanymi barierami, nie przypadkowym sleep, obejmują wszystkie istotne kolejności. Skuteczny test nie tylko „nie rzucił wyjątku”: sprawdza właściciela, rewizje, liczbę wywołań/wierszy i stan końcowy obu stron. Błąd idempotency nie jest dopuszczonym skip.

### Urządzenia i mierzalne cele

- Fizyczny **Samsung S24** właściciela; rzeczywisty wariant/model/Android/API zapisać dopiero przy teście, bez IMEI/serial. Nie zgadywać wersji systemu z nazwy modelu.
- Emulatory API 26 (minimalne wsparcie Android 8), 31/32, 33 i 36, w tym obraz 16 KB i mały ekran. Łączyć scenariusze według ryzyka, nie odpalać całej macierzy na każdej kombinacji.
- Fizyczny drugi producent/tańszy model po uzyskaniu dostępu w closed, bez zakupu/obietnicy dostępności teraz. Do tego czasu jawne ograniczenie dowodu, nie fikcyjny PASS.
- P0: 0 znanych przypadków mieszania kont, niejawnego odrzucenia pracy, obejścia lifecycle i nieodwracalnego usunięcia w grace. 100% obowiązkowych scenariuszy A-01…A-24 z właściwym wynikiem; żaden obowiązkowy test nie jest skipped.
- Login e-mail przy prawidłowej sieci: ≥95% z minimum 30 prób, obejmujących świeży start i powrót aplikacji, dochodzi do właściwego ekranu w ≤5 s. Zmierzyć na S24 i opisać sieć/backend; to nie twierdzenie o najwolniejszym telefonie świata. Po 10 s dostępne retry/wyjście, a nie sam spinner.
- Cached home bez sieci interaktywne ≤3 s w minimum 30 pomiarach. Budżet Argon2 z F-004 pozostaje osobnym pomiarem na docelowych zasobach backendu, nie wynikiem telefonu.
- ≥5 nowych testerów samodzielnie kończy instalację/konto/pierwszą powtórkę; przed rozszerzeniem 7 dni obserwacji bez nierozwiązanego krytycznego crash/ANR. Cel supportu do 2 dni roboczych.
- Odbiór UI: TalkBack, 200% font, RTL, tryby motywu/IME, offline/restart i odmowa powiadomień. Dowód językowy nie sprowadza się do posiadania 17 kluczy.

## Format wyniku i gate

Dla scenariusza: ID taska/A-xx, commit/backend/schema, versionCode/AAB SHA-256, podpis/pakiet, środowisko, urządzenie/API, dane syntetyczne lub zanonimizowany tester, kroki, expected/actual, PASS/FAIL/BLOCKED, czas i odnośnik do bezpiecznego dowodu. Raporty mogą być prywatnym artefaktem CI/release poza Git; brak list e-maili/testerów i raw payloadów.

Wymagany gate blokuje FAIL/BLOCKED/skip, nie tylko exit code kompilacji. Wyjątki P1 jawnie przypisane z terminem, bez wyłączenia ochrony danych/auth/usuwania. Pre-launch report/Vitals uzupełniają test, nie zastępują loginu Google na podpisie Play. Sam opis kryterium ani test na emulatorze nie daje wyniku S24.

## Kryteria i weryfikacja

- [ ] Bazowe `python scripts\ci_check.py` oraz dobrane Gradle unit/compile/lint/release faktycznie przechodzą.
- [ ] Testy auth, wyścigów, izolacji i idempotencji działają na wydzielonym PostgreSQL; żaden obowiązkowy test nie pozostaje skip/assert-True placeholderem.
- [ ] A-01…A-24 mają wersję AAB/backendu, urządzenie/API, kroki, oczekiwany/rzeczywisty wynik i status.
- [ ] A-23/A-24 zachowują kontrakty nauki/importu z E-002, bez dodatkowych wywołań/pollingu.
- [ ] Realny Play/device pokrywa Google, linki, aktualizację, backup i uprawnienia; pre-launch/vitals ocenione.
- [ ] Jest dowód odtworzenia bazy na osobnym środowisku i instrukcja zatrzymania rolloutu/poprawki zgodnej ze starym klientem.
- [ ] Wybrano właściciela diagnostyki, alertów, kosztów AI i obsługi incydentu; P1 jawnie przypisane.

Zakres B-13 rozdzielony na cztery wykonalne taski w indeksie feature'a; wspólne testy integrują ich wynik. **Poza zakresem:** pełny pentest, używanie bety jako testowej bazy i automatyczny deploy. **Wynik weryfikacji:** projekt oparty o aktualny workflow/conftest/build; nie uruchomiono CI/buildów ani nie zapisano fikcyjnych wyników.

## Postęp

### Etap 1 · PostgreSQL w CI bez zielonych skipów (18.11.2026)

Wykonane punkty 1–2 planu CI powyżej:

- [Workflow](../../../../../../.github/workflows/ci.yml) ma usługę `postgres:16` z healthcheckiem, syntetyczną bazą `vocabulario_ci_test` na localhost i `REQUIRE_PG_TESTS=1`. Hasło dotyczy wyłącznie jednorazowego kontenera jobu, nie bety.
- [Conftest](../../../../../../backend/tests/conftest.py): w trybie wymaganym brak adresu/połączenia (kod 3), brak wybranych testów `pg` (kod 3) i każdy pominięty/xfail test `pg` (kod 1) przerywają job. Bez flagi lokalnie testy `pg` są pomijane jak dotąd, z ostrzeżeniem w podsumowaniu. Ochrona localhost/`_test` bez zmian.
- [ci_check](../../../../../../scripts/ci_check.py) uruchamia kroki tym samym interpreterem (`sys.executable`); wcześniej na Windows z venv trafiał do globalnego Pythona bez zależności.
- [Testy bramki](../../../../../../backend/tests/test_pg_requirement.py) uruchamiają osobny proces pytest z kopią conftest; 6 z 7 nie przechodzi na poprzedniej wersji (siódmy to kontrola pozytywna).
- Pierwszy przebieg na prawdziwej bazie ujawnił ukryty dotąd błąd E-002: trafienie w cache dawało inną listę w ścieżce szybkiej (`local_membership=true`) i pełnej, wbrew [kontraktowi cache](../../../../E-002-szybka-nauka/features/F-002-wyszukiwanie/tasks/T-001-cache.md). Decyzja właściciela: obie ścieżki czyszczą i sortują wiersz jak szybka; `lookup_cached` bez `preserve_order` przy trafieniu. Gałąź bez cache bez zmian.

**Dowód lokalny** (Windows, Python 3.12, tymczasowy PostgreSQL 16.2 poza repo): `ci_check` z `REQUIRE_PG_TESTS=1` — UI strings, LSP i pytest zielone, 570 passed / 0 failed / 0 pominiętych `pg`; dwa dodatkowe przebiegi `-m pg` po 35/35. Bez bazy i flagi: 535 passed, 37 skipped, kod 0.

**Otwarte w tym tasku:** pierwszy przebieg na GitHub Actions (nic nie wypchnięto), job Android (punkt 4), upgrade schematu z syntetycznej starej bazy (punkt 6), macierz A-01…A-24 i urządzenia. Dwa pozostałe skipy nie są `pg`: placeholder [test_sync](../../../../../../backend/tests/test_sync.py) bez treści („Requires test DB + auth fixtures”) do zastąpienia prawdziwym testem przy F-003/T-003 oraz parametr manifestu LSP bez czasów. Lokalnie na Windows bez `PYTHONIOENCODING=utf-8` test LSP pada na kodowaniu konsoli `cp1252`; Linux w CI tego nie dotyczy.
