# E-001 · Beta Google Play

**Status:** `in_progress` — kontrakty gotowe, trwa implementacja; aplikacja nie jest jeszcze odebrana do bety.  
**Priorytet:** bieżący kierunek pracy.  
**Odbiorca:** nowy i powracający tester Androida, bez pomocy autora aplikacji.

**Etap pracy:** przygotowanie specyfikacji zakończone: **8 features / 24 taski**, z czego decyzje F-001/T-001 `done`. Implementacja trwa: F-008/T-001 `in_progress` (PostgreSQL i Android w CI), F-008/T-002 `in_progress` (walidacja ustawień, `/health/ready`), F-004/T-001 `in_progress` (komponent haseł, niepodłączony), F-003/T-001 `in_progress` (sesje backendu podłączone do tras; reszta czeka na operacje konta F-004/F-006 i Androida F-003/T-002), F-003/T-002 `in_progress` (zaszyfrowana sesja, właściciel danych w Room, login bez kasowania, ekrany reauth/recovery, trwałe odwołanie sesji na serwerze, logout z decyzją o niewysłanych zmianach; dalej ochrona workerów generacją), pozostałe 18 `ready` do wykonania po osobnym zleceniu. [Rejestr decyzji](./features/F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md) oddziela uzgodniony biznes od realnych bramek konfiguracji. Nie potrzeba kolejnych rund „ok” do kończenia tych bloków.

## Problem i cel biznesowy

Działające tryby nauki nie wystarczą do zewnętrznej bety. Użytkownik musi sam zainstalować aplikację, rozpoznać swoje konto, odzyskać dostęp, zachować postęp i móc skutecznie usunąć dane. Celem jest wiarygodny test obecnego produktu, nie rozwój nowych trybów nauki.

Uzgodniony kierunek: orientacyjnie 5–30 dorosłych testerów, początkowo znajomi, bez kampanii i bez sztucznego ograniczania języków. Priorytetem są stabilność, płynność, profesjonalny UX i informacja zwrotna o core. Beta bez płatności; płatne dodatki/waluta pozostają osobnym przyszłym tematem przed szerszą promocją. Nowe i dotychczasowe niezweryfikowane konta e-mail potwierdzają adres przed pełnym korzystaniem, bez dodatkowego okresu przejściowego i bez utraty danych, ze ścieżką resend/korekta/wyjście/pomoc. Zmiana adresu e-mail wchodzi do pierwszej bety; powiadomienia ograniczamy do lokalnych przypomnień. Zachowujemy istniejący postęp, przygotowujemy osobny serwis publiczny aplikacji, a dodatkowe koszty minimalizujemy i zatwierdzamy przed uruchomieniem.

[Zatwierdzona polityka konta w F-004](./features/F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026) opisuje dodanie hasła do Google-only, brak odłączania metod w becie, niezależność adresu aplikacji od Google oraz różne skutki resetu i zmiany hasła dla sesji. Kontrakty i plan przejścia są zapisane; ich wykonanie/testy pozostają pracą implementacyjną.

Punktem wyjścia jest [analiza stanu faktycznego z 17.11.2026](./sources/analiza-2026-11-17.md). Jej F-/B-/A- są zachowanymi identyfikatorami źródłowymi. **Aktualne jednostki pracy to features i taski poniżej**, nie druga kopia backlogu w analizie.

## Miary sukcesu i zamknięcie

- 0 znanych przypadków mieszania kont lub nieodwracalnej utraty pracy bez świadomej zgody.
- 100% krytycznych scenariuszy konta, synchronizacji i usuwania przechodzi; [A-01…A-24](./sources/analiza-2026-11-17.md#10-macierz-testów-akceptacyjnych) mają zapisane wyniki.
- Co najmniej 5 nowych testerów przechodzi instalację, konto/onboarding i pierwszą powtórkę samodzielnie.
- Przy prawidłowej sieci ≥95% prób e-mail login prowadzi do właściwego ekranu w 5 s; po 10 s nie zostaje sam bezterminowy spinner. Cached home offline interaktywne w 3 s na ustalonym urządzeniu.
- Przed rozszerzeniem grupy: 7 dni obserwacji bez nierozwiązanego krytycznego crash/ANR, działający kanał pomocy i cel pierwszej odpowiedzi człowieka do 2 dni roboczych. Pilne incydenty obsługiwane priorytetowo według F-008, nie odkładane do końca tego celu.
- Spełnione [bramki internal, closed i rozszerzenia](./sources/analiza-2026-11-17.md#11-bramki-wejścia-i-wyjścia-z-bety). P0 z dowodami, pozostałe P1 jawnie przypisane i zaplanowane przed rozszerzeniem.

Progi to cele produktu, nie wymagania Google. Wymogi sklepu sprawdzamy ponownie w dniu publikacji. Zamknięcie epica wymaga wyników z konkretnego AAB/backendu oraz decyzji właściciela o rozszerzeniu bety; sam upload nie wystarcza.

## Zakres

| Feature | Rezultat | Status |
|---|---|---|
| [F-001 · Zakres i uruchomienie bety](./features/F-001-prowadzenie-bety/README.md) | Uzgodnione decyzje, świadome przejście internal → closed | `ready` |
| [F-002 · Wydanie przez Play](./features/F-002-wydanie-play/README.md) | Powtarzalny, podpisany release i bezpieczna aktualizacja | `ready` |
| [F-003 · Sesja i dane offline](./features/F-003-sesja-i-offline/README.md) | Wiarygodny stan konta/sync bez utraty outboxu | `in_progress` |
| [F-004 · E-mail i hasła](./features/F-004-email-i-hasla/README.md) | Rejestracja, odzyskanie dostępu i zmiana adresu e-mail | `in_progress` |
| [F-005 · Google](./features/F-005-google/README.md) | Bezpieczny login i jawne łączenie metod | `ready` |
| [F-006 · Zarządzanie kontem](./features/F-006-zarzadzanie-kontem/README.md) | Tożsamość konta, operacje i skuteczne usuwanie danych | `ready` |
| [F-007 · Prywatność i wsparcie](./features/F-007-prywatnosc-i-wsparcie/README.md) | Prywatność, warunki usługi/informacje prawne, dostępność i wsparcie | `ready` |
| [F-008 · Jakość i operacje](./features/F-008-jakosc-i-operacje/README.md) | Dowody testów, diagnoza awarii i odtwarzanie usługi | `in_progress` |

## Zależności i kolejność

1. **Pierwszy zalecany krok implementacji: F-008/T-001 — rzeczywisty PostgreSQL w CI i brak zielonych skipów.** Równolegle F-008/T-002 izolacja/konfiguracja i czysty komponent F-004/T-001 hasher/walidacja z testami; bez przełączania auth istniejących użytkowników.
2. Fundament sesji F-003/T-001 i dziennik konta/revisions F-008/T-003, backend/Android wyniki i własność kolejki F-003/T-003/T-002. Infrastruktura dziennika jest wspólna dla bezpieczeństwa/usuwania, nie osobny duplikat w każdym tasku.
3. Poczta/odzyskiwanie F-004/T-002, limiter T-003, Google F-005 i operacje T-004/T-005; API + UI + testy pionowo. W tle przegląd dostawców/prawa F-007 może zacząć się przed gotowym kodem.
4. Konto/usuwanie F-006, profil/kolejki F-003/T-004, raport/warunki/publiczny serwis i minimalizacja F-007; kopie/alerty/budżet F-008/T-003/T-004. Do aktywacji procesu wymagane kompletne zabezpieczenia i testy granic, nie tylko przycisk.
5. F-002 release/Console i syntetyczna próba starego debug oraz Play→update; prawdziwe ID/domena/umowy/kwoty/kontakty muszą być uzupełnione. Backup/restore, S24/16 KB/App Links/Google i wszystkie A-xx są gate, nie obietnicą z kompilacji.
6. F-001/T-002: osobno internal, closed i rozszerzenie po 7 dniach/miarach, z kontrolą krajów. P1 wymagane bezpieczeństwem przed closed, pozostałe przed rozszerzeniem. Nie publikujemy open/production w E-001.

To kolejność integracji, nie nakaz jednego wielkiego PR ani czekania z każdym niezależnym komponentem na cały poprzedni feature. Taski wskazują start od **kontraktu** oraz późniejszy warunek integracji/odbioru; nie tworzymy koła „najpierw gotowe wszystkie features”.

W powyższej liście prefiks `E-001/` jest domyślny. Kontrakty [E-002](../E-002-szybka-nauka/README.md) obowiązują przy regresji nauki/importu, ale nie są listą prac do ponownego wykonania.

## Poza zakresem i decyzje

Bez nowych trybów nauki, płatności, społeczności, voice/mikrofonu/STT, pełnego panelu WWW i migracji całej architektury auth. Nie zmieniamy gotowości kart ani limitów importu.

Zamknięte zasady logowania: wymaganie weryfikacji, hasła/reset, dołączanie Google/metod, zmiana/korekta adresu i skutki dla sesji. [Stan pięciu projektów F-004 i ich pozostałe zależności](./features/F-004-email-i-hasla/README.md#stan-po-zbiorczym-domknięciu-zasad-logowania-i-danych-logowania) oddziela przygotowany kontrakt od gotowości do implementacji.

Zamknięte także decyzje produktu Android/offline: lokalny logout bez sieci z odroczonym odwołaniem, blokada nauki po potwierdzonej utracie sesji bez kasowania pracy oraz trwałe local-first istniejącego profilu. [Stan czterech projektów F-003](./features/F-003-sesja-i-offline/README.md) obejmuje także projekt snapshot/cursor; wskazuje osobno przegląd protokołu/idempotencji/retencji oraz przejście starych instalacji.

Zamknięte decyzje konta/usuwania: natychmiastowa blokada, 7 dni na odstąpienie, potem do 7 dni na purge (maksymalnie 14 dni), samoobsługowy WWW oraz nowe puste konto po completed. [Projekty F-006 i ich zależności](./features/F-006-zarzadzanie-kontem/README.md) obejmują grace/cofnięcie, pauzę zadań, niewysłaną pracę, manifest i rejestr restore.

Zamknięte decyzje produktu [F-007](./features/F-007-prywatnosc-i-wsparcie/README.md): bez raw diagnostyki, logi 7 dni/metryki 30 dni, kopie do około 30 dni (zmiana 18.11.2026); obecne/planowane usługi poza EOG po wymaganej weryfikacji, dokumenty/pomoc PL/EN/ES, proste potwierdzenie 18+ i osobne warunki, cel odpowiedzi człowieka do 2 dni roboczych. Cztery projekty obejmują retencję/dostawców, raport bez LLM, akceptację/istniejące konta, lokalne alarmy i WWW.

Zamknięte także bloki [F-008](./features/F-008-jakosc-i-operacje/README.md) i [F-002](./features/F-002-wydanie-play/README.md): CI/PG i urządzenia, izolowane środowiska, dodatkowa infrastruktura do 50 EUR/miesiąc, backup wyłącznie w Railway (PITR + dzienne, decyzja 18.11.2026)/RPO 1 h/RTO 24 h od wykrycia, dziennik konta w bazie ze śladem w logach i restore bez cofnięcia haseł/adresów, operator/e-mail, budżet AI WARN/HARD oraz aktualny release/Play/kraje. Nowy applicationId, brak planowego resetu po becie. Kwot AI nie wybrano celowo; konfiguracja obu progów jest obowiązkowa przed uruchomieniem.

### Co rzeczywiście pozostaje przed uruchomieniem

| Bramka | Właściciel / moment |
|---|---|
| Nazwa, domena i nowy applicationId | Właściciel; ID/nazwa przed pierwszym uploadem, domena przed mailami/WWW/App Links |
| Rzeczywisty typ/status/deklaracje Play i publikowane dane | Właściciel według F-002/T-002; nie zgadujemy na podstawie opłaty w 2026 |
| Faktyczne kraje testerów i właściwy przegląd prawa/licencji/DPA/transferów | Właściciel z odpowiednią weryfikacją F-007/F-002; przed użyciem dostawcy/dodaniem kraju |
| Model/cennik, WARN/HARD AI, hosting/kopie/koszt i prywatne klucze/kontakty | Operator według F-008; brak zgody na zakup/auto-topup i brak wartości = brak uruchomienia integracji |
| Implementacja i migracje z zachowaniem User.id/pracy | Wykonawca po osobnym zleceniu, najpierw syntetyczna próba; starej instalacji nie kasujemy na ślepo |
| Wyniki CI/A-01…A-24, Play/device/restore i samodzielna ścieżka ≥5 osób | Wykonawca/operator; podpisany build, rzeczywiste środowisko i dowód, nie sam opis |

Nie ma kolejnego nieopisanego bloku biznesowego. Te bramki nie dają „gotowej bety” i nie są żądaniem ponowienia uzgodnionych odpowiedzi. Historyczna analiza pozostaje źródłem; obowiązuje bieżący [F-001/T-001](./features/F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md) i taski.

**Dowody ukończenia:** specyfikacja i decyzje zapisane; brak implementacji/wyników runtime, zakupów, deployu, operacji na danych i publikacji. `ready` epica to gotowość zakresu do wykonania, nie odbiór aplikacji ani prawne zatwierdzenie.

**Weryfikacja dokumentacji 17.11.2026:** 34 dokumenty E-001, 428 lokalnych linków/odnośników i 41 linków przychodzących z repo, 32 unikalne ID features/tasków; indeksy/statusy zgodne. 15 kontroli tekstowych kontraktów pokrywa decyzje obu końcowych bloków i integracje. To kontrola dokumentacji, nie wyniki CI, urządzenia, Play lub restore.
