# T-001 · Decyzje startowe i zakres bety

**ID:** `E-001/F-001/T-001` · **Status:** `done` — decyzje i specyfikacja, bez implementacji produktu · **Priorytet / rozmiar:** P0 / S.  
**Feature:** [Prowadzenie bety](../README.md). **Źródło:** B-00, [rozdział 12 analizy](../../../sources/analiza-2026-11-17.md#12-decyzje-do-podjęcia-przed-implementacją).

## Cel i zakres

Uzgodnić i zapisać decyzje, od których zależy kod: odbiorcy/wiek/track, moment weryfikacji e-maila, łączenie Google, outbox przy reauth/logout, przypomnienia, operacje konta, dostawcy/retencja, staging i odpowiedzialność za wydanie. Oddzielić wymagane P0 od świadomie odłożonego P1.

**Zależności:** brak technicznych; potrzebne decyzje właściciela, bez ich domyślnego zatwierdzania przez wykonawcę.

## Uzgodnienia z 17.11.2026

| Obszar | Uzgodnione | Kontrakt / bramka wykonawcza |
|---|---|---|
| Skala i rekrutacja | Orientacyjnie 5–30 osób, początkowo znajomi, bez kampanii reklamowej; odbiorcy dorośli. Bez sztucznego ograniczania języków; potencjalni testerzy m.in. dla angielskiego, hiszpańskiego, francuskiego i chińskiego. Oświadczenie 18+ bez DOB/dokumentów; osobna akceptacja warunków | Docelowo świat, na start tylko kraje rzeczywistych testerów po kontroli F-002/T-002; PL/EN/ES dokumentów to nie ograniczenie języków nauki |
| Cel | Stabilny i płynny core, profesjonalny wygląd, samodzielna obsługa; zbieramy błędy i sugestie | Miary epica i F-008/T-001; fizyczny S24, wersja Androida do odczytu przy teście; termin po gate, nie wybrana data |
| Dostęp | Zatwierdzone internal → closed, bez publicznej premiery E-001. Link Play i samodzielne konto aplikacji | Konto powstało w 2026, prawdopodobnie opłacone; typ/weryfikacje/upload niepotwierdzone. F-002/T-002 obejmuje obie gałęzie i warunkowe 12/14 |
| Model zarabiania | Beta bez płatności i waluty. Po becie przewidywany podstawowy bezpłatny zakres i ewentualne płatne dodatki, bez zatwierdzonego cennika; osobny przyszły temat przed szerszą promocją | Docelowy model poza tym epikiem |
| Weryfikacja adresu | Nowe i dotychczasowe niezweryfikowane konta e-mail wymagają potwierdzenia przed pełnym korzystaniem, bez dodatkowego okresu przejściowego i utraty danych; dostępne resend, korekta adresu, wyjście i pomoc. Bez zbędnego drugiego maila dla prawidłowo zweryfikowanego adresu Google | Dokładne ekrany, uprawnienia API, parametry tokenów i techniczna migracja obecnych kont do opisania w F-004/F-003 |
| Linki i poczta | Potwierdzenie adresu i reset hasła działają także na prostej stronie HTTPS na komputerze/bez aplikacji; bez pełnego portalu konta i bez logowania linkiem do biblioteki. Resend Free zaakceptowany warunkowo dla własnej domeny, którą właściciel dopiero kupi; dokumentacja dostawcy potwierdza taki model | Projekt w F-004/T-002; DPA/transfery/retencja, limity, DNS i dostarczenie do domknięcia przed uruchomieniem. Bez zgody na plan płatny |
| Metody logowania | E-mail/hasło i Google mogą prowadzić do jednego konta po jawnym potwierdzeniu własności. Google-only może dodać hasło po ponownym potwierdzeniu Google i wymaganej weryfikacji adresu aplikacji. Samodzielne odłączanie metod poza betą | Kontrakty recent-auth, dodania/łączenia, obsługa kolizji i wyścigów; bez automatycznego łączenia po samym adresie |
| Zmiana e-maila | W pierwszej becie, po ponownym potwierdzeniu tożsamości hasłem lub podłączonym Google i potwierdzeniu nowego adresu. Bez wymogu dostępu do starej skrzynki; na stary potwierdzony adres zawiadomienia o rozpoczęciu i zakończeniu. Dotychczasowe Google pozostaje podłączone. Stary adres aktywny do zakończenia zmiany, potem wszystkie sesje aplikacji odwołane i ponowny login | Kontrakt API/UX, TTL i awarie rozpisane w F-004/T-004; pozostał przegląd zależności Android/offline i zgodnego wydania |
| Hasła i sesje | Reset odwołuje wszystkie sesje aplikacji. Zmiana hasła i dodanie pierwszego hasła do Google-only odwołują pozostałe, a bieżące urządzenie zachowuje dostęp po odnowieniu sesji. Dodanie hasła wysyła zawiadomienie na adres aplikacji. Reauth nie kasuje outboxu | Mechanizm transakcji/rotacji i wyścigów, egzekwowanie odwołania w API, odtworzenie po utracie odpowiedzi |
| Polityka nowych haseł | 15–128 znaków, bez obowiązkowych klas znaków; Unicode i spacje bez trimowania/obcinania. Wklejanie i menedżery haseł dozwolone. Dotyczy rejestracji, resetu, zmiany i dodania hasła | F-004/T-001: Unicode scalar, Argon2id i proste ustanowienie nowego hasła dla legacy bez zmiany User.id; nie kopiujemy bcrypt jako nowego hasła. Brak zgody na wykonanie migracji teraz |
| Reset i dowód adresu | Skuteczny reset hasła przez link na bieżący adres również potwierdza ten adres, bez kolejnego maila weryfikacyjnego. Wszystkie sesje odwołane, nadal wymagany ponowny login | Powiązanie dowodu z aktualną rewizją adresu i atomowość w F-004/T-002; stary link nie potwierdza zmienionego adresu |
| Dowód przy zmianie hasła | Zmiana istniejącego hasła w ustawieniach wymaga obecnego hasła; przy zapomnianym haśle reset przez e-mail. Świeże Google nie jest alternatywnym dowodem dla tej operacji w becie | Spójność API/UX i recent-auth. Dodanie pierwszego hasła do Google-only oraz zmiana adresu zachowują własne, wcześniej zatwierdzone zasady |
| Dołączenie Google | Dopuszczone różne adresy po potwierdzeniu obu tożsamości; bez zmiany adresu aplikacji/scalenia i bez przepinania Google z innego ID. Pozostałe sesje odwołane, bieżąca odnowiona, zawiadomienie na adres aplikacji | Projekt F-005/T-001: nonce, recent-auth, konflikty i atomowość; parametry walidatora/limitów, retencja i zgodne wydanie do domknięcia |
| Google a zewnętrzna skrzynka | Niezweryfikowany adres aplikacji spoza wiarygodnego Gmail/Workspace wymaga naszego linku; samo historyczne `email_verified` zewnętrznego adresu u Google nie wystarcza. Już potwierdzonego adresu aplikacji nie weryfikujemy ponownie | Dokładne claimy i reguły zgodności adresu w F-005/T-001, wspólne z F-004. Zmiana adresu aplikacji nie jest cofana przez Google |
| Oczekująca zmiana i korekta adresu | Tylko jedna oczekująca zmiana; nowy poprawnie uwierzytelniony wniosek zastępuje poprzedni. Resend nie unieważnia linków tego samego wniosku. Przy korekcie niezweryfikowanego adresu bez zawiadomień na starą potencjalnie cudzą skrzynkę | Projekt F-004/T-004; testy zastępowania, anulowania i wyścigów są częścią późniejszej implementacji |
| Nieudany login hasłowy | Jeden komunikat bez ujawniania istnienia/rodzaju konta: „Nieprawidłowy e-mail lub hasło”, 401 `invalid_credentials`. Reset i Google dostępne każdemu, awarie i limity mają własne komunikaty | Projekt F-004/T-003 obejmuje timing, limity i mapowanie błędów; bez powrotu do szczegółowych publicznych kodów |
| Offline i stare dane | Zachowanie niewysłanej pracy przy reauth, sync/anuluj/jawne odrzucenie przy logout, brak mieszania kont. Minimalne zmiany, bez refaktoryzacji przy okazji. Obecny backend zawiera postęp więcej niż jednego użytkownika i konta automatycznych testów | Macierz stanów i projekt migracji cache/outboxu opisane w F-003; konkretna procedura obecnych instalacji do uzgodnienia z F-002/F-008. Bez zgody na kasowanie danych; testy destrukcyjne wyłącznie izolowane |
| Logout bez sieci | Dopuszczone lokalne wylogowanie po rozstrzygnięciu niewysłanej pracy. Aplikacja usuwa aktywny dostęp na telefonie, a odwołanie sesji serwerowej ponawia po odzyskaniu połączenia; nie udaje natychmiastowego odwołania | Projekt E-001/F-003/T-002: zaszyfrowane zlecenie, restart i nieznany wynik rotacji; parametry retencji do przeglądu F-007 |
| Potwierdzona utrata sesji a offline | Jednoznaczne odwołanie/wygaśnięcie potwierdzone przez serwer blokuje bibliotekę i naukę do ponownego loginu tego samego właściciela; dane i niewysłana praca pozostają. Zwykła utrata sieci/timeout nie odbiera nauki offline przy znanym uprawnionym koncie i cache | Macierz stanów i bariery workerów w E-001/F-003/T-002; bez mieszania tego stanu z wymaganiem weryfikacji adresu |
| Edycja profilu offline | Poziom i ustawienia istniejącego profilu zapisujemy lokalnie z trwałą kolejką; UI oddziela zapis lokalny od serwerowego, konflikt nie usuwa edycji. Utworzenie nowego profilu wymaga sieci, wybór już pobranego działa offline | Projekt E-001/F-003/T-004: rewizje, retry i jawne rozwiązanie konfliktu bez nadpisywania innego profilu |
| Odstąpienie od usunięcia | Konto blokowane i sesje odwołane od przyjęcia; 7 pełnych dni na wycofanie. W tym okresie zachowane dane/progress i lokalna praca; zadania wstrzymane, nie destrukcyjnie anulowane. Cofnięcie wymaga dowodu właściciela i nowego loginu, nie wskrzesza starych sesji | Projekt E-001/F-006/T-002; retencja procesorów/backupów i wykonawczy restore do sprawdzenia z F-007/F-008 |
| Termin realizacji usunięcia | Po 7 dniach odstąpienia do kolejnych 7 dni na usunięcie aktywnych danych: łącznie maksymalnie 14 dni od przyjęcia. To wyjaśnione i zatwierdzone liczenie 7+7, nie obietnica wymazania wszystkich kopii w 7 dni | Wykonawca mapuje dane bez FK, bariery workerów, alerty i jawne wyjątki; szczegóły F-006/F-007/F-008 |
| Usuwanie bez aplikacji | Samoobsługowy formularz WWW z dowodem hasłem/podłączonym Google albo linkiem na wcześniej zweryfikowany adres; pomoc awaryjna. Bez wymogu instalacji i bez portalu biblioteki | API/dowody i ścieżki opisane w F-006/T-002, WWW w F-007/T-004; nie ma usuwania po samym podanym e-mailu |
| Powrót po usunięciu | Po completed można utworzyć nowe puste konto tym samym adresem/Google, z nowym ID. Nie przywracamy starego postępu/kolejek; podczas grace/purge nie reaktywujemy konta zwykłym loginem | Ochrona owner ID i lifecycle F-003/F-006; inny telefon offline reaguje po otrzymaniu wiarygodnego stanu, nie ma obietnicy natychmiastowego zdalnego wymazania |
| Powiadomienia | Tylko lokalne przypomnienia, bez serwerowego push | Szczegóły reboot/strefa/uprawnienia i zmiana konta w odpowiednim feature |
| Diagnostyka | Bez pełnych promptów/odpowiedzi/notatek/zapytań w diagnostyce; minimalne logi techniczne 7 dni, metryki kosztów bez treści 30 dni. Nie dotyczy potrzebnych danych nauki i świadomego zgłoszenia | Wykonawca obejmuje DB/stdout/hosting/logcat/wyjątki, historię/cache i skuteczny cleanup F-007/F-008 |
| Kopie i dostawcy | **Zmienione 18.11.2026:** backup wyłącznie w Railway (PITR + kopie dzienne), bez AWS/zewnętrznego magazynu; retencja kopii do około 30 dni, bez tygodniowych i miesięcznych. Obecne/planowane usługi także poza EOG dopuszczone po wymaganej weryfikacji umów/zabezpieczeń/informacji | Rzeczywiste konto/plan, produkty/modele, DPA/transfery/wyjątki, koszt i rejestr restore. Bez obietnicy EU-only, ZDR i zakupu teraz |
| Dokumenty i pomoc | PL/EN/ES; monitorowana poczta i raport treści wewnątrz aplikacji, bez nowego helpdesk. Cel pierwszej odpowiedzi człowieka do 2 dni roboczych, nie termin naprawy ani dyżur 24/7 | Konkretny kontakt/dostawca skrzynki przy domenie, właściciel obsługi i incydenty F-008; przegląd prawny i zrozumiałość informacji |
| Zgodność i operacje | Osobny publiczny serwis aplikacji i własna domena. Właściciel chce inną nazwę niż początkowe propozycje i poda ją później; żadna nazwa/końcówka nie jest wybrana. Nie zakładamy gotowych stron prawnych/pomocy. Priorytet najniższych rozsądnych kosztów, uzasadnione dodatkowe usługi dopuszczalne po akceptacji | Konkretna nazwa/rejestrator i hosting serwisu, adres pomocy/koszt, staging oraz odpowiedzialność za akceptację prawną; propozycje cen w F-007/T-004 nie oznaczają zakupu |

Kolumna kontraktów wskazuje właścicieli wykonania. Techniczne projekty wymienione niżej są już zapisane w taskach; zwroty o migracji/parametrach nie oznaczają kolejnej otwartej ankiety. Fakty z rzeczywistych konsol, prawo, nazwa/domena i kwoty pozostają świadomymi bramkami uruchomienia.

„Brak bugów” jest celem jakościowym, nie obietnicą absolutnego braku błędów. Warunek dopuszczenia musi mieć mierzalne kryteria krytyczności, testy i dowody.

### Zamknięty blok decyzji: uwierzytelnianie i dane logowania

Zasady haseł/resetu, weryfikacji, Google, dołączania metod, zmiany/korekty adresu i skutków dla sesji są ustalone. W F-004 wszystkie pięć tasków ma projekt techniczny, a F-005 opisuje wspólny Google/recent-auth. Nie otwieramy ponownie zatwierdzonych pytań przy pracy nad kolejnym ekranem.

Przegląd zależności sesji Androida/offline, planu testów i retencji jest zapisany w taskach. Rzeczywiste prawo/konfiguracja dostawców i publikacja nadal mają bramki. Zamknięcie decyzji kończy zakres tego taska, nie implementację ani epic.

### Zamknięty blok decyzji: Android i offline

Zatwierdzono zbiorczo lokalny logout offline z odroczonym odwołaniem, blokadę po potwierdzonym odwołaniu bez utraty pracy oraz trwałe local-first istniejącego profilu. [F-003](../../F-003-sesja-i-offline/README.md) zawiera projekty wszystkich czterech tasków i listę konkretnych pozostałych przeglądów technicznych. Nie pytamy ponownie o te warianty przy każdym ekranie.

Projekt watermark obejmuje snapshot PostgreSQL, transakcje długo otwarte i tombstones 30 dni. Procedura obecnych instalacji/nowego pakietu oraz granica zgodności są w F-002/T-001, a `db_epoch`, odwołanie sesji i restore recovery w F-008/T-003. Nie są to nowe funkcje produktu.

### Zamknięty blok decyzji: konto i usuwanie

[F-006](../../F-006-zarzadzanie-kontem/README.md) ma projekty obu tasków: tożsamość/metody konta oraz usuwanie/cofnięcie. Ustalono 7 dni na odstąpienie + do 7 dni na purge, samoobsługę WWW i możliwość nowego pustego konta po zakończeniu. W okresie grace nie kasujemy danych ani nie anulujemy destrukcyjnie importu; zwykły login nie cofa procesu.

Manifest i wyjątki ma F-007, trwały rejestr request/cancel/purge i restore F-008/T-003, alerty F-008/T-004, a zgodne wydanie F-002. Ich potwierdzenie w rzeczywistych usługach jest odbiorem wykonania, nie zmianą terminów usuwania.

### Zamknięty blok decyzji: prywatność i wsparcie

[F-007](../../F-007-prywatnosc-i-wsparcie/README.md) ma projekty czterech tasków. Zatwierdzone: brak raw diagnostyki, logi 7 dni/metryki 30 dni, backupy do około 30 dni (zmiana z 27 dni 18.11.2026), transfery poza EOG warunkowo po weryfikacji, PL/EN/ES, oświadczenie 18+ i osobne warunki, pierwsza odpowiedź człowieka do 2 dni roboczych. Czas odpowiedzi doprecyzowano po wyjaśnieniu, bez powtarzania pozostałych pięciu decyzji.

Cel 2 dni roboczych zastępuje wcześniejszą rekomendację odpowiedzi w 1 dzień z analizy źródłowej; nie przepisujemy historycznego źródła jako nowej decyzji. Incydenty nadal mają priorytet i osobne terminy prawne.

Ustalono fakty z kodu: payloady 30 dni domyślnie, także pełny import w stdout, wyłączony UI korekty/raportu; oraz ograniczenia dostawców, w tym storage Resend w USA/30 dni. Projekty opisują wszystkie kanały logów, raport bez LLM z kolejką operatora, legal gate istniejących kont, minimalny WWW i alarmy bez funkcji budzika. Proponowane techniczne terminy markerów/tombstones/raportów są oddzielone od zatwierdzonych decyzji.

F-007 rozdziela publiczny/prywatny cache i dane historyczne oraz warunkową allowlistę usług; F-008 dostarcza mechanizm cleanup/backup/restore. Realne umowy/wyjątki prawne, konfiguracja i domena/koszt nadal wymagają sprawdzenia przed użyciem. Nie pytamy ponownie o biznesowy wybór retencji/PL-EN-ES/odpowiedź 2 dni.

### Zamknięty blok decyzji: operacje i wydanie Play

| Zatwierdzona odpowiedź właściciela | Konsekwencja specyfikacji |
|---|---|
| Infrastruktura najtaniej, w razie potrzeby dodatkowo do 50 EUR/miesiąc | F-008/T-002/T-004: local/CI, staging na okna, kosztorys z buforem i brak automatycznych zakupów; AI/domena osobno |
| AI kwotowo dopiero przed startem; ostrzeżenia i kontrolowane dokupienie | F-008/T-004: WARN + nieprzekraczalny admission HARD, wspólne rezerwacje, ręczne doładowanie nie podnosi HARD, brak kwoty blokuje start AI |
| RPO ≤1 h, RTO ≤24 h od wykrycia | F-008/T-003: Railway PITR + kopie dzienne, retencja do ok. 30 dni, dziennik konta w bazie ze śladem w logach i obowiązkowa próba restore; bez 24/7 |
| Operatorem właściciel, e-mail, minimalny monitoring; dostępny S24 | F-008/T-001/T-004: urządzenie i macierz emulatorów, niezależne alarmy; realny Android/kontakt do odczytu przy wykonaniu |
| Internal → closed, publiczna premiera poza E-001 | F-001/T-002 i F-002/T-002: osobne gates, 5–30, warunek 12/14 tylko jeśli rzeczywiście dotyczy konta personal |
| Docelowo świat, rozszerzanie po kontroli krajów rzeczywistych testerów | F-002/T-002: prywatny rejestr kontroli kraju i decyzja przed dodaniem; nie wybieramy wszystkich krajów bez analizy |
| Nowy applicationId, dokładny później; nazwa/domena odłożone | F-002/T-001: gate przed pierwszym uploadem, osobna instalacja debug/Play, brak wymyślonego ID/rebrandingu kodu |
| Zachować konta i postęp bety po premierze | Stabilne User.id, brak planowego resetu; staging/CI tylko syntetyczne. Trzeba uzgodnić pracę starego debug przed odinstalowaniem |

**18.11.2026:** właściciel odrzucił AWS/zewnętrzny magazyn; backup tylko w Railway, akceptując ryzyko jednego dostawcy ([F-008/T-003](../../F-008-jakosc-i-operacje/tasks/T-003-backup-rejestr-i-odtwarzanie.md#decyzja-tylko-railway-18112026)). Wariant UptimeRobot jest projektem wykonawcy opartym o ich udokumentowane możliwości, **nie** zamówieniem ani zatwierdzonymi umowami. Rzeczywisty plan/koszt/DPA i klucze to kontrolowane kroki wykonawcze.

## Uzupełnienia proceduralne, nie nowe pytania

- Mały internal na własnych urządzeniach, następnie zatwierdzone closed 5–30; bez osobnego systemu zaproszeń do kont w aplikacji. Google Play zarządza dostępem do pobrania, nie zabezpiecza publicznego API rejestracji.
- Tester używa konta Google dopuszczonego w Play do instalacji; konto w aplikacji może utworzyć innym e-mailem lub przez Google. Te dwie tożsamości mają różne role.
- Analiza prawna obejmuje wymagania Hiszpanii/UE; konkretne dane identyfikacyjne operatora i konta testerów nie należą do specyfikacji w publicznym repo. Dokumenty publiczne zawierają dane wymagane prawem, po osobnej weryfikacji.

Polityka dotychczasowych kont: potwierdzenie przed pełnym użyciem, bez okresu przejściowego, resetu danych i oznaczania adresów jako zweryfikowanych bez dowodu. Techniczne przejście F-002/F-003/F-004 wymaga próby i osobnego zlecenia, nie ponownego wyboru polityki.

## Pozostałe bramki wykonawcze i właściciele

| Temat / blokowane prace | Kto rozstrzyga i co trzeba przygotować |
|---|---|
| Kanał dystrybucji i [E-001/F-002/T-002](../../F-002-wydanie-play/tasks/T-002-konfiguracja-play-console.md) | Właściciel potwierdza typ i stan konta w Console; wykonawca przygotowuje checklistę bez pozyskiwania dokumentów tożsamości |
| E-001/F-004 i E-001/F-005: wykonanie metod | [Polityka i kontrakty F-004](../../F-004-email-i-hasla/README.md#zatwierdzona-polityka-konta--17112026) oraz Google gotowe do wykonania; implementator weryfikuje je testami, bez nowych skutków ani samodzielnego odłączania |
| E-001/F-003: istniejące instalacje | Implementator wykonuje syntetyczną próbę i kontrolowaną procedurę F-002/T-001; właściciel zatwierdza konkretną operację danych poza repo. Brak pochodzenia = recovery, nie przypisanie po loginie |
| E-001/F-006 oraz F-007: wykonanie retencji i wyjątki | 7+7, logi 7/metryki 30, kopie do 27 i warunkowe transfery zatwierdzone. Wykonawca przegląda manifest/cache, parametry techniczne i możliwości procesorów/restore; właściciel z przeglądem prawnym potwierdza konkretne wyjątki/umowy przed użyciem |
| [E-001/F-007/T-004](../../F-007-prywatnosc-i-wsparcie/tasks/T-004-publiczny-serwis-aplikacji.md), pomoc i treści prawne | PL/EN/ES, kanał i cel odpowiedzi ustalone; projekt WWW/wersji/akceptacji zapisany. Właściciel wybiera odłożoną domenę, rzeczywisty adres/hosting/koszt i zatwierdza przegląd prawny |
| E-001/F-007: treści AI i zgłoszenia | Projekt obejmuje słownik/rejestr, raport od lookup po ćwiczenie, outbox i człowieka. Implementator sprawdza skuteczność polityki/testów; właściciel zapewnia prawdziwy kanał i zgodny tekst |
| E-001/F-008: konfiguracja i pomiary | Cele/koszt zatwierdzone; wykonawca mierzy faktyczne zasoby i robi kosztorys, właściciel wpisuje progi AI/kontakt i zatwierdza konkretną usługę. RPO/RTO i macierz wymagają dowodów, nie ponownej ankiety |

Odbiorcy dorośli nie oznaczają dowolności generacji ani automatycznej klasyfikacji IARC 18+. Wulgaryzm jako hasło słownikowe trzeba odróżnić od niedozwolonych treści/scenariuszy generacji. Politykę i deklaracje sprawdzamy przed publikacją, bez automatycznego zakazu każdego wulgaryzmu i bez traktowania samego „18+” jako zabezpieczenia.

## Jak kończymy przygotowanie

1. Rozstrzygamy pytania biznesowe i operacyjne; odpowiedzi zapisujemy tutaj z konsekwencjami.
2. Wykonawca sprawdza aktualny kod, proponuje kontrakty i podział; nie wybiera za właściciela istotnego zachowania.
3. Doprecyzowujemy features/taski według [kompletności specyfikacji](../../../../zasady.md#kompletna-specyfikacja-przed-implementacją). Najpierw wspólne zasady tożsamości, e-maila, sesji i danych; potem zależne ekrany i integracje.
4. `ready` oznacza zatwierdzony kompletny zakres danego feature'a i wymaganych zależności, nie gotowość do uruchomienia całego epica naraz.
5. Implementacja wyłącznie na osobne zlecenie. Przygotowanie dokumentacji nie oznacza deployu, operacji na danych ani publikacji.

## Kryteria i weryfikacja

- [x] Każda z ośmiu grup decyzji źródłowych ma odpowiedź, uzasadnienie i właściciela.
- [x] Ustalono projekt środowiska z syntetycznymi kontami i osobną bazą testową, nie produkcję.
- [x] Zakres i miary E-001 zapisano; realne niewiadome wskazują blokowane wykonanie.
- [x] Właściwe taski/statusy i indeksy zawierają kontrakty, bez drugiego planu.
- [x] Każda pozostała niewiadoma ma właściciela i wskazane blokowane features/taski.

**Poza zakresem:** implementacja auth, wybór nowych funkcji nauki, automatyczna publikacja.  
**Wynik weryfikacji / decyzje:** zamknięte rundy biznesowe 17.11.2026, przygotowane osiem features i 24 taski z zależnościami oraz bramkami. `done` dotyczy tylko uzgodnień/specyfikacji T-001; nie oznacza wdrożenia, zakupu, ukończenia innych tasków ani prawnej akceptacji.
