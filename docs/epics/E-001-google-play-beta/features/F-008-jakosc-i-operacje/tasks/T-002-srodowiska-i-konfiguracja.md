# T-002 · Odizolowane środowiska i konfiguracja

**ID:** `E-001/F-008/T-002` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Jakość i operacje](../README.md). **Źródło:** podział B-13 i decyzje z 17.11.2026.

## Rezultat i decyzje

Testy nie dotykają kont testerów, a konfiguracja pozwala odróżnić błąd wdrożenia od błędnego hasła. Docelowy dodatkowy budżet infrastruktury: możliwie 0, najwyżej **50 EUR miesięcznie ponad obecne utrzymanie**, bez AI i domeny. To limit projektu, nie zgoda na zakup teraz. W becie są prawdziwe konta/postęp, zachowywane również przy późniejszej premierze.

**Start:** kontrakty konfiguracji F-003/F-004/F-005. **Integracja:** [T-001 CI](./T-001-bramki-jakosci.md), [T-003 backup/restore](./T-003-backup-rejestr-i-odtwarzanie.md), [T-004 monitoring/koszty](./T-004-monitoring-koszty-i-incydenty.md), [release F-002/T-001](../../F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md).

## Minimalna topologia

| Środowisko | Dane i przeznaczenie | Zasady |
|---|---|---|
| local/CI | Wyłącznie syntetyczne konta, lokalny PostgreSQL z nazwą `_test`; atrapione AI/poczta/Google | Bez prawdziwych kluczy i dostępu do bety; izolowana baza przy każdym jobie CI |
| staging | Osobny backend i PostgreSQL Railway w regionie UE, uruchamiane przed testami integracji/release | Osobne sekrety i konta usług; brak importowania backupu bety. Zatrzymanie/odtworzenie środowiska nie narusza bety |
| beta | Backend, WWW i PostgreSQL prawdziwych testerów; po premierze ciągłość tej domeny danych | Bez automatycznego resetu po testach, bez destrukcyjnych testów i udawania środowiska syntetycznego |
| recovery | Tymczasowe izolowane środowisko odtwarzania | Bez publicznego ruchu i workerów do ukończenia procedury T-003 |

Staging nie musi działać 24/7: przed oknem testowym uruchomić, potwierdzić gotowość, po nim wyłączyć zasoby obliczeniowe i sprawdzić, co nadal jest płatne. Do testów protokołu wystarcza local/CI; prawdziwe Google/App Links/Play wymagają staging/device. Nie zastępować staging transakcją „potem rollback” na produkcyjnej bazie.

Region beta sprawdzić względem istniejącego [kontraktu regionów E-002](../../../../E-002-szybka-nauka/features/F-001-fundamenty/tasks/T-002-region-api-i-bazy.md). Nie przenosić obecnych danych bez osobnego planu i zgody. Różne środowiska mają różne bazy, origins, tajne klucze JWT/refresh/mail/HMAC, OAuth konfigurację i storage. Sama nazwa projektu lub inny profil użytkownika nie daje izolacji.

## Konfiguracja i sekrety

1. Jeden walidowany model settings środowiska. W `beta`/`staging` jawne `environment`, `debug=false`, zaufane publiczne origins/proxy, issuer/audience, bieżące wersje API/dokumentów i właściwy DB. Domyślne `development`, lokalny URL i pusty sekret nie są fallbackiem produkcji.
2. Sekrety wyłącznie w kontrolowanej konfiguracji usługi/CI i kopii operatora poza Git. Osobne najmniejsze uprawnienia dla runtime, backupu, publishera dziennika i GC/restore; nie jeden klucz administratora. Nie odczytywać ani wypisywać istniejących sekretów na potrzeby dokumentacji.
3. Validate-on-start: brak obowiązkowego pola daje nazwę błędnego pola i stan not-ready, nigdy wartość sekretu. Dla wdrożenia bety obowiązkowe m.in. komplet auth/mail, `PUBLIC_APP_ORIGIN`, bieżące dokumenty, kontakt i ustawione oba progi AI z T-004. Nazwa/ID/domenu i wartości dostarcza właściciel w krokach wykonawczych, nie w publicznym tasku.
4. Kosztowna/usługowa integracja ma jawne `enabled` i spójność pól. Wyłączony Anthropic nie inicjalizuje klienta i nie staje się ukrytym fallbackiem; włączony ma przejść allowlistę dostawców/modeli oraz warunki F-007.
5. Staging początkowo korzysta z atrap/dedykowanych sandboxów. Prawdziwe maile tylko do kontrolowanych skrzynek testowych z allowlisty; rzeczywiste AI tylko w oznaczonym ręcznym smoke teście, z osobnym małym limitem, nigdy w każdym PR.
6. Backend nie ufa dowolnemu `X-Forwarded-For`. Potwierdzić kontrakt ingress Railway kontrolowanym testem; limiter F-004 pozostaje fail-closed. Lista zaufanych proxy jest parametrem wdrożenia, nie `0.0.0.0/0`.
7. WWW: origins/CORS/CSP, wyłączenie niepotrzebnych cookies/trackerów, publiczne legal/support/delete i transakcyjne linki zgodnie z F-007. Sam działający `/health` nie potwierdza dostarczalności poczty i poprawnego klienta Google.

## Gotowość i zgodność wdrożeń

- Zachować prosty liveness; dodać `/health/ready` z kontrolą DB i gotowości schematu/konfiguracji. Publicznie tylko `200 {"status":"ok"}` albo 503, bez nazw tabel, kluczy, właścicieli, kosztów i błędów dostawcy.
- Readiness nie wywołuje AI/poczty/Google ani skanu tabel. Krótki timeout DB do 1 s, cała odpowiedź do 2 s. Kontroluje też mały stan ostatniego heartbeat maintenance (maks. 30 min) i ochrony backupu T-003, aby zewnętrzny monitor wykrył martwą obsługę operacji. To sygnał degradacji dla operatora, nie polecenie skasowania sesji lub wyłączenia dostępnych odczytów. Awaria samego AI nie daje not-ready całego backendu.
- Jeden operator migracji schematu przed dopuszczeniem nowego backendu; nie konkurencyjny DDL z każdej repliki. [Obecne testy](../../../../../../backend/tests/conftest.py) używają `apply_schema`; zachować ten mechanizm, dopisać wersjonowane addytywne kroki zamiast wprowadzać drugi równoległy system.
- Kolejność expand → backend zgodny ze starym kontraktem → zweryfikowany klient → kontrolowane przełączenie minimalnej wersji → ewentualny contract w osobnym wydaniu. Brak automatycznego downgrade schematu lub przywracania starej bazy dla cofnięcia błędnego ekranu.
- Wyłączenie starego protokołu nie niszczy niewysłanej pracy. Nieobsługiwany klient dostaje 426 `app_update_required` z minimum/version i zaufanym URL aktualizacji, bez refresh-loop. Lokalne dane nie są kasowane. Szczegóły okna migracji i pakietów: F-002/T-001.
- Nie ufać wersji klienta jako zabezpieczeniu: sesje/lifecycle/ownership i wymagane pola sprawdzane na serwerze. Stary JWT bez sesji nadal nie daje dostępu.

## Kroki wykonawcze i awarie

Inwentaryzacja obecnego planu/regionu/usług bez wypisywania sekretów → kosztorys T-004 → osobna zgoda na konfigurację → staging → test startup/readiness → próba migracji na syntetycznej starej bazie → smoke test → zatwierdzenie wdrożenia bety.

Nieudany start/migracja zatrzymuje publikację. Brak DB nie tworzy pustej biblioteki ani nowego konta. Timeout testu ma przerwanie i wynik nieznany, nie zielony pipeline. Recovery ma własny sekret dostępu i blokadę wysyłki maili/AI, aby restore nie uruchomił starych zadań.

## Akceptacja

- [ ] Test destrukcyjny z local/CI nie potrafi połączyć się z DB bety; staging/beta/recovery nie współdzielą poświadczeń i outboxu.
- [ ] Macierz brakujące/błędne settings daje not-ready bez sekretów; właściwa konfiguracja działa po restarcie i na drugiej replice.
- [ ] Spoofed proxy, przypadkowy LAN/HTTP, wyłączony dostawca i niezgodny schemat mają jawne wyniki.
- [ ] Upgrade z syntetycznej starej bazy zachowuje User.id/postęp, nowe pola są addytywne, nie oznaczają wstecz weryfikacji ani akceptacji.
- [ ] Zapisano realny plan/region, przewidywany dodatkowy koszt i osobną zgodę operatora przed zmianą usług.

**Poza zakresem:** zakup infrastruktury teraz, reset obecnej bazy, kopiowanie testerów do CI, Kubernetes i przebudowa całego deployu. **Wynik:** projekt; brak zmian konfiguracji/uruchomienia. `ready` dotyczy zakresu do wykonania po zleceniu, nie gotowego staging.
