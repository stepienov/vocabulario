# F-006 · Zarządzanie kontem

**ID:** `E-001/F-006` · **Status:** `ready` · **Epic:** [E-001](../../README.md).

**Wartość:** użytkownik wie, czyje dane widzi, czym konto różni się od profilu nauki i jak zakończyć korzystanie z usługi.

## Zakres i akceptacja

- „Moje konto” pokazuje e-mail, stan weryfikacji i metody logowania bez zbędnych danych osobowych.
- Pomoc, prywatność, odzyskanie/zmiana hasła, zmiana e-maila, logout i usuwanie są rzeczywistymi ścieżkami.
- Usunięcie działa w aplikacji i przez publiczny kanał WWW, z weryfikacją właściciela i informacją o terminie.
- Aktywne kolejki i sesje nie odtwarzają danych; wspólny słownik oraz inne konto są chronione.

## Zatwierdzone zasady usuwania — 17.11.2026

1. Natychmiastowa blokada konta i odwołanie sesji, **7 dni na wycofanie**.
2. Przez okres odstąpienia dane pozostają zachowane; import/enrichment są wstrzymane, nie destrukcyjnie anulowane. Cofnięcie wymaga dowodu właściciela i nowego loginu, bez przywracania starych sesji.
3. Po 7 dniach proces nieodwracalny; następne maksymalnie 7 dni na usunięcie danych aktywnego systemu — **łącznie do 14 dni** od przyjęcia.
4. WWW samoobsługowo, bez aplikacji i bez portalu biblioteki: hasło/podłączone Google albo link na wcześniej zweryfikowany adres. Pomoc awaryjna nie jest obejściem dowodu właściciela.
5. Po zakończeniu ponowna rejestracja tym samym e-mailem/Google tworzy nowe puste konto z nowym ID. Nie przywraca starych kolejek.

Backupy, logi/dostawcy i minimalny rejestr zapobiegający wskrzeszeniu po restore mają jawne wyjątki i zatwierdzone terminy w F-007/F-008. Nie obiecujemy zdalnego wymazania telefonu, który nadal jest offline.

## Stan przygotowania

| Task | Projekt | Integracja / bramka wykonawcza |
|---|---|---|
| T-001 | `/me` z legal/legacy password flag, owner cache, ekran/metody i stany | F-007 definiuje wersje/URL, domena/kontakt uzupełniane przed startem; test na urządzeniu |
| T-002 | Dowody/API, 7+7, pauza/cancel/purge/fencing, manifest, journal i testy | Retencja/cache F-007, append/restore F-008/T-003, alerty T-004, release F-002; prawdziwe umowy/konfiguracja przed włączeniem |

Decyzje i projekty z zależnościami zamknięte do implementacji po zleceniu. `ready` nie stanowi zgody na operację danych ani dowodu skutecznego purge/restore; potrzebne są wyniki implementacji i realne umowy/wyjątki.

| ID | Task | Status |
|---|---|---|
| E-001/F-006/T-001 | [Moje konto](./tasks/T-001-moje-konto.md), B-07 | `ready` |
| E-001/F-006/T-002 | [Usuwanie konta i danych](./tasks/T-002-usuwanie-konta.md), B-08 | `ready` |

**Zależności:** T-001 po sesji Androida, poczcie i Google; akcja usunięcia po T-002. T-002 start po decyzjach i sesjach backendu, integracja urządzenia po E-001/F-003/T-002. WWW nie wymaga budowy pełnego portalu.

Zmiana e-maila ma jednego właściciela: [E-001/F-004/T-004](../F-004-email-i-hasla/tasks/T-004-zmiana-emaila.md); tutaj integrujemy wejście i stany, nie tworzymy drugiej implementacji procesu.

**Weryfikacja:** A-13/A-15/A-16, wszystkie 17 locale, realne zatrzymanie zadań i retencja. **Dowody:** brak.
