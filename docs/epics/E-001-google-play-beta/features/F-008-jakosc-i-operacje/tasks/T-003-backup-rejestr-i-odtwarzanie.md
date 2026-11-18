# T-003 · Backup, dziennik konta i bezpieczne odtwarzanie

**ID:** `E-001/F-008/T-003` · **Status:** `ready` · **Priorytet / rozmiar:** P0 / M.  
**Feature:** [Jakość i operacje](../README.md). **Źródło:** B-13, usuwanie F-006, decyzje z 17.11.2026 i **18.11.2026** (backup wyłącznie w Railway, retencja do około 30 dni).

## Rezultat i zależności

Cel właściciela: **RPO do 1 h**, **RTO do 24 h od wykrycia** katastroficznej awarii. To cele wymagające próby, nie gwarancja dyżuru 24/7. Zwykła aktualizacja/logowanie nadal nie usprawiedliwiają utraty pracy. Konta i postęp bety mają przetrwać betę.

**Start:** [środowiska T-002](./T-002-srodowiska-i-konfiguracja.md) i [lifecycle F-006/T-002](../../F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md). **Integracja:** [retencja F-007/T-001](../../F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md), [sesje F-003/T-001](../../F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md), [sync F-003/T-003](../../F-003-sesja-i-offline/tasks/T-003-wynik-synchronizacji.md), [alerty T-004](./T-004-monitoring-koszty-i-incydenty.md). Ruch po restore dopiero po całej procedurze, nie po samym odtworzeniu bazy.

## Decyzja: tylko Railway (18.11.2026)

Bez AWS i bez innego zewnętrznego magazynu. Wcześniejszy projekt S3 + `age` + zewnętrzny journal został **zastąpiony** jako zbyt ciężki dla zamkniętej bety. Świadomie akceptowane ryzyko: kopie i baza są u jednego dostawcy; całkowita utrata projektu Railway nie jest pokryta. Powrót do zewnętrznej kopii to osobna decyzja przed szerszą publikacją.

Warstwy według [przewodnika Railway](https://railway.com/guides/postgres-backups-restores):

| Warstwa | Ustawienie | Retencja | Rola |
|---|---|---|---|
| [Point-in-time recovery](https://docs.railway.com/volumes/point-in-time-recovery) | Włączone na produkcyjnym Postgres przed pierwszym testerem | ok. 4 tygodnie (4 pełne kopie tygodniowe + WAL) | Główne odtworzenie do chwili sprzed incydentu; RPO w praktyce minuty |
| [Volume backups](https://docs.railway.com/volumes/backups) dzienne | Włączone | 6 dni | Szybki powrót po złym wdrożeniu/migracji |
| Volume backups tygodniowe/miesięczne | **Wyłączone** | — | Przekraczałyby uzgodnioną retencję |
| Ręczny backup przed ryzykowną migracją | Tylko gdy potrzebny | usunąć ręcznie najpóźniej po 30 dniach | Punkt powrotu przed zmianą schematu |

**Retencja kopii: do około 30 dni** (decyzja 18.11.2026 zastępuje „maks. 27 dni”). To wartość deklarowana w informacji o prywatności F-007; nie obiecywać krótszej. Restore PITR tworzy nową usługę obok źródłowej; stare/rozwidlone usługi i wolumeny po incydencie usuwa się po weryfikacji, najpóźniej w tym samym limicie, i odnotowuje w rejestrze incydentu.

Lokalny `pg_dump` operatora służy wyłącznie próbie restore: szyfrowany dysk, usunięcie po próbie, bez przechowywania w Git/chmurze prywatnej. Hasło DB nie trafia do argv/logów skryptów repo.

PITR nie ma osobnej opłaty; płaci się storage bucketu i egress. Koszt ujmuje kosztorys [T-004](./T-004-monitoring-koszty-i-incydenty.md).

## Monitorowanie kopii

Railway zarządza archiwizacją WAL; aplikacja nie mierzy wieku snapshotu i **nie ma trybu 503 ochrony zapisów** (wcześniejszy `backup_protection_active` usunięty). Zamiast tego:

- przed betą: potwierdzenie, że PITR jest „healthy”, istnieje pierwsza pełna kopia i datetime picker pokazuje okno;
- co tydzień i po każdym wdrożeniu zmieniającym bazę: operator sprawdza status archiwizacji i datę ostatniej kopii dziennej (lista kontrolna w T-004);
- jeżeli Railway udostępni alert/webhook o błędzie archiwizacji, podłączyć go do e-maila operatora z T-004; do tego czasu ręczna kontrola jest jawnie zapisanym ograniczeniem.

## Dziennik konta (w bazie)

Tabela `account_journal` w tej samej bazie: append-only zdarzenia lifecycle i bezpieczeństwa — `deletion_requested`, `deletion_cancel_intent`, `deletion_cancelled`, `purge_required`, `purge_completed`, `password_reset`, `password_change`, `password_added`, `google_linked`, `email_changed`. Pola: event UUID, process UUID, typ, subject HMAC User.id (`ACCOUNT_ERASURE_KEY` z F-006), expected/target `lifecycle_revision`/`credentials_revision`/`email_revision`, czasy/terminy. Bez e-maila, Google sub, hasła/PHC, tokenów i treści nauki. Bez CASCADE od User: po purge zostaje pseudonimowy marker do jego retencji.

Zapis zdarzenia w **tej samej transakcji** co zmiana User/procesu (wspólna kolejność blokad F-003/T-001: User → sesje → retry → proces/dziennik). Nie ma osobnego publishera, lease ani zewnętrznego magazynu; 202/200 odpowiedzi operacji konta po commit.

Każde zdarzenie dodatkowo trafia jako jedna linia logu strukturalnego (`account_journal`: event UUID, typ, subject HMAC, rewizje) do logów Railway, które są **poza odtwarzaną bazą**. To minimalny ślad na okno utracone przy restore, w granicach retencji logów F-007; nie zawiera danych identyfikujących poza pseudonimem.

Retencja: receipt 30 dni od terminalnego stanu, marker/dziennik 45 dni od terminalnego stanu procesu; otwarty proces nie znika przez wiek.

## Przywracanie bezpieczeństwa kont

Odtworzenie danych nie może przywrócić odwołanej sesji ani starego hasła/adresu sprzed skutecznej zmiany. Po każdym restore, przed ruchem:

1. Odwołać **wszystkie** sesje, refresh retry i jednorazowe dowody (powód `restore`); nowe `db_epoch`. Klient wymusza nowy login bez kasowania lokalnej pracy (F-003/T-002).
2. Porównać log `account_journal` z okresu od punktu restore do odcięcia ruchu z odtworzonym dziennikiem w bazie. Zdarzenie w logu, którego brak w bazie:
   - `deletion_requested`/`purge_required`/`purge_completed` → ponownie zastosować blokadę/usunięcie dla tego subject zgodnie z F-006 (bez wskrzeszania);
   - `deletion_cancelled` → zachować anulowanie tylko gdy rewizja lifecycle jest zgodna; inaczej blokada i ręczne rozstrzygnięcie;
   - zmiana bezpieczeństwa (hasło/adres/Google) → `User.restore_recovery_required = true` (addytywne, domyślnie false).
3. Login z `restore_recovery_required`: poprawny dowód daje 403 `restore_recovery_required` zamiast tokenów; błędne dowody nadal neutralne 401. Odzyskanie: reset na adres niezmieniony w utraconym oknie, podłączone Google albo ręczna obsługa operatora; bez przypisania po samym e-mailu. UI `ReauthRequired(reason=restore_recovery)`/pomoc.
4. Gdy logi z okna są niedostępne lub niejednoznaczne: `restore_recovery_required` dla kont zmienionych w ostatniej dobie przed punktem restore (według `updated_at`/rewizji) i jawny wpis w raporcie incydentu. Brak User nie oznacza `account_deleted` bez markera i nie uprawnia do przypisania starego outboxu nowemu ID.

## Procedura odtworzenia

1. Zapis początku incydentu/detekcji; wstrzymanie rolloutu, workerów i zapisów (maintenance F-008/T-002).
2. PITR „Restore to this moment” do chwili tuż przed incydentem → nowa usługa obok; weryfikacja liczby wierszy/ostatnich zapisów kluczowych tabel. Źródło pozostaje nietknięte do przełączenia.
3. Uzgodnienie dziennika i bezpieczeństwa według sekcji wyżej; dopiero potem workery/poczta, bez wysyłania na adresy ze starego stanu.
4. Smoke: izolacja kont A/B, stare tokeny odrzucone, nowy login działa, receipt/terminy, brak wskrzeszenia usuniętych danych, pełny pull zachowujący lokalne overlaye, stary cursor → 410/nowy pull.
5. Przełączenie connection string, włączenie PITR na nowej usłudze (fork nie archiwizuje sam), potwierdzenie pierwszej kopii, komunikat o skutkach RPO. Stara usługa/wolumen usunięte po weryfikacji, w limicie retencji.

## Akceptacja

- [ ] PITR i kopie dzienne włączone na produkcji, tygodniowe/miesięczne wyłączone; zrzut ustawień i data pierwszej kopii zapisane przed pierwszym testerem.
- [ ] Próba restore PITR na staging lub kopii produkcji przed closed: zmierzony czas do gotowości (≤24 h) i wiek odtworzonych danych (≤1 h); powtórka co miesiąc i po istotnej zmianie schematu. Nieudana próba blokuje rozszerzenie.
- [ ] Testy backendu: zdarzenie dziennika w tej samej transakcji co zmiana (rollback nie zostawia zdarzenia ani zmiany), linia logu bez danych identyfikujących, odwołanie wszystkich sesji po restore, 403 `restore_recovery_required` tylko po poprawnym dowodzie.
- [ ] Scenariusze: usunięcie/anulowanie/zmiana hasła po punkcie restore nie wskrzeszają danych ani dostępu.
- [ ] Retencja: brak kopii starszych niż ok. 30 dni, w tym ręcznych i rozwidlonych usług po incydencie.

**Poza zakresem:** zewnętrzny magazyn kopii (AWS/S3 i inne), odporność na utratę całego projektu Railway, automatyczny restore produkcji, zerowe RPO. **Wynik:** projekt po decyzji 18.11.2026, bez włączonego PITR i bez próby restore.