# T-002 · Usuwanie konta i danych

**ID:** `E-001/F-006/T-002` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Zarządzanie kontem](../README.md). **Źródło:** B-08; F-09 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel i zatwierdzone zachowanie

Samoobsługowe usuwanie całego konta z Androida i WWW, z dowodem właściciela i rzeczywistym zatrzymaniem pracy. Decyzje z 17.11.2026:

- Po przyjęciu żądania natychmiast blokujemy zwykły dostęp i odwołujemy sesje, lecz przez **7 × 24 godziny** można wycofać usunięcie.
- Dopiero po tym okresie rozpoczyna się nieodwracalna realizacja; dane aktywnego systemu usuwamy w kolejnych **maksymalnie 7 × 24 godzinach**, czyli najpóźniej **14 dni od przyjęcia**. To nie obietnica wymazania wszystkich backupów i danych dostawców w tym samym czasie — wyjątki i terminy zatwierdza F-007.
- WWW działa bez instalowania aplikacji: obecne hasło, podłączone Google albo link na wcześniej zweryfikowany bieżący adres aplikacji. Pomoc awaryjnie, nigdy kasowanie na podstawie samego podanego e-maila.
- Po zakończeniu można utworzyć nowe, puste konto tym samym e-mailem/Google, z nowym User.id; nie ma przywrócenia starego postępu ani przypisywania starych kolejek.

**Start:** [E-001/F-001/T-001](../../F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md), [E-001/F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md). **Integracja mobilna:** [E-001/F-003/T-002](../../F-003-sesja-i-offline/tasks/T-002-sesja-androida.md). Publiczna ścieżka i retencja uzgodnione z E-001/F-007/T-001.

## Stan kodu i miejsca integracji

- [auth.py](../../../../../../backend/app/api/v1/auth.py) nie ma procesu usuwania ani lifecycle konta; usunięcia nie naprawi sam ekran.
- [Modele](../../../../../../backend/app/models/__init__.py): profile, karty/SRS, review, listy, korekty, historia, importy i urządzenia mają część powiązań CASCADE. `AppLog`, `LookupEvent` i `LlmUsage` mają ID użytkownika bez FK; `LlmCallPayload` zawiera surowy request/response. Te dane nie znikną od samego `DELETE users`.
- `LexicalEntry.created_by_user_id` to SET NULL, a cache wyszukiwań nie ma właściciela. Współdzielony słownik nie jest tym samym co prywatna historia lub dowolny tekst użytkownika.
- [card_jobs](../../../../../../backend/app/services/card_jobs.py) zapisuje po długich wywołaniach AI i wewnętrznych commit; [import_jobs](../../../../../../backend/app/services/import_jobs.py) tworzy karty z zapamiętanego joba. Potrzebna bariera zapisu, a nie samo anulowanie taska w jednym procesie.

Poniższy projekt nie jest dowodem wdrożenia. Źródło wymagań sklepu: [Google Play account deletion](https://support.google.com/googleplay/android-developer/answer/13327111?hl=en) — wymagane ścieżki w aplikacji i poza nią, objęcie danych oraz jasne wyjątki; ponownie sprawdzić przed publikacją.

## 1. Stan, terminy i model

`User.account_status`: `active`, `deletion_pending`, `deleting`; domyślnie active. `User.lifecycle_revision BIGINT NOT NULL DEFAULT 1` wzrasta przy przyjęciu, cofnięciu i rozpoczęciu purge. Nie zmieniamy ID konta ani adresu/metod w okresie odstąpienia.

Nowa trwała tabela `account_deletions`:

| Pole | Kontrakt |
|---|---|
| `id` | UUIDv4 request ID wygenerowany przed potwierdzeniem przez klienta; PK |
| `user_id` | Nullable UUID FK SET NULL po fizycznym usunięciu; indeks |
| `subject_hmac`, `subject_key_version` | HMAC stabilnego User.id i dodatnia wersja klucza, bez e-maila/Google sub; pseudonimowy znacznik, **nie anonimowe dane** |
| `state` | `grace`, `purging`, `completed`, `cancelled`; błąd wykonania to osobny kod/next_attempt, nie „completed” |
| `requested_at`, `cancel_until`, `purge_due_at` | UTC z zegara serwera: T0, T0+7 dni, T0+14 dni; klient nie ustala terminów |
| `status_secret_hash`, `request_fingerprint` | SHA-256 losowego sekretu statusu i znormalizowanej intencji/wersji potwierdzenia; bez surowych sekretów |
| `cancel_request_id`, `cancel_fingerprint`, `cancelled_at` | Nullable pola bezpiecznego ponowienia cofnięcia |
| `purge_started_at`, `completed_at` | Nullable UTC; ukończenie dopiero po weryfikacji zakresu |
| `stage`, `attempts`, `next_attempt_at`, `lease_until`, `lease_token`, `last_error_code` | Zamknięte etapy/kody, UUID właściciela lease, trwałe wznowienie bez surowego traceback/payloadu |

Częściowy unique jednego aktywnego procesu (`grace`/`purging`) na `user_id`. Nowe żądanie nie zastępuje poprzedniego i nie przesuwa dat; powtórne kliknięcie nie rozpoczyna kolejnych 7 dni. Po skutecznym cofnięciu można rozpocząć nowy proces ze świeżym dowodem i nowym ID.

Odstąpienie dozwolone wyłącznie gdy serwer pod blokadą potwierdza `state=grace AND now < cancel_until`. Czas pobieramy po uzyskaniu blokady (`clock_timestamp()` lub bieżący UTC serwera), nie ze starego PostgreSQL `now()` początku transakcji czekającej na lock. Na granicy lub później 409 `deletion_irreversible`, także jeśli worker jeszcze nie rozpoczął kasowania. „7 dni” oznacza 168 godzin, nie lokalną północ, bez zależności od DST.

W okresie grace dane i ustawienia pozostają nienaruszone; nie zwalniamy e-maila/Google do rejestracji, nie anonimizujemy jeszcze prywatnych danych i nie wykonujemy destrukcyjnego cancel importu.

## 2. Dowód właściciela bez zwykłego loginu WWW

Wspólne dla Androida i strony **dedykowane dowody operacji**, nie nowe access/refresh i nie portal do biblioteki. Reuse walidatora haseł F-004, Google/nonce F-005, rate limit i `account_action_tokens` F-004. Nie wywoływać zwykłego `/auth/google` do cofania — mogłoby utworzyć nowe konto.

Rozszerzenie tokenów akcji o purpose `request_account_deletion`, `cancel_account_deletion`, `proof_method` (`password`, `google`, `email`), `lifecycle_revision` oraz nullable `target_deletion_id` wymagany przy cofnięciu. Hash losowych 32 bajtów, rewizje adresu/poświadczeń jak w F-004. Dowód hasła/Google TTL **5 minut**, dowód e-mail **30 minut**, jednorazowe zużycie przy mutacji; token nie daje nauki/sync ani zmiany innych danych.

- Hasło: istniejące hasło tego konta, także gdy adres niezweryfikowany. Loginowe zasady 1–128 znaków, bez trim; ten sam ograniczony hasher i synthetic hash dla nieistniejącego/Google-only. Neutralny 401 `invalid_credentials`.
- Google: świeży dedykowany challenge z serwerowym nonce i `purpose=account_deletion`, action request/cancel. Wspólny bezpieczny walidator; `sub` musi być już powiązane z istniejącym User.id. Nigdy automatyczne zakładanie/łączenie po e-mailu, także gdy adres Google różni się od aplikacji.
- E-mail: tylko bieżący **już zweryfikowany** adres aplikacji, przy zgodnej rewizji. Nie wysyłać linku na pomylony niezweryfikowany adres lub sam snapshot Google. Żądanie i odpowiedź publiczna neutralne; inne metody/pomoc nadal dostępne.
- Nie wymagać najpierw weryfikacji skrzynki do usunięcia konta, gdy użytkownik poprawnie dowiódł własności hasłem/Google. Dowód operacji nie potwierdza przy okazji innej skrzynki i nie nadaje pełnych uprawnień.
- Cofnięcie wiąże dowód z konkretnym aktualnym deletion ID i lifecycle revision; stary link/proof nie cofa nowego procesu. Zmiana rewizji lub zużycie unieważnia dowód.

TTL dowodu cofnięcia i termin wysyłki linku są dodatkowo ograniczone przez `cancel_until`; nie wysyłamy już bezużytecznego linku po granicy. Android porównuje udowodnione `user_id` z właścicielem obecnego kontekstu przed finałowym request; wybór Google B przy koncie A nie zmienia celu ani danych A.

Google na stronie: dedykowany Sign in with Google z nonce, tylko jednorazowy ID token; Web client ID/authorized origins z F-005. Bez żądania offline access, Google refresh i dostępu do Gmail. Kod Google ładowany dla świadomie wybranej metody, ograniczone CSP; inwentaryzacja SDK/cookies F-007 nadal wymagana. Hasła, ID token i action token tylko w pamięci, nie w logach, URL query, localStorage lub analityce.

## 3. API i odzyskanie wyniku

Prefiks `/api/v1`; wspólny `api_error`. Dedykowany publiczny router nie oznacza braku proof, limitów ani kontroli lifecycle.

| Endpoint | Body / sukces |
|---|---|
| `POST /account-deletion/proof/password` | `{email,password,action}` →200: action token, expiry, udowodnione `user_id` i podstawowy stan własnego procesu |
| `POST /account-deletion/google/challenge` | `{action}` →200 challenge ID, nonce, expiry; action tylko request/cancel |
| `POST /account-deletion/proof/google` | `{action,challenge_id,id_token}` →200 taki sam dowód operacji; challenge zużyty atomowo |
| `POST /account-deletion/email/request` | `{email,action}` →neutralne 202 i resend available po 60 s; rzeczywisty link tylko dla kwalifikującego się konta |
| `POST /account-deletion/request` | `{request_id,action_token,status_secret,confirmation_version:"delete-account-v1"}` →202 z deletion ID, state, T0, cancel_until, purge_due_at |
| `POST /account-deletion/status` | Albo `{request_id,status_secret}`, albo `{action_token}` celu cancel; →200 ID/stan/terminy/can_cancel, bez e-maila/profili/treści |
| `POST /account-deletion/cancel` | `{deletion_id,request_id,action_token}` →200 cancelled, requires_login=true; bez TokenResponse |

`action` na wejściu to `request` lub `cancel`, mapowane serwerowo na konkretny purpose. Przy poprawnym dowodzie credentials i braku procesu do cofnięcia: jawne `no_pending_deletion`, bez utworzenia nowego i bez ogólnej sesji.

Sekret statusu: 32 losowe bajty generowane przez SecureRandom/Web Crypto; czyta wyłącznie status i **nie** pozwala cofnąć/usunąć konta. Android zapisuje request ID + sekret w Keystore chronionym magazynie przed HTTP. WWW może przechować wyłącznie ten ograniczony receipt w sessionStorage bieżącej karty do zakończenia procesu/wyjścia; nie hasło, action token ani token Google. Utrata karty/receiptu: świeży dowód hasła/Google lub link na zweryfikowaną skrzynkę pozwala ustalić własny proces i go cofnąć przed terminem.

Action token/receipt/nonce mają kanoniczne base64url bez paddingu z dokładnie 32 bajtów (43 znaki); odrzucać zły format/długość, nie hashować dowolnie dużego pola. ID walidowane jako UUID, confirmation_version jako zamknięta wartość, payload Google według limitów wspólnego walidatora.

Idempotencja request: ponowienie tego samego ID, sekretu i intencji zwraca aktualny proces bez nowej konsumpcji proof, przesuwania czasu i ponownego maila, także po revoke sesji. Inne body/sekret pod tym samym ID →409 `operation_id_conflict`. Inny ID przy trwającym procesie nie tworzy drugiego; uwierzytelniony właściciel otrzymuje istniejący stan, nie reset odliczania.

Po timeout/restart najpierw status z zachowanego receiptu, bez automatycznego tworzenia nowego żądania. 404 statusu ze złym/nieznanym receiptem jest neutralne; może oznaczać, że pierwszy request nadal nie zakończył commit. Nie ogłaszać „anulowano” ani pozwalać dalej uczyć się tylko na tej podstawie. Nowa próba używa tego samego request ID/sekretu i świeżego proof, jeśli poprzedni nie jest dostępny; nie odtwarzać hasła/Google token z dysku.

Idempotencja cancel: zgodny cancel request ID/fingerprint zwraca cancelled bez skutków ponownie; inne wejście →409. Po utracie odpowiedzi receipt/status potwierdza cancelled, ale nie loguje. Złe/wygasłe proof →403 `account_action_required` lub 410 `account_action_expired`; zły stan →409 `deletion_not_pending`/`deletion_irreversible`; 422 walidacja bez sekretów w `input`; 429 retry; 5xx nie udaje przyjęcia.

## 4. Transakcja, blokada i cofnięcie

Kolejność wspólna z F-003: User → sesje/retry → recent-proof/challenge, jeśli użyte → zmiana adresu → deletion process → tokeny akcji → buckety mailowe → outbox. Nie blokować joba i potem czekać na User; claim worker kończy transakcję lease przed tą kolejnością.

Przyjęcie w jednej transakcji:

1. Po wstępnej kryptografii ponownie sprawdzić właściciela, aktywność, rewizje i TTL pod blokadą User. Dokładne retry rozpoznać przed ponownym zużyciem dowodu.
2. Utworzyć `grace` z terminami, zużyć proof, ustawić User deletion_pending i podnieść lifecycle_revision.
3. Odwołać wszystkie sesje i retry, unieważnić pozostałe proof/challenge/linki weryfikacji/resetu/zmiany adresu. Pending email change zakończyć jako unieważniony, nie zmienić adresu.
4. Wstrzymać nowe prace i oznaczyć lifecycle w istniejących zadaniach; żaden destrukcyjny rollback importowanych kart podczas grace.
5. Zapisać minimalne zdarzenie procesu i ewentualne zawiadomienie na **zweryfikowany** adres w istniejącym outbox. Mail nie warunkuje skuteczności blokady i nie zmienia dat. Bez wiadomości na potencjalnie cudzy niepotwierdzony adres.

Nowa autoryzacja/login/refresh/Google nie daje zwykłego dostępu kontu pending/deleting. Hasło/Google sprawdzane poprawnie mogą skierować do ograniczonego procesu cofnięcia; nie wydają app sesji. Nieudana próba pozostaje neutralna jak dotąd.

Wspólne kody lifecycle: 403 `account_deletion_pending` wyłącznie po wiarygodnym dowodzie tożsamości, bez tokenów zwykłej sesji; 401 `account_deleted` tylko przy poprawnym starym dowodzie i markerze usunięcia. Brak dowodu/markera pozostaje zwykłym odrzuceniem auth, nie poleceniem czyszczenia danych. Daty/can_cancel pochodzą z ograniczonego endpointu statusu, nie z dowolnej publicznej próby sprawdzenia adresu.

Anulowanie przed granicą: sprawdzenie świeżego proof i joba, state cancelled, User active, lifecycle_revision++; unieważnienie dowodów procesu i trwałe zdarzenie w jednej transakcji. **Nie odwołujemy usunięcia przez samo zalogowanie ani odczyt linka. Nie wskrzeszamy starych sesji.** Nowy zwykły login przywraca ten sam ID, profile/postęp i niewysłaną pracę, która nadal jest na telefonie.

Nie przywracamy unieważnionego pending email-change i starych linków resetu; można rozpocząć nowe. Prace istniejące przed grace wznawia istniejący scheduler po sprawdzeniu lifecycle, z tym samym job ID i zapisanymi etapami, bez dublowania już utworzonych kart i zbędnych LLM. Nowe karty powstałe po wznowieniu nadal podlegają 25/profil/bieżący dzień UTC, według czasu utworzenia karty jak dziś; nie zwalniamy limitu przez pauzę. Importu anulowanego niezależną świadomą decyzją użytkownika nie wznawiamy.

Po granicy worker pod tą samą blokadą przechodzi grace → purging i User deleting. Cancel kontra purge ma jeden wynik; brak stanu „cancelled, lecz część danych usunięta”. Grace nie przechodzi w completed tylko dlatego, że upłynął zegar.

## 5. Zatrzymanie zadań i urządzenia

Każda operacja zapisująca dane właściciela przechwytuje lifecycle_revision; przed **każdym commit** po HTTP/LLM sprawdza aktualny User active i tę samą rewizję pod blokadą User. Dotyczy API autoryzowanego wcześniej, importu, etapowych callbacków enrichment, word-family/shared cache i osobnych loggerów zapisujących prywatny payload. Sam sprawdzony na początku JWT/istnienie FK nie wystarcza.

Blokada User poprzedza także pierwszy flush zapisów właścicielskich: bez `autoflush` brudnego snapshotu przed sprawdzeniem i bez polegania na starym obiekcie z identity map. Nie trzymać blokad/dirty ORM przez LLM; odczytany input jest snapshotem, po sieci nowa krótka transakcja ponownie ładuje User/kartę i sprawdza rewizję. Jedno sprawdzenie na transakcję/batch, nie dodatkowy SELECT na każdą kartę. Brak aktywnego User powoduje jawny paused/superseded i rollback, nie zapis osieroconego payloadu.

Wywołania sieciowe poza blokadami DB. Żądania AI już wysłanego nie da się cofnąć; po powrocie nie zapisujemy prywatnego wyniku/logu i nie tworzymy kolejnego LLM. Wynik starego lifecycle nie stosuje się także po późniejszym cofnięciu i reaktywacji; wznowienie uruchamia poprawny obecny kontekst.

Podczas grace:

- Android przechodzi do `DeletionPending`, chowa bibliotekę i **zachowuje Room/outbox**, blokuje nowe oceny i sync. Receipt i stan procesu przechowuje przy tym samym owner+generation; nie usuwa pracy na samym 202.
- Sync/lookup/import/enrichment/powiadomienia i receivery po reboot respektują blokadę. Proces serwerowy jest **wstrzymany**, nie destrukcyjnie anulowany. Nie wprowadzamy nowego pollingu; status przy wejściu do procesu i ręcznym odświeżeniu.
- Inny telefon offline nie pozna stanu natychmiast; nie obiecujemy zdalnego wymazania. Przy następnym kontakcie otrzymuje `account_deletion_pending` i zamraża ten sam owner/cache; nie wysyła kolejki przez innego użytkownika.

Watchdog/claim importu i resume enrichment filtrują konta nieaktywne już przed enqueue; grace nie nabija retry/failed ani nie uruchamia wciąż tych samych zadań. Nie używać istniejącego destrukcyjnego `finalize_cancel` do pauzy konta.

Po potwierdzonym nieodwracalnym etapie można czyścić lokalne dane tego właściciela na mocy ostatecznej zgody na usunięcie całego konta. Nigdy na samym generic 401/braku sieci/braku User. Przed odpowiedzią `account_deleted` serwer sprawdza poprawny podpis starego dowodu tożsamości i marker usunięcia dla jego ID; nie czyści danych B na podstawie tokena A. Przy zbyt starym dowodzie/braku zachowanego markera pozostaje recovery i jawna decyzja, bez zgadywania ani przypisania cache nowemu ID.

## 6. Zakres danych i wykonanie purge

Wykonawczy manifest tabel/plików jest testowany, nie oparty tylko na nazwach FK:

| Obszar | Działanie nieodwracalnej fazy |
|---|---|
| Konto, profile, ustawienia, metody, urządzenia | Usunąć wraz z sesjami, retry, proof/challenge, action tokenami i procesami zmiany adresu |
| Karty/listy/SRS/review/moves/undo | Usunąć także prywatne tombstones i deduplikację; inne konto pozostaje nietknięte |
| Importy i historia/korekty/eskalacje | Usunąć job/items/events, raw_note, input_meta, logi etapów i prywatne powiązania |
| LookupEvent, AppLog, LlmUsage, LlmCallPayload | Jawne czyszczenie po owner, profile, card/job/operation/request IDs i powiązaniach; surowe payloady i wolny tekst nie zostają tylko po ustawieniu user_id=NULL |
| Mail | Anulować/usunąć prywatne payloady i tokeny/outbox tego konta, w tym niewysłane linki; spóźniony worker nie wysyła starej wiadomości |
| Wspólny słownik/rodziny/cache | Zachować wyłącznie rzeczywiście nieosobowe ogólne treści; usunąć atrybucję użytkownika i prywatne pochodne. Sam SET NULL nie dowodzi anonimizacji |
| Statystyka kosztów | Dopuszczalny tylko zatwierdzony nieidentyfikowalny agregat bez query/lemma/request/response/user/card/profile/operation IDs; inaczej usunąć rekord |
| Nowe minimalne dane | Usunąć list/report receipts, undo, profile sync state i proof wieku/warunków wraz z User; nie mylić z odrębnym 30/45-dniowym receipt/journal procesu usuwania. Publisher terminalnego zdarzenia nie może zniknąć przez CASCADE User |

Przed usunięciem powiązań zebrać zakres referencji do wyczyszczenia; bez logowania ich list do publicznych logów. Osierocone historyczne payloady bez wiarygodnego pochodzenia wymagają klasyfikacji/oczyszczenia w F-007 przed deklaracją pełnej skuteczności. Nie kasować całego słownika ani danych innych kont jako skrótu. Usunięcie wpisu będącego jedynie cache nie może usuwać karty należącej do B.

Worker w istniejącym procesie backendu/maintenance: kontrola co 15 minut, najwyżej 10 należnych procesów na przebieg, lease 60 s odnawiane przy kolejnych krótkich batchach. Najwyżej 1000 wierszy tabeli/transakcję; trwały etap i bezpieczne ponowienie, bez oczekiwania sieciowego pod User/job lock. Kolejność usuwa liście i duże dane przed finalnym User; CASCADE jest zabezpieczeniem, nie całym planem.

Każda zmiana etapu sprawdza aktualny `lease_token` i stan pod blokadą, także po przejęciu zadania przez inną replikę. Finalne usunięcie User i ustawienie completed są jednym commit, po zakończeniu czyszczenia i sprawdzeń; nie zwalniamy e-maila/Google w oknie „User usunięty, ale konto jeszcze purging”.

Błąd pozostawia purging i last_error_code, kolejne podejście z backoff 15 min →30 min →1 h →maks. 6 h; brak „po N próbach uznaj done”. Alert po pierwszej porażce, ponowny przy <24 h do purge_due_at i po przekroczeniu; operator ma stan/ID procesu bez surowych danych. SLA 14 dni wymaga rzeczywistej obsługi alertów w F-008, nie samego wpisu w regulaminie.

`completed` dopiero po sprawdzeniu zerowej liczby prywatnych rekordów manifestu/nieuprawnionych referencji i zamknięciu User. Minimalny dowód wykonania/marker i zatwierdzone wyjątki retencji są jawnie odrębne; nie nazywamy ich anonimowymi tylko dlatego, że używają HMAC.

## 7. Dostawcy, backup i bezpieczeństwo odtworzenia

F-007 musi wskazać konkretne okresy/wyjątki dla maila, hostingu, AI, telemetryki i backupów. Wysyłamy realnie dostępne żądania usunięcia do procesorów lub dokumentujemy ich wiążący cykl retencji; nie zakładamy nieistniejącego API ani że usunięcie pojedynczej odpowiedzi AI usuwa wszystkie logi dostawcy. Brak weryfikacji blokuje publiczną obietnicę, nie jest ukrytym „done”.

Minimalny rejestr usunięć i cofnięć (subject HMAC User.id, process ID, daty i stan; bez adresu, Google sub, treści) jest **niezależny od przywracanego snapshotu bazy**. Właścicielem projektu jest [F-008/T-003](../../F-008-jakosc-i-operacje/tasks/T-003-backup-rejestr-i-odtwarzanie.md): szyfrowany append-only journal S3, conditional writes i transactional publisher, bez sieci pod DB lock. Sam rekord wewnątrz starego backupu nie zapobiega wskrzeszeniu; koszt/umowy magazynu wymagają osobnej akceptacji przed użyciem.

Konsekwencja kolejności: request blokuje lokalny User/sesje w commit, ale 202 potwierdzenia dopiero po trwałym journal; cancel najpierw rezerwuje poprawny intent przed deadline, wstrzymuje purge, publikuje i dopiero aktywuje konto; purge dopiero po trwałym `purge_required`. Terminalny outbox i User deletion atomowo; brak publikacji completed nie pozwala GC pominąć purge. Timeout przed potwierdzeniem to wynik nieznany/receipt, nie cofnięcie blokady lub zgoda na zwykły login.

HMAC używa oddzielnego `ACCOUNT_ERASURE_KEY` (co najmniej 32 losowe bajty, wersjonowanie klucza przy rekordzie), nie hasła użytkownika ani rotowanego doraźnie klucza limitera. Klucze potrzebne dla zachowanych markerów/backupów nie znikają przy zwykłym deployu. Propozycja retencji receiptu: 30 dni od terminalnego stanu, potem usunięcie sekretu i zbędnych danych procesu; minimalny rejestr restore ma osobny, uzgodniony horyzont F-007/F-008. Nie wolno usunąć markera tylko dlatego, że wygasł receipt.

F-007 domknął decyzje: bez raw diagnostyki, logi 7/metryki 30 dni, kopie maks. 27 dni, warunkowe transfery poza EOG po weryfikacji. [Projekt retencji](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md) i F-008/T-003 ustalają marker/rejestr 45 dni od terminalnego stanu całego procesu oraz częste kopie dla RPO 1 h, wobec historycznych do 27 dni i dowodów do 30 dni. To techniczny horyzont z testem GC wszystkich wersji, nie wieczysta czarna lista ani ponowny wybór 7+7.

Manifest purge obejmuje także nowe raporty treści, ich lokalne niewysłane szkice, dowód warunków/18+ i prywatne pochodne cache. Normalny TTL 7/30 dni nie usprawiedliwia przekroczenia purge aktywnego konta; minimalny marker/receipt i potwierdzone wyjątki backupów/procesorów opisujemy osobno. Resend Free ma storage USA/30 dni i brak automatycznego API usunięcia pojedynczego maila; nie przedstawiać completed jako dowodu wymazania wszystkich wiadomości u dostawcy/odbiorcy.

Po restore brak udostępnienia usługi do uzgodnienia rejestru: ponownie blokujemy/usuwamy objęte konta, respektujemy skuteczne cofnięcia, nie przywracamy odwołanych sesji i zmieniamy sync db_epoch z F-003. Niejednoznaczność zdarzeń blokuje uruchomienie, nie pomija żądań. Retencja markera obejmuje co najmniej ważność starych dowodów i wszystkie backupy mogące odtworzyć konto; dokładne maksimum i klucz HMAC z F-007/F-008. To pseudonimowe dane o ograniczonym celu, z zatwierdzoną podstawą/okresem, nie wieczysta czarna lista.

Po completed nowa rejestracja pod starym adresem/sub tworzy nowy ID; marker starego User.id nie blokuje nowego konta i nie łączy danych. W czasie grace/purging adres i Google pozostają zajęte, brak automatycznego odtworzenia przez login.

## 8. WWW, maile i limity

Publiczne ścieżki z F-007: `/delete-account` (wyjaśnienie/dowód), `/account/delete-account` (link i końcowe potwierdzenie), `/account/cancel-deletion` (cofnięcie), `/account/deletion-status` (ograniczony status). Tokeny mailowe w fragmentach; GET/skaner niczego nie usuwa, nie cofa i nie loguje. Jawne POST oraz zabezpieczenia nagłówków/CSP jak w F-004.

Strona pokazuje pełen zakres i **obie daty**, odróżnia „przyjęto, można wycofać” od „usunięto”. Ostateczny przycisk żądania wprost potwierdza wszystkie profile, postęp i niewysłaną pracę również na innych urządzeniach. WWW nie zna liczby lokalnych operacji telefonów; nie pokazuje zmyślonego zera. Android może pokazać licznik tego telefonu i zaznacza brak wiedzy o pozostałych.

Do verified adresu: zawiadomienie o przyjęciu z terminem cofnięcia i publicznym wejściem do świeżego dowodu; po cofnięciu zawiadomienie o cofnięciu. Nie wysyłamy po purge nowego maila wymagającego zachowania skasowanej skrzynki w outbox — zakończenie widoczne na receipcie/pomocy. Budżet/wysyłka z F-004, opóźnienie maila nie przesuwa terminów.

Rozszerzyć istniejący limiter F-004, bez nowego mechanizmu:

- Wszystkie publiczne POST tego routera włączone do wspólnego 120/15 min/IP; proof hasła/Google także do kosztowego limitu 20/15 min/IP, hasło do 5/5 min/IP+email.
- Challenge Google 30/15 min/IP; operacje request/cancel po poprawnym dowodzie 3/h/user/akcja. Zgodne retry nie nalicza ponownie limitu mutacji.
- Publiczne mail request 20/15 min/IP; mail per adres+purpose cooldown60 s i 3/h, neutralne 202 przy braku konta/niekwalifikowaniu/limicie odbiorcy; globalne limity/admission jak w F-004.
- Status 60/15 min/IP+hash receipt albo proof; receipt/hasła/nonce nie są surowym kluczem bucketa. `Retry-After`, logi i HMAC jak w F-004. Cofnięcie przyjęte w czasie oceniamy zegarem serwera, nie wyłączamy throttlingu przy granicy.

## 9. Dostarczenie i akceptacja

Podział L: (a) lifecycle i blokada wszystkich zapisów, (b) dowody/request/cancel/status, (c) worker/manifest i idempotencja, (d) Android/WWW oraz dostawcy/restore. Brak uruchomienia przycisku na produkcji przed integracją (a)–(d).

Addytywna migracja bez ustawiania istniejących kont jako usuwane. Backend publikuje stan/kody przed Androidem; F-002/F-008 określają minimalną wersję i zatrzymanie rollout. Starszy klient nie omija server lifecycle, lecz jego zachowanie po 401 nie jest dowodem ochrony lokalnej pracy; istniejące instalacje muszą przejść zgodne wydanie.

- [ ] Testy z kontrolowanym zegarem: T0, przed T0+7 dni, dokładna granica, purging i T0+14 dni; daty w UI wynikają z serwera.
- [ ] Cofnięcie zachowuje User.id i wszystkie dane/postęp; wymaga nowego loginu i nie reaktywuje starych sesji ani dawnych linków zmiany e-maila.
- [ ] Wznowienie importu po zmianie dnia UTC nie duplikuje kart/joba i respektuje 25 kart/profil/dzień; nic nie przenosi `ready`/pełnego cache przed ukończenie enrichment.
- [ ] A-15: aktywny import/enrichment, drugi telefon i outbox nie odtwarzają danych usuniętego konta; pauza grace nie niszczy importowanych kart.
- [ ] Request/cancel/worker równolegle pod barierami PostgreSQL dają jeden zgodny stan; timeout po commit/restart/duplikat nie przesuwa terminów.
- [ ] Snapshot ORM/log/LLM sprzed request nie zapisuje się po nim ani po cofnięciu z nową lifecycle revision.
- [ ] Manifest usuwa także dane bez FK i surowe payloady; test danych kont A/B oraz wspólnego słownika nie narusza B.
- [ ] A-16: WWW na komputerze bez aplikacji obsługuje hasło, podłączone Google i link verified mail; nie tworzy konta przy błędnym Google. GET/skaner niczego nie mutuje.
- [ ] Receipt tylko czyta stan; nie cofa. Link sprzed zmiany rewizji lub poprzedniego procesu nie anuluje nowego.
- [ ] Nowy User.id pod tym samym adresem/Google nie przejmuje Room/outbox ani serwerowego postępu starego.
- [ ] Realny restore z uzgodnionym rejestrem nie wskrzesza kont/sesji; uzasadnione wyjątki odpowiadają publicznym terminom.
- [ ] Testy API/relacji/wyścigów na izolowanym PostgreSQL oraz Room/ViewModel/urządzenie. Bez produkcyjnego SQL i bez użycia prawdziwych kont w destrukcyjnych testach.

**Bramki wykonawcze:** manifest/wyjątki F-007, [kopie/journal/restore F-008/T-003](../../F-008-jakosc-i-operacje/tasks/T-003-backup-rejestr-i-odtwarzanie.md), [alerty F-008/T-004](../../F-008-jakosc-i-operacje/tasks/T-004-monitoring-koszty-i-incydenty.md) i zgodne wydanie F-002 muszą przejść testy przed włączeniem usuwania. Nie zatwierdza to kosztów/umów prawnych. **Poza zakresem:** portal biblioteki WWW, usuwanie konta Google, eksport self-service i kasowanie wspólnego słownika. **Wynik weryfikacji:** kod/oficjalna polityka i decyzje sprawdzone, pełny projekt zapisany; brak implementacji/runtime.
