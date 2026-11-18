# T-001 · Prywatność, retencja i deklaracje Play

**ID:** `E-001/F-007/T-001` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Prywatność i wsparcie](../README.md). **Źródło:** B-11; F-15 i [wymogi Play](../../../sources/analiza-2026-11-17.md#9-google-play--co-przygotować-poza-kodem).

## Cel i zakres

Uzgodnić faktyczne dane, odbiorców, dostawców i retencję; przygotować publiczną politykę i adres usuwania, Data safety, deklaracje treści/AI i dostęp recenzenta. Polityka dostępna przed rejestracją i w ustawieniach; bez haseł/kont recenzenta w repo.

## Przygotowanie zgodności przed uruchomieniem

- Mapa cel → dane → podstawa prawna → odbiorcy/dostawcy → region przetwarzania/transfer → retencja → sposób usunięcia. Uwzględnić konta, naukę/import, pocztę, Google, hosting/AI, logi i przyszłą diagnostykę.
- Zweryfikować role dostawców, wymagane umowy powierzenia i podstawy transferów poza EOG. Sam wybór europejskiego regionu jednego serwera nie dowodzi lokalizacji wszystkich procesorów.
- Okresy zatwierdzone przez właściciela zapisano poniżej, oddzielnie od propozycji technicznych. Sprawdzić możliwość wykonania, terminy sprzątania i wyjątki dostawców; sama deklaracja TTL nie jest dowodem.
- Polityka prywatności realizuje obowiązek informacyjny; nie zastępuje podstawy prawnej ani osobnych zgód tam, gdzie są wymagane. Nie tworzyć zbiorczego „zgadzam się na wszystko”, nie uzależniać nauki od zbędnej analityki/marketingu.
- Sprawdzić faktyczne cookies/SDK i dostęp do pamięci urządzenia: rozróżnić konieczne/wyłączone z obowiązku zgody od pozostałych. Nie dodawać banera cookies tylko dlatego, że istnieje aplikacja; brak banera też wymaga potwierdzenia konfiguracji strony i SDK.
- Dokumenty publiczne i krótka informacja przed rejestracją muszą odpowiadać rzeczywistym przepływom, w tym wysyłaniu treści do AI. Zatwierdzić języki dokumentów i sposób dostępu dla obsługiwanych odbiorców.

Warunki korzystania/aviso legal są w [E-001/F-007/T-003](./T-003-warunki-i-informacje-prawne.md), bez dublowania polityki i statusów. Powyższe to lista analizy, nie gotowa polityka ani opinia o pełnej zgodności.

### Wejście z zatwierdzonego F-006

[Proces usuwania](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) ma ustalone zachowanie: blokada od razu, 7 dni na wycofanie, potem do 7 dni na usunięcie aktywnych danych (maksymalnie 14 dni). Nie pytamy ponownie o te warianty. Tu trzeba zweryfikować zgodność zobowiązania i wypełnić konkretne okresy/wyjątki:

- prywatne AppLog/LookupEvent/LlmUsage bez CASCADE i raw LlmCallPayload, także payloady historycznie bez wiarygodnego owner;
- dane osobowe, które mogły trafić do współdzielonego cache/słownika — SET NULL nie dowodzi anonimizacji;
- mail i jego webhooki/logi u dostawcy, AI i hosting: dostępne sposoby usunięcia, rzeczywiste okresy i transfery;
- backupy, rejestr usunięć/cofnięć odporny na restore, klucz HMAC oraz retencja pseudonimowego markera/receiptu; brak wieczystej blokady ponownej rejestracji;
- Google na publicznym formularzu, jedynie transakcyjny status w sessionStorage i brak zgody „na wszelki wypadek”; klasyfikacja faktycznie koniecznych technologii;
- jasna informacja, że telefonu offline nie da się wymazać natychmiast, odinstalowanie nie jest żądaniem usunięcia, a cofnięcie nie odzyskuje lokalnej pracy wcześniej świadomie odrzuconej.

Właściciel zatwierdza wyjątki i zobowiązania po inwentaryzacji/przeglądzie prawnym. Nie utożsamiamy zaakceptowanego celu 14 dni dla aktywnego systemu z gotową gwarancją terminu każdego procesora lub backupu.

**Start:** [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md). **Końcowa zgodność:** [E-001/F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md), finalny zestaw SDK/danych z [E-001/F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md) i zakres powiadomień/diagnostyki.

## Zatwierdzone decyzje produktu — 17.11.2026

| Obszar | Decyzja |
|---|---|
| Diagnostyka | Nie utrwalamy pełnych promptów, odpowiedzi, notatek ani wyszukiwanych tekstów w diagnostyce; minimalne logi techniczne 7 dni, metryki kosztów bez treści 30 dni |
| Backupy | Railway PITR (ok. 4 tygodnie) + dzienne (6 dni); do około 30 dni od wykonania, bez tygodniowych i miesięcznych (decyzja 18.11.2026). Bez zewnętrznego magazynu |
| Dostawcy i transfery | Dopuszczone obecne/planowane usługi także poza EOG, dopiero po wymaganej weryfikacji umów, zabezpieczeń i informacji. To nie jest zatwierdzenie dowolnego dostawcy ani gotowy dowód zgodności |
| Dokumenty/pomoc | PL, EN i ES, niezależnie od 17 locale interfejsu i języków nauki |
| Wiek i warunki | Oświadczenie pełnoletności bez daty urodzenia/dokumentów; osobna akceptacja warunków. Prywatność to informacja, nie checkbox zgody na wszystko |

Brak kopii diagnostycznych nie oznacza zakazu zapisu fiszki/postępu ani świadomie wysłanego zgłoszenia. Retencja dostawcy AI/poczty jest osobnym przepływem; nie obiecujemy jej wyłączenia lokalnym przełącznikiem.

## Stan faktyczny i mapa przepływów

Poniższe to odczyt kodu i publicznych dokumentów, **nie konfiguracji produkcji**. Nie odczytano `.env`, konsol dostawców ani danych testerów.

| Cel / dane | Miejsca i odbiorcy | Docelowa kontrola |
|---|---|---|
| Konto, adres, hash hasła, powiązanie Google, sesje | PostgreSQL, Android; [modele](../../../../../../backend/app/models/__init__.py), [auth](../../../../../../backend/app/api/v1/auth.py) | Stabilny User.id, ograniczone odpowiedzi F-006, sekrety tylko w przeznaczonych magazynach F-003/F-004 |
| Profile/języki/poziom, fiszki, import/notatki, historia ocen i kolejki | Backend PostgreSQL i prywatny Room/ustawienia Androida; robocze dane generacji | Dane funkcjonalne właściciela; zachowanie przez grace, manifest purge F-006, bez automatycznego kasowania nieaktywnego konta |
| Tekst wyszukiwania, kontekst językowy, treść do generacji | Backend → Wikimedia i/lub OpenAI; import opcjonalnie Anthropic według konfiguracji | Tylko potrzebna treść; bez automatycznego dodawania e-maila, User.id, Google sub i sekretów do promptu/cache key. Sam tekst może zawierać dane osobowe |
| Użycie AI i diagnostyka | [LlmUsage/LlmCallPayload](../../../../../../backend/app/services/llm_usage.py), [LookupEvent](../../../../../../backend/app/services/lookup_events.py), [AppLog](../../../../../../backend/app/services/app_log.py), stdout/hosting | Zmienić wszystkie kanały, nie tylko flagę payloadów; okresy niżej |
| Wiadomość transakcyjna, odbiorca, link, status dostarczenia | Planowany Resend, skrzynka odbiorcy, lokalny szyfrowany outbox | Wyłącznie potrzebna wiadomość, limity i krótkie sekrety F-004; osobna retencja dostawcy |
| Raport treści/pomoc i odpowiedź | Nowy zapis zgłoszenia, panel operatora, monitorowana skrzynka | Świadomy podgląd danych, bez biblioteki i automatycznego LLM; T-002 |
| WWW, logowanie Google i technologie urządzenia | FastAPI/Jinja2, przeglądarka, Google po świadomym uruchomieniu, hosting | Inwentaryzacja cookies/storage/SDK; brak opcjonalnej analityki/marketingu w tym epiku |
| Backupy, eksporty techniczne i rejestr odtworzenia | Railway (PITR, kopie wolumenu, logi) i jednorazowe kopie operatora do próby restore | Inwentarz kopii/rozwidlonych usług i protokół [F-008/T-003](../../F-008-jakosc-i-operacje/tasks/T-003-backup-rejestr-i-odtwarzanie.md) |
| Dostępność usługi i alerty | Projektowany UptimeRobot: publiczny status HTTPS, e-mail operatora, bez kont testerów | Minimalny monitoring [F-008/T-004](../../F-008-jakosc-i-operacje/tasks/T-004-monitoring-koszty-i-incydenty.md), bez SDK analityki w Androidzie |

### Potwierdzone luki

- [Konfiguracja](../../../../../../backend/app/core/config.py) domyślnie włącza `llm_store_payloads` i TTL 30 dni. [Purge](../../../../../../backend/app/services/llm_usage.py) usuwa stare payloady i opróżnia candidates, ale nie usuwa całych metryk ani query/lemma/identyfikatorów.
- [LLM](../../../../../../backend/app/services/llm.py) dodatkowo wypisuje pełne prompty/odpowiedzi importu przez logger **i print**. Lokalna flaga bazy nie wyłącza stdout i logów hostingu.
- [Middleware HTTP](../../../../../../backend/app/core/app_log_middleware.py) zapisuje query params oraz wybrane pola treści lookup/karty. [Sanitizer](../../../../../../backend/app/services/app_log.py) redaguje tylko najwyższy poziom, nie jest gwarancją ochrony zagnieżdżonych danych. Nie stwierdzono tu automatycznego zapisu body haseł; obecna allowlista body dotyczy innych tras.
- Osierocenie identyfikatora przez SET NULL nie anonimizuje treści. Cache zapytania/lexical entry może być pochodną prywatnego inputu i wymaga klasyfikacji, nie deklaracji „to tylko słownik”.
- [Zależności Androida](../../../../../../android/app/build.gradle.kts) nie deklarują wprost SDK analityki/crash reporting. Ostateczny dependency graph, merged manifest, release i ruch sieciowy nadal wymagają sprawdzenia. [Interceptor](../../../../../../android/app/src/main/java/com/vocabulario/app/di/AppModule.kt) używa BASIC, co obejmuje URL; release nie może logować prywatnych parametrów.

## Kontrakt minimalizacji i retencji — projekt wykonawczy

Pierwsze trzy okresy i backupy pochodzą z decyzji właściciela. Pozostałe wartości są propozycją techniczną do wspólnego przeglądu F-003/F-004/F-006/F-008, nie dodatkowymi rzekomymi zgodami użytkownika ani gotową polityką prawną.

| Zbiór | Cel i maksymalny okres |
|---|---|
| Automatyczne kopie diagnostyczne treści | Wyłączone dla prawdziwych danych bety: payloady LLM, query/lemma/candidates w telemetrii, request/response body, stdout, logcat, traceback i eksport logów. Testy syntetyczne osobno |
| AppLog i inne własne logi techniczne | 7 dni od zdarzenia; allowlista: kod zdarzenia/błędu, szablon trasy, metoda/status, czas, losowy request ID, niezbędny pseudonim właściciela. Bez e-maila/IP/pełnego URL/query/body/tekstu wyjątku z danymi |
| LlmUsage i metryki kosztów | 30 dni od wywołania: model/dostawca, operacja, tokeny/koszt/czas/status; tylko niezbędne techniczne ID. Bez tekstu/query/lemma/POS jako śladu treści; nadal dane pseudonimowe, jeśli powiązane z osobą |
| Konto i dane nauki | Przez korzystanie z konta, do zgodnego żądania usunięcia. Bez nowej automatycznej polityki usuwania za nieaktywność. Normalne usuwanie karty/profilu wymaga spójnej obsługi synchronizacji, nie pozostawiania ukrytych kopii bez celu |
| Auth/mail | Dokładne krótkie okresy w [F-004/T-003, pkt 4](../../F-004-email-i-hasla/tasks/T-003-odpornosc-auth.md#4-techniczna-retencja-auth-i-kolejność-prac); to nie ogólne logi ani uprawnienie do retencji po purge konta |
| Odroczony logout na urządzeniu | Propozycja F-003: zaszyfrowany sekret do potwierdzenia albo najpóźniej 30 dni od lokalnego logout; potem tylko jawny stan „niepotwierdzone”, bez sekretnych danych |
| Minimalne tombstones sync | Propozycja: 30 dni od usunięcia zasobu, tylko owner/profil/typ/ID/znacznik zmiany. Przy purge konta wcześniej usuwane; stary cursor wygasa zamiast wymagać wieczystej historii |
| Minimalne ACK/deduplikacja operacji | Receipts utworzenia listy/raportu i znaczniki undo: owner, losowy ID, fingerprint i bezpieczny wynik, bez pełnego payloadu. Do końca konta lub życia zasobu zgodnie z F-003/T-003/F-007/T-002; nie usuwać wcześniej, jeśli nadal dopuszczamy bezterminowy offline retry. Osobowe/pseudonimowe, nie „anonimowa analityka”; wcześniejszy purge konta usuwa |
| Zgłoszenie treści / pomoc | Propozycja: do rozwiązania sprawy + 30 dni, kontrola otwartych spraw co tydzień; bez automatycznego resetowania terminu przez zadanie systemowe. Konto usuwane ma wcześniejszy termin F-006; wyjątek prawny tylko konkretny i udokumentowany |
| Akceptacja warunków i wieku | Minimalny dowód przy koncie, nie hash treści biblioteki ani IP/device fingerprint. Znika przy purge; inne przechowywanie tylko po odrębnej udokumentowanej ocenie prawnej |
| Receipt usuwania | Propozycja: hash/status i potrzebne daty do 30 dni od terminalnego stanu, nie adres/Google sub ani prawo do cofnięcia |
| Rejestr usunięcia/cofnięcia i marker | 45 dni od terminalnego stanu całego procesu; obejmuje backup do około 30 dni i stare dowody do 30 dni. Otwartego/niejednoznacznego procesu nie usuwać dla zwolnienia miejsca; opóźnienie alarmowane i rozstrzygane, nie „przedłużane na zawsze” |
| Minimalny rejestr zmian bezpieczeństwa | F-008/T-003: te same 45 dni od terminalnego stanu, HMAC User.id + typ/revisions/ID/czasy, bez hasła/hashu/adresu/sub. Chroni przed odzyskaniem starego hasła/adresu po restore; nie służy analizie zachowań |
| Backupy oraz ręczne kopie/eksporty bazy | Do około 30 dni od wykonania; F-008/T-003: PITR ok. 4 tygodnie, dzienne 6 dni, bez tygodniowych/miesięcznych. Każda kopia/wersja ma owner, lokalizację i deadline, także kopia lokalna oraz odmontowany wolumen |

Dla danych aktywnego systemu **wcześniejszy purge konta z F-006 wygrywa z normalnym TTL**. Minimalny rejestr/receipt i zweryfikowane wyjątki dostawców/backupów mają osobny cel i muszą być jawnie opisane. Powiadomienie przyjęcia usunięcia wysłane do dostawcy w T0 może nadal podlegać jego retencji, mimo completed w T0+14 dni; nie wysyłamy nowego maila po purge.

### Cache, brak owner i dane historyczne

1. Rozdzielić funkcjonalny cache od diagnostyki. Współdzielony słownik może zawierać wyłącznie treść rzeczywiście ogólną/publiczną z ustalonym pochodzeniem. Nie uznawać nazwiska, notatki czy promptu za anonimowe przez usunięcie FK lub regex.
2. Niepewne/prywatne zapytania i pochodne muszą mieć owner oraz usuwalną ścieżkę; propozycja krótkiego cache zapytania: do 24 h od utworzenia. Nie kopiować prywatnych notatek do wspólnego lexical cache. Trwała własna fiszka pozostaje danymi nauki.
3. Nie wyłączać hurtowo prawidłowego publicznego cache ani nie dodawać LLM do „anonimizacji”. Projekt admission/provenance musi zachować kontrakty gotowości i mierzyć hit rate/liczbę wywołań z E-002. Jeśli nie da się wykazać publicznego charakteru, nie publikować treści innym użytkownikom.
4. Wykonać manifest danych bieżących i historycznych: AppLog, LookupEvent, LlmUsage/payloads, import, jobs, raporty i cache. Rekordy bez wiarygodnego owner nie są przypisywane po e-mailu ani deklarowane jako nieosobowe. Zaproponować ograniczone usunięcie starej diagnostyki/niepewnych pochodnych po osobnym zatwierdzeniu operacji, nie teraz.
5. Cleanup TTL nie może kasować pracy offline, idempotency/undo potrzebnego do przyjęcia spóźnionej operacji ani zerować dziennego limitu importu. Minimalne tombstones to inny zbiór niż pełna usunięta karta; uporządkowanie fizycznego soft-delete i pochodnych należy do manifestu F-006/F-003.

### Reguła admission i migracji cache

Wprowadzić jawne `visibility=owner|public`, `owner_id` dla prywatnego wpisu, `created_at/expires_at`, `provenance_kind/source_ref` oraz wersję promptu/modelu; modelować na istniejących tabelach cache, bez drugiego równoległego cache. Domyślna wartość nowego/historicznie nieudowodnionego wpisu **nie jest public**.

Public dopuszczony tylko, gdy jest dokumentowalny ogólny materiał: istniejący zweryfikowany publiczny wpis lub canonical headword/treść ze sprawdzonego publicznego źródła z metadanymi licencji. Pochodna AI może dziedziczyć public tylko, gdy jej jedynym inputem treściowym jest taki ogólny materiał, bez dodatkowego prywatnego kontekstu/note/import/raw query. Sama długość/jeden wyraz, regex PII lub brak User.id w prompt nie dowodzą publiczności.

Decyzję podejmować na podstawie już dostępnego provenance, **bez nowego LLM/dodatkowego odpytywania słownika tylko dla klasyfikacji**. Brak dowodu → owner-scoped cache do 24 h, nigdy read innego owner. Public `lexical_entries` i `content_is_complete` nadal dopiero po pełnym enrichment; wczesny słownikowy dowód nie zmienia `ready/learnable`.

Odczyt: najpierw dozwolony prawidłowy public/own cache zgodnie z obecnym kluczem i wersjami, nigdy prywatny rekord A jako fallback dla B. Przy coalescing/in-flight klucz również uwzględnia zakres właściciela, nie tylko hash słowa. Rzeczywiście publiczne in-flight pozostaje współdzielone.

Migracja addytywna: nowe pola → odczyt respektujący scope → kontrolowana klasyfikacja istniejących rekordów według znanego pochodzenia → dopiero ograniczenia NOT NULL/check/index. Nieznane osierocone dane trafiają do niedostępnej kwarantanny i osobno zatwierdzonego cleanup, nie do konta aktualnie zalogowanego. Zachować udowodnione publiczne trafienia. Próba porównuje izolację A/B i hit rate/liczbę LLM na stałym zbiorze syntetycznym; koszt ewentualnej utraty **nieuprawnionego** współdzielenia musi być ujawniony w kosztorysie, nie ukrywany przywróceniem wycieku.

### Wykonanie i obserwowalność

- Jedna polityka allowlisty pól w kontrolowanych wejściach do logów; redakcja rekurencyjna jako dodatkowa ochrona, nie zgoda na logowanie dowolnego body. Obejmuje wyjątki, błędy walidacji, middleware, logi bibliotek/serwera, panel i pobranie diagnostyki.
- Wyłączyć zbieranie przed zaproszeniem testerów. Historyczne raw dane mają osobną kontrolowaną procedurę czyszczenia; samo ustawienie flagi niczego nie usuwa. Nie udostępniać ich panelowi po zmianie polityki.
- Cleanup co 15 min w backendzie, paczki po 1000 najstarszych rekordów z indeksem terminu, współbieżny claim/SKIP LOCKED, bez skanów N+1. Sekretne auth mają ciaśniejsze paczki F-004. Pojemność musi wystarczyć do dotrzymania maksymalnych okresów; backlog/błąd jest alarmem i jawnym zadaniem operatora, nie sukcesem `0 usunięto`.
- Retencja nie opiera się wyłącznie na ruchu do endpointu. Test kontrolowanego zegara i restartu potwierdza sprzątanie także przy braku wywołań AI. Prywatna sesja loggera respektuje lifecycle F-006, aby nie odtworzyć skasowanych danych.
- Jeśli kopie zawierają dane sprzed usunięcia, przechowujemy je izolowane do ich terminu, bez zwykłego przeglądania/reimportu. Restore blokuje ruch do uzgodnienia dziennika konta z logami; także brak dostępu do starych logów/payloadów i nowe `db_epoch`. Ręczne kopie i stare wolumeny nie mogą ominąć limitu.

## Dostawcy, role i wyjątki — do potwierdzenia przed użyciem

| Dostawca | Potwierdzony fakt publiczny / ograniczenie |
|---|---|
| OpenAI API | Kod używa Chat Completions, nie Responses. Dane API domyślnie nie służą do treningu bez opt-in. Standardowe abuse logs mogą zawierać treść do 30 dni, z wyjątkami bezpieczeństwa/prawnymi. Jawne `store=false` nie wyłącza tego ani całej retencji cache |
| OpenAI prompt cache | [Helper](../../../../../../backend/app/ai/prompt_cache.py) podaje `ttl=30m`, ale obecna dokumentacja modeli wskazuje, że TTL cache może być minimum, a stan może przetrwać do 24 h. Nie publikować obietnicy „OpenAI usuwa po 30 minutach” ani ZDR bez potwierdzenia |
| Anthropic API — jeśli wybrany | W kodzie opcjonalny import; biblioteka nie jest jawną zależnością bazową pyproject. Standardowo do 30 dni, lecz oznaczone naruszenia mogą mieć dłuższą retencję (treść do 2 lat, klasyfikacja do 7 lat); wyjątki modelowe/umowne. Sprawdzić faktycznie wybrany model/produkt, nie przenosić zasad konsumenckiego czatu na API |
| Resend Free — planowany | Treść wiadomości/logi przechowywane w USA 30 dni, backupy 7 dni. Region wysyłki EU nie przenosi storage do UE. Brak API usuwania pojedynczego maila; wcześniejsze usunięcie wysłanego wymaga kontaktu z supportem dostawcy. Nie obiecywać automatycznego skasowania każdego maila w 14 dni |
| Resend podprocesorzy | Zwykła wysyłka API nie uruchamia funkcji AI edytora/supportu, ale dokumentacja opisuje antyspamowe próbkowanie przez TypeSafe z ZDR. Objąć rzeczywistą listę podprocesorów przeglądem; nie twierdzić, że poczta nie ma żadnych takich odbiorców |
| Railway | Region serwisu/wolumenu wybieralny; przetwarzanie własne platformy także USA. Logi zależą od planu (np. Hobby 7 dni, Pro 30 dni), nie od TTL naszej tabeli. F-008 ustala faktyczny plan, ograniczenie retencji i koszt bez nowego zewnętrznego log drain |
| Railway backup (PITR/kopie wolumenu) | Bucket PITR i kopie wolumenu w tym samym projekcie Railway (decyzja 18.11.2026, bez AWS). Okna retencji ustala platforma: PITR ok. 4 tygodnie, dzienne 6 dni; ślad `account_journal` w logach podlega retencji logów planu |
| UptimeRobot / planowany | Tylko publiczny endpoint/stan i kontakt operatora, bez danych kont/nauki. Sprawdzić warunki, lokalizację i retencję kontaktu; brak Android SDK i zgody na płatny plan |
| Google | Logowanie/obsługa dowodu przez Google, odrębne od danych nauki. Ustalić rzeczywistą rolę i zakres claimów; nie nazywać automatycznie każdego produktu Google naszym procesorem |
| Wikimedia | [Lookup](../../../../../../backend/app/services/dictionary_lookup.py) wysyła zapytanie z backendu; dostawca widzi tekst i połączenie backendu, nie dostaje automatycznie konta użytkownika. Zweryfikować politykę/rolę i licencję pobieranej treści; bez domyślnej obietnicy DPA i własnego TTL dostawcy |
| Skrzynka pomocy | Wybór przy domenie/kontakcie, osobny od Resend API. Sprawdzić dostawcę, retencję wiadomości/kosza/backupów, dostęp i transfery przed uruchomieniem |

Lista zawiera warianty kodu i planu, nie potwierdzenie konfiguracji produkcji. **Allowlista projektu:** OpenAI Chat Completions na zatwierdzonych w konfiguracji modelach/cenniku, Wikimedia dla obecnego słownika, Google Sign in/Credential Manager, Resend wyłącznie maile transakcyjne, Railway API/WWW/PostgreSQL/backup oraz powyższy monitoring po jego osobnym zatwierdzeniu. Bez Responses/Files/edytora AI poczty/SDK analytics. Anthropic w becie domyślnie wyłączony, dopuszczalny tylko po osobnym potwierdzeniu modelu/retencji/umowy i jawnym włączeniu, bez automatycznego fallbacku.

Przed użyciem właściciel z właściwym przeglądem potwierdza faktyczny model/produkt, konto/umowy/region i podstawę prawną; runtime akceptuje tylko jawny model/cennik z F-008/T-004, nie dowolny URL dostawcy. Nie wpisujemy do publicznego taska tajnych wartości kont. Zmiana odbiorcy/celu wymaga aktualizacji informacji i oceny potrzeby nowej zgody, nie tylko podmiany klucza.

Właściciel z odpowiednim przeglądem prawnym zatwierdza podstawy dla konkretnych celów: wykonanie usługi, bezpieczeństwo i obsługa praw mają różne przesłanki. DPA/SCC/DPF nie są jedną wymienną etykietą ani certyfikatem zgodności aplikacji. Nie tworzyć ogólnego wyjątku „możemy zachować wszystko dowolnie długo”; wymagany wyjątek ma zakres, podstawę, termin/przegląd i ograniczony dostęp.

## Informowanie, prawa i deklaracje Play

- Przed przekazaniem tekstu do AI: czytelna informacja, jakie treści i do kogo trafiają, także możliwe transfery/retencja. Nie dodawać e-maila/hasła do promptu. Użytkownik może anulować generację; anulowanie nie odsyła automatycznie danych innemu modelowi.
- Ustalić dla faktycznych przepływów potrzebę wyróżnionej informacji i zgody według Play/GDPR. Gdy zgoda jest konieczna, osobny nieprezaznaczony wybór przed wysyłką; odmowa nie kasuje konta/pracy i nie blokuje niezależnej nauki już pobranych fiszek. Akceptacja regulaminu nie zastępuje takiej zgody.
- Publiczna informacja wskazuje administratora/kontakt, cele/podstawy, odbiorców/transfery, okresy/warunki, prawa i drogę skargi; spójna z rzeczywistym 7+7, kopią do około 30 dni i wyjątkami procesorów.
- Dostęp/sprostowanie/usunięcie/ograniczenie/sprzeciw/przenoszenie według właściwych przesłanek mają obsługę przez monitorowane wsparcie. To nie wymaga nowego eksportu self-service w aplikacji: operator ma bezpieczny, kontrolowany tryb realizacji. Zweryfikować tożsamość bez domyślnego żądania skanu dokumentu.
- Cel pierwszej odpowiedzi supportu 2 dni robocze nie zmienia terminów ustawowych. Art. 12 GDPR: co do zasady działanie/informacja w miesiąc, wyjątkowe przedłużenie według prawa z powiadomieniem w pierwszym miesiącu; to nie domyślna licencja na opóźnienie purge 7+7.
- Przygotować macierz Data safety: rzeczywisty typ danych, cel, required/optional, odbiorca, definicja collection/sharing/ephemeral i usuwanie. Kandydaci obejmują e-mail/User ID, historię wyszukiwania/aktywność, własne treści i diagnostykę. Nie zaznaczać mechanicznie „brak zbierania” po wyłączeniu payloadów ani „brak sharing”, bo dostawca ma DPA.
- F-002 porównuje formularz z finalnym AAB/SDK/backendem i politykami w dniu publikacji; Google login, przeglądarka i metadane hostingu także mają rzeczywiste przepływy. Rejestracja i ustawienia prowadzą do publicznej wersji PL/EN/ES, nie do dokumentu w GitHub.

## Źródła publiczne sprawdzone 17.11.2026

- [OpenAI: Data controls](https://developers.openai.com/api/docs/guides/your-data).
- [Anthropic: retencja organizacji/API](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data).
- [Resend: GDPR, transfery, podprocesorzy i retencja](https://resend.com/security/gdpr).
- [Railway: backupy](https://docs.railway.com/volumes/backups), [bezpieczeństwo/regiony/logi](https://docs.railway.com/enterprise/security).
- [Google Play: User Data](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en), [prominent disclosure](https://support.google.com/googleplay/android-developer/answer/11150561?hl=en).
- [GDPR, tekst skonsolidowany, w szczególności art. 5, 6, 12–22, 28 i 44+](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02016R0679-20160504).

Dokumentacja dostawcy może się zmienić; przy wyborze konta/modelu i przed publikacją zachować datę oraz dowód właściwych warunków poza publicznym repo, bez sekretów/danych testerów.

## Kryteria i weryfikacja

- [ ] Publiczne adresy działają bez loginu; treść opisuje konto, naukę, importy, wyszukiwania, zgłoszenia, logi/AI i prawa.
- [ ] Retencja odpowiada zweryfikowanej konfiguracji, a nie samemu domyślnemu TTL.
- [ ] Data safety i pozostałe deklaracje zgadzają się z faktycznym zachowaniem i definicjami Play; internal/closed rozróżnione.
- [ ] Usuwanie i zgłaszanie treści mają rzeczywiste ścieżki; nie deklarujemy „nie zbieramy danych”.
- [ ] Wymagania ponownie sprawdzone w dniu zgłoszenia, odpowiedzialność za treść prawną ustalona.
- [ ] Mapa danych, podstaw, dostawców/transferów i retencji ma zatwierdzone wartości; obowiązkowe wymagania mają przypisane taski realizujące zachowanie, nie tylko tekst polityki.
- [ ] Syntetyczne znaczniki sekretu/tekstu nie trafiają do DB logów, stdout, hostingu, logcat, panelu ani pliku diagnostycznego, również przy błędzie i zagnieżdżonym JSON.
- [ ] Zegar/restart/brak ruchu sprawdzają logi 7 dni, metryki 30 dni i krótkie auth; wcześniejszy purge usuwa własne dane, nie dane konta B ani publiczny słownik.
- [ ] Backup do około 30 dni, brak niezinwentaryzowanego eksportu i skuteczny restore bez wskrzeszenia danych; możliwości/wyjątki procesorów opisane uczciwie.

**Bramki wykonania:** wdrożony manifest/cache/cleanup według powyższego projektu; owner zatwierdza podstawy/wyjątki i faktyczne konta/produkty/DPA przed ich użyciem. Projekt mechanizmu kopii/retencji wersji i rejestru jest w F-008/T-003, koszty/monitoring w F-008/T-004; nie pozostaje ogólne „F-008 dopiero wymyśli restore”. Wyniki runtime/publikacja są późniejszą akceptacją, nie wykonane teraz.

**Poza zakresem:** automatyczna gwarancja zgodności prawnej, zbędne zgody marketingowe. **Wynik weryfikacji:** kod/publiczne źródła i decyzje produktu sprawdzone, projekt zapisany; bez implementacji, operacji na danych i zatwierdzonej polityki prawnej.
