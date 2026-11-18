# T-004 · Widoczna kolejka i trwała zmiana profilu

**ID:** `E-001/F-003/T-004` · **Status:** `ready` · **Priorytet / rozmiar:** P1 / M.  
**Feature:** [Sesja i offline](../README.md). **Źródło:** B-09b; F-11 w [analizie](../../../sources/analiza-2026-11-17.md).

## Cel, decyzja i zależności

Użytkownik wie, co istnieje tylko na telefonie, co dotarło na serwer i co wymaga działania. **Zatwierdzone:** edycja poziomu i ustawień istniejącego profilu działa local-first z trwałą kolejką; brak sieci nie daje pozornego zapisu na serwerze. Utworzenie nowego profilu językowego wymaga sieci. Wybór wcześniej pobranego profilu może działać offline.

**Start:** kontrakt wyników i pełnej kolejki [E-001/F-003/T-003](./T-003-wynik-synchronizacji.md). **Integracja:** właściciel/generacja E-001/F-003/T-002 i UI konta E-001/F-006/T-001. Nie czekamy z projektowaniem ekranu na gotowy build; akceptacja obejmuje E-001/F-008/T-001.

## Stan faktyczny

[LearningRepository.updateProfile](../../../../../../android/app/src/main/java/com/vocabulario/app/data/LearningRepository.kt) zmienia lokalny profil przed HTTP, lecz na część błędów zwraca optymistyczny sukces bez trwałego intentu. Przy 404 może wybrać aktualny inny profil i ponowić tam. Istniejący outbox obsługuje ustawienia/listy/karty, ale nie tę zmianę profilu. [Backend profili](../../../../../../backend/app/api/v1/auth.py) nie ma rewizji do rozpoznania konfliktu dwóch urządzeń.

## 1. Stan i ekran kolejki

Wykorzystać raport i transakcyjny `QueueSnapshot` z T-003, bez drugiego licznika. Krótki status przy bibliotece/ustawieniach + rozwijane szczegóły, nie nowy rozbudowany panel:

| Stan | Komunikat i akcja |
|---|---|
| Zapis lokalny, pending | „Zapisano na urządzeniu. Oczekuje na synchronizację”; liczba i profile |
| Offline | „Brak połączenia”; lokalna praca pozostaje, możliwość ręcznego ponowienia po powrocie |
| Wysyłanie | Postęp bez blokowania zwykłej nauki; jeden przebieg sync, brak równoległych submitów |
| Complete | Ostatnia pełna synchronizacja profilu i brak oczekujących zmian |
| Partial / przejściowy błąd | Zachowane liczby, bez komunikatu „Wszystko zsynchronizowane”; „Spróbuj ponownie” |
| Auth / weryfikacja / wymagane warunki | Odpowiednia akcja loginu/weryfikacji/akceptacji F-007, nie „wyczyść dane”; brak fałszywego Complete |
| Blocked/parked/needs_review | Bezpieczna przyczyna, docelowy profil i akcja rozwiązania/świadomego odrzucenia |

Licznik konta obejmuje wszystkie profile; szczegóły mogą filtrować profil, ale pokazują pozostałą pracę. Nie sumować lokalnej listy z jej create intentem podwójnie. Job importu już na serwerze ma oddzielny status. „Ostatnia próba” nie zastępuje „ostatniej pełnej synchronizacji”.

Obejmuje również nowy jawny `content_report` F-007/T-002 w istniejącym outboxie: oczekuje/wysyłany/potwierdzony/błąd, nie „korekta wykonana”. Raport ma własny niezmienny client_report_id i ACK, ten sam owner/generation oraz decyzję o niewysłanej pracy przy logout; bez drugiego licznika i osobnego modułu synchronizacji.

Podzbiór potrzebny do bezpiecznego wysłania/ACK raportu jest bramką F-007 przed closed, niezależnie od P1 rozbudowy ekranu kolejki/edycji profilu. Nie odkładać wymaganej ścieżki zgłoszenia razem z kosmetyką.

Queue UI nie pokazuje surowego JSON, stack trace, tokenów ani odpowiedzi backendu jako tekstu dla użytkownika. Lokalizacja w 17 locale, czytelne stany dla TalkBack, nie tylko kolor/spinner.

## 2. Trwała edycja profilu

W istniejącym outbox dodać `profile_update`; payload wersjonowany: `profileId`, `baseRevision: Long?`, `clientOpId`, wyłącznie zmienione pola `cefr_level`, `selected_tenses`, `app_lang`, `tense_label_lang`. Null bazowej rewizji oznacza draft oczekujący jej ustalenia, nigdy zgodę na bezwarunkowe HTTP. Stabilny profil i właściciel pochodzą z kontekstu, nie z przyszłego active ID.

W jednej transakcji Room: walidacja, lokalny profil + intent. Dopiero po commit UI pokazuje zapis lokalny. Błąd dysku nie jest sukcesem; formularz zachowuje edycję i pozwala ponowić. Profile o innym właścicielu/nieznanym ID nie mogą być celem.

- Dla jednego profilu najwyżej jedna mutacja w locie. Nowsze zmiany lokalne pozostają oddzielnym intentem; nie modyfikować body/ID mutacji, która mogła już dotrzeć na serwer.
- Niewysłane zmiany można scalić per-profile/per-field przed pierwszym HTTP. Nowszy wybór tego samego pola wygrywa lokalnie. Baza rewizji następnego intentu jest aktualizowana dopiero po potwierdzeniu poprzedniego; nie zgadujemy `revision+1` po timeout.
- Echo starszego zapisu nie nadpisuje nowszej lokalnej edycji. Oddzielić ostatni potwierdzony snapshot profilu od overlayu oczekujących pól w istniejącym cache/wersjonowanym payloadzie, bez osobnej nowej bazy.
- Globalne ustawienia konta pozostają w istniejącym `settings_update`; transakcja i ochrona overlayów z T-003 obowiązują również tam. Nie duplikować ustawień w dwóch rodzajach intentów.

### Kontrakt backendu i konflikty

Addytywnie `LanguageProfile.revision BIGINT NOT NULL DEFAULT 1` oraz nullable `last_mutation_id UUID`, `last_mutation_fingerprint CHAR(64)`. Odpowiedź profilu zawiera `revision`. Nowy klient wysyła w istniejącym `PUT /profiles/{id}` `expected_revision` i `client_op_id` razem ze zmienianymi polami.

Pod blokadą wiersza profilu należącego do użytkownika:

1. Najpierw rozpoznać ostatni ten sam ID + fingerprint znormalizowanej mutacji (w tym bazowej rewizji). Identyczne ponowienie zwraca bieżący wynik bez ponownego podniesienia rewizji; inne body tego samego ID →409 `operation_id_conflict`.
2. Inna niż oczekiwana rewizja →409 `profile_conflict`, bez zapisu. Brak właściciela/zasobu →404 `profile_not_found`, bez fallback do aktywnego profilu.
3. Walidacja jak obecnie, kolizja pary →409 `profile_pair_exists`. Atomowo zmiana pól, revision+1 i znacznik mutacji; odpowiedź dopiero po commit.

Nie tworzymy uniwersalnego rejestru idempotencji. Jeśli po zagubionej odpowiedzi inne urządzenie zdążyło zmienić profil i zastąpić ostatni znacznik, retry dostaje konflikt, nie fałszywy ACK; intencja lokalna zostaje.

**Rozstrzygnięcie:** pobrać raz aktualne profile i pokazać konflikt z zachowanym lokalnym draftem. Akcje „Przyjmij ustawienia z serwera” (jawnie odrzuca tę edycję) albo „Zastosuj moje zmiany” (nowy ID i aktualna baseRevision, ponowna walidacja). Nie stosować automatycznego last-writer-wins ani ponawiania na innym profilu. Kolejny konflikt ponownie wymaga rozstrzygnięcia, bez pętli.

404 pozostawia informację o niedostępnym profilu i draft; można go świadomie odrzucić/wybrać istniejący profil, ale nie przypisujemy do niego kolejki poprzedniego. 422 pokazuje pola do korekty; 429 respektuje retry; 5xx/transport zachowują intent. Pobranie listy profili nie usuwa profilu/draftu z lokalną pracą.

### Wybór i tworzenie profilu

Wybór znanego profilu lokalnie: transakcja aktywnego ID w Room, zmiana projekcji locale i trwały `profile_activate` dla istniejącego endpointu aktywacji; ostatni niewysłany wybór można scalić. Każdy request nadal jawnie niesie swój profile ID. Pull nie przestawia widocznego profilu tylko dlatego, że inne urządzenie zmieniło serwerowe `is_active`.

Nowy profil wymaga potwierdzenia serwera; bez tworzenia pozornego profilu offline. 409 istniejącej pary pozwala odnaleźć ten sam profil w jednorazowym odświeżeniu listy i wybrać go jawnie; błędu pobierania nie zamieniać w pustą listę. Zmiana języka UI urządzenia jest lokalną preferencją, nie dowodem zapisu nowej pary na serwerze.

## 3. Migracja, dostarczenie i akceptacja

Backend najpierw dodaje rewizje/pola odpowiedzi. W przejściowym okresie legacy update bez expected_revision jest obsługiwany tylko do uzgodnionej granicy zgodności; **każda** zaakceptowana mutacja edytowanych pól, także legacy/admin, podnosi revision i usuwa nieaktualny znacznik ostatniej mutacji. Samo activate/last_used nie powoduje konfliktu edycji poziomu. Po przełączeniu minimalnej wersji braki pól nowego kontraktu są 422, nie bezwarunkowy zapis.

Istniejące profile dostają revision=1. Ich bazową wersję klient ustala online zanim wyśle nowy intent; przy offline zachowuje lokalny draft jako oczekujący ustalenia bazy. Po pierwszym pobraniu porównuje ostatni znany snapshot: zmienione po obu stronach pola → konflikt; bez wiarygodnego snapshotu wymaga potwierdzenia, nie nadpisuje serwera w ciemno.

Już utraconego intentu ze starego `updateProfile` nie da się wiarygodnie odtworzyć z samego optymistycznego cache. Różnice przy migracji zachować jako draft do rozstrzygnięcia, nie oznaczać wstecz jako zsynchronizowane. To nie jest przenoszenie danych między użytkownikami.

- [ ] A-14: poziom/czasy/język profilu offline mają trwały intent i napis „na urządzeniu”; restart nie gubi zmiany.
- [ ] Zakończenie procesu między zapisem profilu/outbox jest atomowe. Błąd zapisu pozostawia formularz bez fałszywego potwierdzenia.
- [ ] Dwie szybkie edycje i stara odpowiedź w locie nie cofają nowej; retry identycznej mutacji nie wykonuje jej ponownie.
- [ ] Dwa urządzenia, 409 obu rodzajów, 404 i 422 zachowują draft i wymagają poprawnego rozstrzygnięcia; brak fallback do innego active ID.
- [ ] Queue UI uwzględnia wszystkie rodzaje/statusy/profili; parked i needs_review nie znikają z ostrzeżenia logout.
- [ ] Zmiana właściciela unieważnia stary callback; pobranie profili nie usuwa niewysłanych zmian.
- [ ] Testy jednostkowe ViewModel, Room i backendu na izolowanym PostgreSQL; ręcznie offline/restart i TalkBack/locale.

**Integracja:** API/wyniki T-003, owner/cache T-002, retencja F-007 i granica starych klientów w [F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md). Legacy update bez expected_revision kończy się przy przełączeniu protokołu, nie „kiedyś”. **Poza zakresem:** multi-account, tworzenie nowych profili offline i panel administracyjny. **Wynik weryfikacji:** zatwierdzony wariant local-first i kompletny projekt, bez implementacji/testów runtime.
