# Dokumentacja Vocabulario

## Zacznij tutaj

**[Rejestr epików](./epics/README.md)** jest stałym punktem wejścia do tematów produktu. Aktualny priorytet: **[E-001 · Beta Google Play](./epics/E-001-google-play-beta/README.md)**.

Nowy temat opisujemy jako epic z założeniami biznesowymi, dzielimy na features, a w razie potrzeby na taski. Pełne ID zadania: `E-001/F-004/T-001`. Po zakończeniu zmienia się status i zapis dowodów — dokument **nie wędruje do archiwum**.

## Mapa

| Obszar | Dokument | Rola |
|---|---|---|
| Tematy produktu | [Rejestr epików](./epics/README.md) | Priorytety, rezultaty i statusy |
| Organizacja pracy | [Zasady epików](./epics/zasady.md) | Numeracja, struktura, statusy, minimalna treść i ukończenie |
| Bieżąca praca | [E-001 · Beta](./epics/E-001-google-play-beta/README.md) | Konta, dane, dystrybucja, samodzielna obsługa przez testera |
| Kontrakty optymalizacji | [E-002 · Szybka nauka](./epics/E-002-szybka-nauka/README.md) | Zachowane taski, zwłaszcza nauki/importu; nie ponowna kolejka |
| Rozwój później | [E-003 · Paczki](./epics/E-003-paczki-startowe/README.md), [E-004 · Nauka](./epics/E-004-rozwoj-nauki/README.md) | Świadomie odłożone tematy i hipotezy |
| Dawne oznaczenia | [Mapa migracji](./epics/migracja.md) | B-*, taski 00–12 i E-01 → nowe pełne ID |
| Start projektu | [README repozytorium](../README.md) | Uruchomienie lokalne, Android i backend |
| Wspólne zasady | [CONTRIBUTING](../CONTRIBUTING.md) | Publikowanie, sekrety, dokumentacja i walidacja |
| Narzędzia | [Katalog skryptów](../scripts/README.md) | Zastosowania i ryzyka |
| Operacje | [Railway CLI](./setup/railway-cli.md) | Bezpieczna diagnostyka, nie aktualny stan deployu |
| Operacje bety | [Alerty, limit AI, odtworzenie](./setup/operacje-beta.md) | Runbook operatora bez sekretów |
| Wydanie Androida | [AAB, podpis, wymuszenie aktualizacji](./setup/wydanie-android.md) | Parametry release i procedura podniesienia minimum |
| Bramki bety | [Internal → closed → rozszerzenie](./setup/beta-bramki.md) | Lista kontrolna i szablon wyniku |
| Lookup | [Zasady wyszukiwania](./reference/lookup-zasady.md) | Utrzymywana referencja |
| Karty | [Schemat wzbogacania](./reference/wzbogacanie-karty-schemat.md) | Kontrakt etapów, historyczne czasy nie są SLA |
| Języki | [Szablon LSP](./reference/lsp-manifest-template.yaml) | Szablon manifestu |
| Prawo | [Projekty dokumentów prawnych](./reference/dokumenty-prawne/README.md) | Projekty ES/PL/EN do przeglądu, niewdrożone jako dokumenty usługi |
| Testy UI | [Maestro E2E](../e2e/README.md) | Uruchomienie i ograniczenia istniejących scenariuszy |
| Przypadki lookup | [Scenariusze](./testing/lookup/README.md) | Dane do świadomego wyboru testów |
| Historia poza epikami | [Archiwum](./archive/README.md) | Dawne audyty i ręczna dystrybucja APK |

## Co gdzie należy

- `epics/`: problem → wartość → rozwiązanie → wykonanie. README epica/feature'a i plik taska prowadzą statusy. `sources/` przy epiku zachowuje datowaną analizę i dowody; nie zastępuje statusu realizacji.
- `setup/`, `reference/`, `testing/`: instrukcje i kontrakty wielokrotnego użytku, utrzymywane z kodem. Nie tworzymy sztucznych epików dla każdej instrukcji.
- `archive/`: migawki dawnych audytów/instrukcji, nie magazyn ukończonych epików.
- Ignorowane `.local/`: ustawienia komputera, surowe logi, eksporty i eksperymenty. Nie są wymaganym źródłem dla współpracowników.

Dokumentacja jest publiczna. `sources/` ani `archive/` nie ukrywają materiałów i nie usuwają historii Git. Test pominięty, sam opis lub istniejący kod nie wystarczają do `done`.
