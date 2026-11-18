# T-003 · Backup, niezależny rejestr i bezpieczne odtwarzanie

**ID:** `E-001/F-008/T-003` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / L.  
**Feature:** [Jakość i operacje](../README.md). **Źródło:** B-13, usuwanie F-006, decyzje z 17.11.2026.

## Rezultat i zależności

Cel właściciela: **RPO do 1 h**, **RTO do 24 h od wykrycia** katastroficznej awarii. To cele wymagające próby, nie dowód obecnego backupu ani publiczna gwarancja dyżuru 24/7. Zwykła aktualizacja/logowanie nadal nie usprawiedliwiają utraty pracy. Konta i postęp bety mają kontynuować życie po becie.

**Start:** [środowiska T-002](./T-002-srodowiska-i-konfiguracja.md) i [lifecycle F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md). **Integracja:** [retencja F-007/T-001](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md), [sesje F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md), [sync F-003/T-003](../../F-003-sesja-i-offline/tasks/T-003-wynik-synchronizacji.md), [alerty T-004](./T-004-monitoring-koszty-i-incydenty.md). Restore dopuszcza ruch dopiero po całej procedurze, nie po samym `pg_restore`.

## Wybór magazynu i granice

Projekt: prywatny **AWS S3 Standard, eu-central-1**, osobne buckety/prefixy i uprawnienia dla zaszyfrowanych kopii oraz dziennika praw/bezpieczeństwa. Wybór techniczny pod cel trwałości, nie utworzone konto/usługa. Przed użyciem: właściciel akceptuje rzeczywisty koszt, DPA/transfery i konfigurację, zgodnie z F-007/T-001. Nie zakładać darmowego AWS, kredytów ani lokalizacji każdego podprocesora wyłącznie w UE.

Powód odrębnego wyboru: [Railway Buckets](https://docs.railway.com/storage-buckets) obecnie nie oferują versioning, Object Lock ani lifecycle/backupów bucketu. Nie przypisujemy tych funkcji do „S3-compatible”. Amazon S3 dokumentuje conditional writes i versioning. Dziennik w drugiej tabeli tej samej odtwarzanej bazy nie spełnia wymogu niezależności.

General purpose buckets, Block Public Access, **Versioning Enabled**, TLS i szyfrowanie po stronie klienta; żadnych publicznych URL i tokenów w nazwie obiektu. Bez Object Lock z retencją blokującą terminowe wymazanie; least privilege publishera i version-aware GC są jawnym mechanizmem. Format kopii: `pg_dump --format=custom` strumieniowany przez `age` do pliku szyfrowanego; backup/publisher znają tylko publiczny recipient. Prywatny klucz odszyfrowania operator przechowuje poza aplikacją/Git, z drugą zaszyfrowaną kopią i próbą odczytu. Małe zdarzenia dziennika też szyfrowane; podpis/HMAC wersjonowany oddzielnym kluczem poza snapshotem bazy.

Niezbędne narzędzia `pg_dump/pg_restore`, klient S3 i `age` dodać jawnie do obrazu/jobu w czasie implementacji z przypięciem wersji, bez pobierania niezweryfikowanego skryptu przy każdym backupie. Synchroniczny klient storage nie blokuje event loop FastAPI; I/O poza transakcjami DB.

## Kopie i ich wykonanie

| Kopia | Harmonogram / retencja |
|---|---|
| Częsta logiczna | Co 30 min, zachowanie przez 24 h; margines na wykonanie i wykrycie przerwy przy celu RPO 1 h |
| Dzienna | Jedna ukończona kopia dziennie, do 6 dni |
| Tygodniowa | Jedna ukończona kopia tygodniowo, do 27 dni od wykonania |
| Ręczna przed zmianą | Tylko gdy potrzebna, z jawnym terminem nie dłuższym niż 27 dni |

Cotygodniowa/codzienna kopia może być oznaczeniem już ukończonego obiektu, nie kolejnym pełnym dumpem. Nie obniżać częstotliwości do doby w celu zmieszczenia kosztu; brak możliwości celu lub przekroczenie 50 EUR dodatkowej infrastruktury wymaga konkretnej decyzji przed uruchomieniem.

Osobny krótko działający job co 30 min; blokada/lease wyklucza nakładanie, timeout 10 min, stary job nie publikuje nowszego manifestu. Gdy baza nie mieści się w tym oknie, alarm i nowy projekt pojemności, nie urwana kopia. Nie robić backupu w request użytkownika ani w workerze Androida.

Manifest ukończenia: środowisko, losowy backup ID, start spójnego snapshotu, koniec, wersje PostgreSQL/schematu/kodu, długość, SHA-256 zaszyfrowanego pliku, key version, retencja i referencja do niezależnego dziennika. Publikowany dopiero po udanym dump/encrypt/upload i weryfikacji checksum; multipart/temp obiekt nie jest backupem. Hasło DB nie trafia do argv/logów. Retencję liczyć konserwatywnie od początku snapshotu.

GC co 15 min uwzględnia wszystkie wersje obiektu i przerwane multipart. Sam DELETE dodający delete marker w versioned bucket **nie usuwa starych danych**. Osobny GC principal ma uprawnienie trwałego usunięcia wersji; runtime/publisher nie. Wszystkie kopie, w tym ręczne/local i stare wolumeny po restore, są zinwentaryzowane. Usunięcie starych wolumenów po weryfikacji jest oddzielną kontrolowaną operacją, nie automatycznym szerokim `delete`.

S3 lifecycle jest dodatkową barierą, nie dowodem punktualnego usunięcia ani zamiennikiem kontroli wersji/GC. Żaden restore nie służy zwykłemu podglądaniu starych danych. Wiek liczymy od **startu snapshotu** ostatniej ukończonej kopii, nie końca uploadu. 45 min daje pilny alert, już **55 min** ochronny tryb ograniczenia nowych zapisów nauki/importu z jawnym 503 `backup_protection_active`; 60 min oznacza naruszenie celu i alarm. Pięć minut to margines, nie pozwolenie na opóźniony cron.

Guard wieku na wejściu i przed commit zapisów requestów/workerów, na bazie wspólnego stanu ostatniego potwierdzonego snapshotu; nie czekać na cron co 15 min i nie robić N+1 odczytu per karta. Lokalny cache starszego znacznika może blokować wcześniej, nie przedłużać okna. Brak znacznika/niepewny stan = ochrona. Pierwszą kopię wykonać przed dopuszczeniem bety.

Lokalna praca pozostaje w Room. Odczyt, pomoc i operacje praw/bezpieczeństwa z trwałym dziennikiem pozostają dostępne; nie odwoływać sesji z powodu backupu. Powrót po potwierdzeniu nowej pełnej kopii, bez resetu kolejek.

## Niezależny dziennik usunięć i cofnięć

### Dane, zapis i idempotencja

Osobny transactional outbox `account_journal_outbox` w PostgreSQL **do publikacji**, lecz źródłem replay po restore są obiekty S3, nie odtworzony outbox. Pola: event UUID, process UUID, seq, typ, expected/target rewizje `User.lifecycle_revision`, `User.credentials_revision`, `User.email_revision` zgodne z F-003/F-004, subject HMAC User.id, czasy/deadline, prev digest, podpis/key version, niezmienne szyfrowane bytes, digest, lease/attempt/next retry/durable_at. Bez e-maila, Google sub, hasła, treści nauki i tokenów. Subject HMAC stosuje wersjonowany `ACCOUNT_ERASURE_KEY` z F-006.

Obiekt `journal/{process_uuid}/{seq}-{event_uuid}` ma niezmienne bytes. `PutObject If-None-Match: *`; przy 412 odczytać istniejący obiekt i porównać digest, identyczny jest retry, inny zatrzymuje proces/alarmuje. Publisher nie ma prawa nadpisywania/usuwania, bucket policy wymusza conditional put. S3 error/timeout nie jest potwierdzeniem trwałości; sprawdzenie tego samego klucza rozstrzyga wynik. Nie używać ETag jako uniwersalnego SHA-256 pliku.

Jedna sekwencja per proces, publikacja kolejnego zdarzenia dopiero po potwierdzonym poprzednim. Claim 60 s z fencing tokenem; I/O bez blokad DB, po nim sprawdzenie lease i bieżącej rewizji przed ACK. Powtórzenie nie zmienia zdarzenia, T0 i terminu. Retry 30 s, 2 min, 10 min, potem co 15 min z alarmem; brak cichego terminalnego drop.

Claim kończy swoją transakcję przed HTTP; ACK zaczyna od User (jeśli istnieje), potem proces i outbox, nigdy odwrotnie względem wspólnej kolejności F-003. Minimalny outbox końcowy nie ma CASCADE od User: po purge pozostaje pseudonim procesu do potwierdzenia terminalnego zdarzenia/GC, bez danych biblioteki i sekretów.

### Kolejność względem User i odpowiedzi

1. **Request:** pod wspólną blokadą User utworzyć proces/receipt i zdarzenie, zablokować konto oraz odwołać sesje, commit. T0 i terminy ustalone raz. Opublikować poza transakcją. 202 „przyjęto” dopiero po potwierdzonej trwałości zdarzenia. Wcześniejszy błąd/timeout daje wynik nieznany i status receipt, bez powrotu do nauki; klient zachowuje receipt przed HTTP według F-006.
2. **Cancel:** przed `cancel_until`, pod blokadą User sprawdzić dowód i zapisać trwały intent anulowania/zdarzenie, lecz **jeszcze nie aktywować User**. Intent wstrzymuje purge i jest widoczny jako rozstrzyganie. Po potwierdzeniu zdarzenia poza DB dopiero osobna transakcja zgodnej rewizji ustawia cancelled/active. 200 po commit; restart kończy ten sam intent. Przejście terminu podczas publikacji nie unieważnia poprawnie przyjętego pod blokadą intentu. Niepewnego anulowania nie wolno zamienić w purge; alarm przy niedotrzymaniu terminu, bez udawania sukcesu.
3. **Purge start:** zdarzenie `purge_required` musi być trwałe przed nieodwracalnym usuwaniem. Odtworzenie takiego wpisu wymusza dokończenie purge nawet bez późniejszego completed.
4. **Completed:** User usunięty i proces completed atomowo według F-006; potem publisher zapisuje terminalne zdarzenie. Awaria tej publikacji nie wskrzesza danych: istnieje już trwałe `purge_required`. Brak terminalnego zdarzenia blokuje GC dziennika i alarmuje, nie zmienia zakończonego usunięcia na aktywne konto.

To jawny protokół dwóch magazynów, nie fikcyjna wspólna transakcja S3/Postgres. Zwiększenie lifecycle oraz sprawdzanie `journal_pending`/cancel intent obejmuje zapisujące workery. Jeśli nie da się ustalić końca operacji, brak normalnego ruchu tego konta, a nie kasowanie danych telefonu.

### Retencja i kompletność

Receipt 30 dni od terminalnego stanu, minimalny dziennik/marker 45 dni od **terminalnego stanu całego procesu**, nie od pierwszego eventu. Otwarty/purge-required proces nie znika przez arbitralny wiek; jego opóźnienie jest incydentem. GC usuwa komplet zamkniętego segmentu dopiero gdy żaden zachowany backup/stary dowód go nie wymaga, z wszystkimi wersjami; brak wystarczającego horyzontu blokuje restore, nie daje milczącego przedłużenia.

Restore listuje wszystkie strony dziennika, weryfikuje HMAC/podpis, klucze i łańcuchy per proces. Następnie uzgadnia **per subject/User.id według monotonicznej lifecycle_revision**, nie kolejności LIST, UUID ani samych dat: stare cancel nie reaktywuje nowszego procesu usuwania. Najpierw rozstrzyga lifecycle, potem porównuje security revisions; niejednoznaczność = blokada. Nie traktuje błędu uprawnień/transportu jako „pusty dziennik”. Nowy User.id z tym samym adresem nie jest objęty starym procesem.

## Przywracanie bezpieczeństwa kont

Odtworzenie danych nie może przywrócić odwołanej sesji lub starego hasła/adresu sprzed skutecznej zmiany. Przed ponownym ruchem odwołać **wszystkie** odtworzone sesje, refresh retry i jednorazowe dowody; wymusić nowy login bez kasowania lokalnej pracy.

Ten sam dziennik ma minimalne zdarzenia autoryzowanych zmian `password_reset/password_change/password_added/google_linked/email_changed` z docelowymi revisions. Zdarzenie-intent musi być trwałe **przed finalną zmianą poświadczeń/wyjściową odpowiedzią**; dane sekretne nie są kopiowane do dziennika. DB ma krótki `security_change_pending` i nie uruchamia równoległej zmiany tego User. Błąd magazynu zachowuje dotychczasowe poświadczenia i jawny wynik operacji; retry/recovery rozstrzyga ten sam intent, bez trzymania hasła w logu lub zewnętrznym journal.

Zmiana User oraz outbox `security_applied` w jednym commit; publisher domyka segment. Jeżeli po restarcie/braku ponowienia nie ma materiału do ukończenia, po 10 min pod User lock zamknąć niezmieniony intent jako `security_aborted`, z fencing/revision uniemożliwiającym późniejszy commit starego requestu. Sam intent po restore oznacza ostrożnościową blokadę, nigdy dowód wykonanej zmiany. Retencja tych minimalnych segmentów również 45 dni od terminalnego stanu; nie zawierają materiału do odtworzenia hasła/skrzynki.

Po restore porównać revisions z dziennika z odtworzonym User, nie tylko timestamps (długa transakcja mogła nie wejść do snapshotu). Gdy wynik zmiany nie jest w bazie lub intent jest niejednoznaczny, ustawić `User.restore_recovery_required` (addytywne boolean, domyślnie false). Po poprawnym dowodzie taki login nie wydaje zwykłych tokenów: 403 `restore_recovery_required`; niepoprawne dowody nadal mają neutralne 401. Nowy reset do potencjalnie starej skrzynki nie omija blokady. Ograniczony świeży proof do recovery nie jest sesją biblioteki.

Odzyskanie tylko świeżym, nadal zaufanym dowodem: reset do verified skrzynki, jeżeli późniejsze zdarzenie jej nie zmieniało; podłączone Google, jeżeli jego powiązanie jest nadal potwierdzone; po utracie zmiany adresu świeży dowód niezmienionej metody i potwierdzenie nowej skrzynki. Jeśli nie można wykazać zaufanego dowodu, ręczna obsługa przez operatora, bez automatycznego przypisania po samym e-mailu i bez zgadywania. UI używa `ReauthRequired(reason=restore_recovery)`/pomocy. Brak User po utracie ostatniej godziny nie oznacza `account_deleted` bez markera i nie uprawnia do przypisania starego outboxu nowemu ID.

Przy implementacji rozłożyć: (a) outbox/publisher i testy granic commit, (b) integracja operacji F-003/F-004/F-005/F-006, (c) job kopii/retencja, (d) operator restore/test. Nie wdrażać przycisku usuwania ani finalnego nowego auth bez odpowiadającej integracji dziennika.

## Procedura odtworzenia

1. Operator zapisuje początek incydentu/detekcji, zatrzymuje rollout, publiczne zapisy i workery. Nie odtwarza wprost na działającą bazę.
2. W recovery pobiera najnowszą kompletną kopię, weryfikuje manifest/checksum, odszyfrowuje kontrolowanym kluczem, przywraca do nowej izolowanej bazy. Brak klucza/dziennika/digestu zatrzymuje procedurę.
3. Replay wszystkich nowszych i nadal istotnych zdarzeń: pending blokada/pauza, skuteczne cancel przywraca ten sam ID, purge_required/completed usuwa z manifestem F-006 również logi/cache/outbox. Bez powiadamiania adresów ze starego snapshotu.
4. Uzgadnia revisions bezpieczeństwa, odwołuje sesje/dowody, nadaje nowe `db_epoch`. Nie uruchamia starych outboxów pocztowych i zadań, dopóki lifecycle, intenty i uprawnienia nie są uzgodnione.
5. Podczas końcowej listy/replay zatrzymuje przyjmowanie nowych operacji do starego backendu; sprawdza jeszcze raz dziennik po odcięciu ruchu. Inaczej można pominąć cancel przyjęte tuż przed przełączeniem.
6. Uruchamia smoke: A/B izolacja, stare tokeny odrzucone, poprawny nowy login, receipt/terminy, brak wskrzeszenia danych, pełny pull zachowujący lokalne overlaye, pusty/stary cursor →410/nowy pull.
7. Wykonuje świeżą kopię i potwierdza monitoring. Dopiero wtedy przełącza usługę, włącza dozwolone workery i informuje o skutkach RPO. Stary wolumen/tymczasowe odszyfrowane pliki mają kontrolowany termin usunięcia w ramach 27 dni, preferencyjnie po potwierdzeniu poprawności.

## Akceptacja

- [ ] Awaria dump/encrypt/upload, timeout po PUT, ten sam event retry, zły digest/412, zerwany łańcuch i restart po każdej granicy mają test; żaden błąd nie daje fałszywego „backup/żądanie zakończone”.
- [ ] Restore odtwarza spójny PostgreSQL, a nie tylko rozpakowuje plik; zmierzono wiek snapshotu względem zaakceptowanych zapisów i czas do gotowości.
- [ ] Scenariusze grace/cancel/purge/completed, zdarzenie po snapshotcie i nowy User.id pod starym adresem nie wskrzeszają danych/sesji.
- [ ] Zmiana hasła/adresu/Google w utraconej godzinie nie umożliwia użycia cofniętego stanu; sprawdzony recovery bez przejęcia konta.
- [ ] RPO ≤1 h i RTO ≤24 h od wykrycia udowodnione w staging przed closed; próba co miesiąc i po istotnej zmianie mechanizmu. Nieudana próba blokuje rozszerzenie/uruchomienie, nie obniża progu samoczynnie.
- [ ] Fizyczna retencja obejmuje starsze wersje, multipart, kopie ręczne i pozostałe wolumeny; koszty/umowy/klucze mają potwierdzenie wykonawcze.

## Źródła

Sprawdzone 17.11.2026: [S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html), [conditional writes i wymuszenie polityką](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html), [cennik i klasy](https://aws.amazon.com/s3/pricing/), [ograniczenia Railway Buckets](https://docs.railway.com/storage-buckets). Nie używać Glacier/IA z minimalnym okresem rozliczenia/odtwarzaniem niepasującym do retencji i RTO.

**Poza zakresem:** uruchomienie teraz, pełna odporność na jednoczesne przejęcie wszystkich kont operatora/kluczy, gwarancja zerowego RPO, automatyczny restore produkcji. **Wynik:** konkretny projekt, bez utworzenia bucketu, backupu lub próby restore.
