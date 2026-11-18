# F-003 · Sesja i dane offline

**ID:** `E-001/F-003` · **Status:** `in_progress` · **Epic:** [E-001](../../README.md).

**Wartość:** chwilowa awaria nie zabiera dostępu ani postępu; użytkownik wie, co zapisano i na którym koncie.

## Zakres i akceptacja

- Odwoływalna sesja backendu i spójny stan Androida, DataStore, nawigacji i zadań w tle.
- Pełny wynik synchronizacji; błąd pobrania profili nie udaje braku profilu.
- Bez utraty outboxu bez zgody; spóźniona odpowiedź konta A nie zapisuje się do B.
- Zmiana istniejącego profilu działa local-first z trwałym retry i jawnym konfliktem; nowy profil wymaga sieci.
- Logout jest dostępny lokalnie offline z odroczonym odwołaniem sesji na serwerze. Potwierdzone odwołanie/wygaśnięcie blokuje naukę do reauth, zachowując pracę; zwykła awaria sieci tego nie robi.

**Przygotowanie:** wszystkie cztery taski mają projekt, a zasady offline zostały zatwierdzone zbiorczo. To nie jest implementacja ani dowód działania.

| Kontrakt | Zapisane | Integracja / bramka odbioru |
|---|---|---|
| T-001 backend | Sesje, refresh/retry, transakcje/journal i allowlista identity/study | Rollout/minimum F-002/T-001, klucze/restore F-008/T-002/T-003; testy wyścigów |
| T-002 Android | Owner/generation, trwałe tokeny, reauth/logout offline, worker fencing i legal gate | Retencja sekretu 30 dni F-007, stary/nowy pakiet F-002, ekrany F-006/F-007; proces death/device |
| T-003 sync | Wyniki/pełny licznik, ACK/undo/receipts, snapshot/cursor, tombstones 30 dni | Per-profile horyzont, restore epoch, brak powtórnego create i ochrona overlayów; prawdziwy PostgreSQL |
| T-004 profil | Trwałe local-first/revisions/conflicts i queue UI | Snapshot/draft migracji, 422 po odcięciu legacy zgodnie z F-002; dwie edycje/urządzenia |

Wspólny przegląd projektu obejmuje retencję F-007, procedurę F-002 i nowe stany operacyjne F-008. Nie zostały otwarte ponownie pytania o offline/hasła/Google. `ready` dotyczy kompletnego projektu, wyniki runtime są odbiorem implementacji.

| ID | Task | Status |
|---|---|---|
| E-001/F-003/T-001 | [Sesje backendu](./tasks/T-001-sesje-backendu.md), B-02 | `in_progress` |
| E-001/F-003/T-002 | [Sesja Androida i logout](./tasks/T-002-sesja-androida.md), B-03 | `in_progress` |
| E-001/F-003/T-003 | [Wynik sync i profili](./tasks/T-003-wynik-synchronizacji.md), B-09a | `ready` |
| E-001/F-003/T-004 | [Kolejka i zapis profilu](./tasks/T-004-kolejka-i-profil.md), B-09b | `ready` |

**Zależności:** T-001 po decyzjach E-001/F-001/T-001; T-002 po T-001/T-003; T-004 po T-003. Nie blokujemy rozpoczęcia T-003 gotowym panelem konta.

**Poza zakresem:** nowa architektura offline od zera. **Weryfikacja:** A-05, A-08…A-15, A-17/A-20. **Dowody:** brak.
