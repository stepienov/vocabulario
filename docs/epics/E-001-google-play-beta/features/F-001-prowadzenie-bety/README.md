# F-001 · Zakres i uruchomienie bety

**ID:** `E-001/F-001` · **Status:** `in_progress` — decyzje zapisane, uruchomienie po implementacji i dowodach · **Epic:** [E-001](../../README.md).

**Wartość:** tester otrzymuje świadomie przygotowaną betę z jasnymi ograniczeniami i działającym wsparciem, zamiast przypadkowego debug APK.

## Zakres i akceptacja

- Decyzje o odbiorcach, kontach, danych, dostawcach i środowisku są zapisane przed implementacją zależnych elementów.
- Internal i closed to osobne bramki; spełnienie warunków sklepu nie zastępuje testów jakości.
- Zapisy wyników odnoszą się do konkretnego AAB/backendu; krytyczne zgłoszenia mają właściciela.
- Rozszerzenie dopiero po miarach i bramkach epica. Bez dokładania nowych trybów nauki.

## Taski

| ID | Zadanie | Status |
|---|---|---|
| E-001/F-001/T-001 | [Decyzje i zakres](./tasks/T-001-decyzje-i-zakres.md), dawniej B-00 | `done` — specyfikacja |
| E-001/F-001/T-002 | [Internal i zamknięta beta](./tasks/T-002-uruchomienie-bety.md), dawniej B-14 | `in_progress` — przygotowany [runbook bramek A/B/C](../../../../setup/beta-bramki.md); uruchomienie wymaga działań właściciela |

**Zależności:** decyzje bez zależności technicznych; uruchomienie po wymaganych P0 i końcowej bramce E-001/F-008/T-001. Szczegóły w taskach.

**Weryfikacja:** zapis decyzji oraz [bramki wydania](../../sources/analiza-2026-11-17.md#11-bramki-wejścia-i-wyjścia-z-bety). **Dowody:** kolejne ustalenia w T-001 i macierz polityki konta w F-004; bez testów i implementacji produktu.

Decyzje biznesowe dla obu końcowych bloków zamknięte; nie potrzeba kolejnego „ok” do przygotowania tasków. Następna praca to implementacja na osobne zlecenie. Wykonawcze bramki ID/nazwy/domeny, Console, kraju, umów/kosztu i AI pozostają jawne.
