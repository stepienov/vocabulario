# T-004 · Monitoring, kontrola kosztów i incydenty

**ID:** `E-001/F-008/T-004` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Jakość i operacje](../README.md). **Źródło:** B-13 i decyzje z 17.11.2026.

## Rezultat i zależności

Operator nie dowiaduje się o utracie kopii lub budżetu dopiero od testera. Właściciel sam odbiera alerty **e-mail**, bez deklaracji dyżuru 24/7. Pierwsza odpowiedź człowieka na zgłoszenie pozostaje celem 2 dni roboczych; incydent ma pilną osobną ścieżkę.

**Start:** [T-002 konfiguracja](./T-002-srodowiska-i-konfiguracja.md), [T-003 kopie/dziennik](./T-003-backup-rejestr-i-odtwarzanie.md), [F-007 minimalizacja](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md). **Integracja:** gate release T-001 i protokoły AI/jobs E-002. Bez nowych funkcji nauki, FCM i SaaS helpdesk.

## Monitoring bez nowego SDK

Projekt: **UptimeRobot Free**, sprawdzanie publicznego HTTPS `/health/ready` co 5 min i strony prawnej; alert e-mail dostawcy niezależny od Resend aplikacji. Bez sekretnego parametru URL, loginu testera, fragmentów treści czy wykonywania generacji. Przed kontem/uruchomieniem potwierdzić aktualną darmową ofertę i rolę/retencję danych operatora; nie włączać płatnych integracji. [Cennik](https://uptimerobot.com/pricing/) sprawdzony 17.11.2026; nie zakładać płatnego SLA, minutowego interwału ani płatnych alertów certyfikatu.

Diagnostyka Androida: raporty pre-launch, Android vitals/crash/ANR tam, gdzie Play udostępnia dane dla danego tracka/próbki, własne testy i świadome raporty F-007. Brak nowego Crashlytics/Sentry/analytics SDK w tej becie. Brak danych Vitals nie oznacza zera crashy; przy 5–30 osobach konieczne ręczne potwierdzenia. Mapowanie obfuskacji/symboli zachować przy buildzie.

Backend: własne logi do 7 dni i metryki bez treści 30 dni; panel operatora i alarmy nie zawierają adresu/tekstu biblioteki. Jeśli hosting trzyma stdout dłużej, nie wysyłać tam danych użytkownika/identyfikatorów; ewentualny nieusuwalny osobowy log dostawcy wymaga ujawnionego wyjątku prawnego przed startem, nie cichego odstępstwa od decyzji.

Maintenance backendu co 15 min wylicza tanie agregaty z indeksów/stanów, bez wywołań LLM i N+1 per karta. Lokalny deduplikowany alert trafia do operatora; publiczny health nie ujawnia szczegółów. Dla utraty heartbeat samego maintenance/readiness zewnętrzny monitor musi zobaczyć degradację, nie wieczne 200 martwego procesu.

| Sygnał | Próg / reakcja projektowa |
|---|---|
| Publiczne not-ready | Dwie kolejne nieudane próby 5-min; e-mail DOWN/RECOVERY, brak deklaracji wykrycia w sekundę |
| Backup | 45 min od startu ostatniego ukończonego snapshotu: pilny alarm; 55 min: ochrona zapisów T-003; 60 min: naruszenie celu, nie opóźnione uruchomienie ochrony |
| Journal | Nieopublikowany intent >5 min lub uszkodzony digest: pilny alarm, brak ACK/nieodwracalnego następnego kroku |
| Purge | Brak postępu >1 h, błąd lease/manifestu albo zbliżenie do `purge_due_at` na <24 h: pilny alarm i ręczna ocena |
| Auth/mail | Wyjście poza limity globalne, terminal failure, niedostarczalność lub najstarszy gotowy mail >10 min: alarm bez payloadu; zasady retry F-004 |
| Support | Sprawa bez pierwszej odpowiedzi zbliżająca się do 2 dni roboczych/przekroczona: kolejka operatora, auto-ACK nie liczy się jako odpowiedź |
| Zasoby | DB/volume ≥80%, utrzymujący się brak pamięci/restarty, wyczerpanie puli: alarm, nie automatyczne powiększenie płatnego planu |

Deduplikacja `(environment, alert_kind)`, start/zmiana ważności/recovery i przypomnienie najwyżej raz na 6 h. Alerty wysłane Resend są tylko dodatkiem: utrata poczty/maintenance musi mieć niezależny e-mail monitoringu/platformy. Test odłączenia potwierdza odbiór przez operatora; prywatnego adresu nie zapisujemy w tasku.

## Budżet infrastruktury

Najpierw local/CI, staging tylko na okna testów, istniejący Railway backend+WWW, bez nowego hostingu marketingowego, darmowy monitoring. Infrastruktura dodatkowa możliwie 0, planowane maksimum **50 EUR/miesiąc**, osobno od AI i domeny.

Przed włączeniem kosztów: spis istniejących zasobów/planów i pomiar RAM/CPU/egress/rozmiaru DB, prognoza kosztu staging i retencji, S3 storage/requests/egress/wersje oraz podatek/kurs z buforem. Cel roboczy prognozy ≤40 EUR, pozostawiający 10 EUR na wahania; nie deklarować, że dolar równa się euro lub że abonament i zawarte kredyty liczą się podwójnie.

[Railway](https://docs.railway.com/pricing/plans) publikuje m.in. Hobby 5 USD/Pro 20 USD z zawartym usage oraz opłaty RAM/CPU/volume/egress; to nie oferta zerowego dodatkowego kosztu. [S3](https://aws.amazon.com/s3/pricing/) rozlicza storage/requests/transfer według regionu, bez gwarancji free tier. W kosztorysie podać przyjęte wielkości i datę/kurs, nie wymyśloną kwotę „wszystko za 0”.

Przy prognozie >40 EUR alarm, >50 EUR brak kolejnego kosztownego rozszerzenia/nowego środowiska bez decyzji. Nie wyłączać z dnia na dzień DB, backupu, usuwania lub przechowywania danych dla ratowania rachunku. Rozwiązanie pojemnościowe poza limitem wraca do właściciela jako konkretna oferta; nie obniża potajemnie RPO/retencji. Budżet jest kontrolą kosztu, nie magicznym nieprzekraczalnym limitem faktury platformy.

## Budżet AI i dokupowanie — kontrakt

Właściciel świadomie odkłada kwoty do konfiguracji przed startem. Wymagane `AI_MONTHLY_WARN_USD > 0`, `AI_MONTHLY_HARD_USD >= WARN`, osobny limit małego staging smoke. Jednostka rachunkowa USD; przy wyborze innej waluty jawna konwersja. Puste/zerowe wartości nie znaczą „nielimitowane”.

Do WARN ostrzeżenia przy 70/90%; po WARN działanie dopuszczone do HARD z wyraźnym alertem. Dodatkowe środki kupuje **ręcznie właściciel** w granicach tych limitów; dokupienie salda nie podnosi HARD. Bez integracji automatycznego zakupu kartą, auto-recharge i arbitralnego nowego limitu.

### Egzekwowanie

- Wspólny miesięczny licznik UTC w PostgreSQL, Decimal/najmniejsze jednostki, nie float. Tabela okresu: `spent`, `reserved`; rezerwacja przed każdym rzeczywistym płatnym wywołaniem na bazie zatwierdzonego cennika modelu i maksymalnych tokenów wejścia/wyjścia. Nie rezerwować tylko jednej fazy wieloetapowego importu.
- Atomowa krótka blokada budżetu → rezerwacja z call UUID → commit → zewnętrzne wywołanie poza DB → rozliczenie rzeczywistego usage. Repliki dzielą licznik. Równoległe żądania nie wydają jednocześnie tego samego pozostałego limitu.
- Faktyczna cena/brak usage/timeout może być nieznany. Nie zwalniać takiej rezerwacji jak po pewnym braku wywołania; stan `unresolved`, konserwatywny koszt i ręczne uzgodnienie z dostawcą. Retry dostawcy to nowe możliwe obciążenie i osobna rezerwacja, nie darmowa powtórka.
- Nieznany model/cennik lub brak rezerwacji daje 503 `ai_budget_unavailable`, nie darmowy fallback. Finalne `max_tokens` musi być ograniczone; jeśli oszacowany maksymalny koszt nie mieści się w HARD, nie rozpoczynać HTTP.
- Przy HARD / braku salda dostawcy: jawne `ai_budget_exhausted` z bezpiecznym terminem/krokiem pomocy; zadania pozostają w nowym stanie `waiting_budget`, bez `ready/learnable` na błędnym payloadzie. Nie liczyć czekania jako utraconych retry i nie tworzyć kolejnego joba.
- `waiting_budget` jest stanem/przyczyną oczekiwania zadania, nie nowym skrótem gotowości karty. Publiczna karta zachowuje właściwe pending/preparing/learnable i flagę examples_pending; kolejka profilu nie przechodzi przed learnable/adaptive write. Wykryty rzeczywisty koszt wyższy od rezerwacji zapisujemy w całości i alarmujemy, nie obcinamy metryki do HARD.
- Przegląd `waiting_budget` w istniejącym maintenance co 15 min i po jawnej zmianie budżetu operatora; bez pętli pollingu Androida/nowego LLM „sprawdź saldo”. Wznawiać oryginalną fazę z kontrolą owner/lifecycle i obecnych kontraktów importu.
- Reset okresu nie zeruje nierozliczonych rezerwacji z poprzedniego miesiąca. Każde wywołanie przypisane do okresu rozpoczęcia; pozostałe zobowiązania pokazywane operatorowi. Po restore operacji AI nie wznawiać przed uzgodnieniem wydatków/rezerwacji z metrykami dostawcy.

Nie blokować loginu, praw/usuwania, zwykłego sync ani lokalnej nauki bez kolejnego AI. UI odróżnia „czeka na dostępność generowania” od błędu słowa/hasła; wszystkie komunikaty w 17 locale. Limity 25/import i 25 kart/profil/UTC pozostają; budżet ich nie zeruje ani nie uzasadnia duplikowania kart po wznowieniu.

## Incydent i naprawa

P0: mieszanie kont, utrata/potencjalne ujawnienie danych, cofnięte usunięcie, niebezpieczna zmiana auth — zatrzymać rollout i dotknięte zapisy, zachować minimalny dowód bez treści, eskalować do operatora. P1: niedostępność/część funkcji lub przekroczone cele — ocenić zakres, wyłączyć tylko wadliwą funkcję po jawnej informacji, nie kasować cache.

Kolejność: wykrycie/timestamp → triage → ograniczenie skutków → komunikat → naprawa lub restore T-003 → staging/smoke → osobna decyzja o wznowieniu → krótki opis przyczyny i zabezpieczenia przed powtórką. Nie cofać schematu/bazy, aby naprawić zły ekran. Android naprawia nowy versionCode; opublikowanego pakietu nie „obniżamy”.

Dla naruszenia danych ocenić z właściwym przeglądem obowiązek zgłoszenia/komunikacji (m.in. art. 33/34 GDPR, termin 72 h tam, gdzie ma zastosowanie). Nie każda awaria jest naruszeniem, a cel supportu 2 dni roboczych nie zastępuje terminu prawnego. Brak operatora nie jest zgodą na ignorowanie alertu: wstrzymać rozszerzanie grupy, zaplanować zastępstwo przed nieobecnością, bez publikowania prywatnych kontaktów.

## Akceptacja

- [ ] Wymuszone not-ready, brak backupu/journalu, awaria Resend i maintenance dają właściwy niezależny e-mail, bez lawiny i danych konta.
- [ ] Dwie repliki, timeout po płatnym HTTP, brak usage i granica miesiąca nie omijają HARD ani nie zwalniają niepewnego kosztu.
- [ ] Wyczerpanie/wznowienie nie tworzy kolejnych LLM/jobów/kart; zadanie wraca do swojej fazy, import i gotowość bez regresji E-002.
- [ ] Limity AI rzeczywiście ustawione przed startem, faktury/usage mają właściciela; test nie uznaje samego alertu za hard cap.
- [ ] Operator potrafi zatrzymać rollout, sprawdzić alert i wykonać runbook bez sekretów w instrukcji; zapisano ćwiczenie incydentu i kosztorys w limicie.

**Poza zakresem:** zakupy i zmiany kont teraz, całodobowy zespół SRE, automatyczna akceptacja rachunków, nowe limity języków lub płatności użytkownika. **Wynik:** projekt, bez dodania SDK/monitorów i bez rzeczywistych wywołań.
