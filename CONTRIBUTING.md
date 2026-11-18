# Zasady pracy nad Vocabulario

## Jeden kierunek pracy

Tematy produktu prowadzi [rejestr epików](docs/epics/README.md), obecnie priorytet ma [E-001 · Beta Google Play](docs/epics/E-001-google-play-beta/README.md). [Mapa dokumentacji](docs/README.md) rozdziela epiki, instrukcje, referencje i historię.

- Nowy temat opisujemy jako epic z celem biznesowym; dalej features i taski tylko tam, gdzie potrzebny jest podział. Obowiązują [stałe ID i statusy](docs/epics/zasady.md), np. `E-001/F-004/T-001`.
- Zmiana zachowania wymaga aktualizacji bezpośrednio związanej dokumentacji i weryfikacji.
- Zachowane taski 00–12 są teraz w [E-002](docs/epics/E-002-szybka-nauka/README.md); [mapa migracji](docs/epics/migracja.md) wskazuje nowe ID. Nadal opisują kontrakty nauki/importu, nie kolejkę do automatycznego ponowienia.
- Nie robimy przy okazji porządków refaktoryzacji logiki aplikacji, deployu ani napraw produkcyjnej bazy.

## Co publikujemy

| W Git | Poza Git |
|---|---|
| Kod aplikacji, testy i konfiguracja bez sekretów | `.env`, tokeny, prywatne klucze i dane logowania |
| Szablony `.env.example` / `.env.e2e.example` z fikcyjnymi wartościami | Ustawienia konkretnego komputera i prywatne adresy dostępu |
| Aktualne instrukcje, kontrakty i celowo zachowane archiwum | Surowe logi/raporty, eksporty z baz i dane użytkowników |
| Utrzymywane skrypty z jasnym zastosowaniem | Jednorazowe probe/hammer/repair i płatne eksperymenty |
| Małe, potrzebne fixture'y z ustalonym prawem do publikacji | Niepotrzebne decki/importy, APK/AAB, buildy i cache |

Materiały lokalne trzymaj w `.local/`. Dawny ignorowany `doc/` pozostaje zgodny wstecz, ale nie jest drugim miejscem na bieżący backlog. Automatycznie generowane pliki należy umieszczać w istniejących ignorowanych katalogach wyników.

Przejściowy wyjątek: współdzielony `android/keystore/debug.keystore` pozostaje dla zgodności obecnych APK. Jest celowo udostępnionym kluczem debug, **nie zabezpieczeniem produkcyjnego wydania**. Rozdzielenie od produkcyjnego podpisu należy do [E-001/F-002/T-001](docs/epics/E-001-google-play-beta/features/F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md); innych keystore'ów nie dodajemy do Git.

`.gitignore` nie usuwa już śledzonych plików ani historii. Wyciek prawdziwego sekretu wymaga jego odwołania/rotacji i osobnej decyzji o historii — nie wystarczy przenieść pliku.

## Dokumentacja bez bałaganu

- Każdy epic ma stały folder `docs/epics/E-NNN-slug/`, features wewnątrz `features/F-NNN-slug/`, a opcjonalne taski w `tasks/T-NNN-slug.md`. Numery features i tasków są lokalne w rodzicu; poza nim podajemy pełne ID.
- Zakończenie zmienia status i dowody, nie ścieżkę. Nie przenosimy ukończonych epików do archiwum, nie renumerujemy i nie odzyskujemy numerów.
- Każdy README rodzica indeksuje dzieci. Status w nagłówku i indeksie aktualizujemy razem; priorytet i zależności nie wynikają z numeracji.
- Analizy i dawne plany danego epica są kontekstem w jego `sources/`, nie równoległym backlogiem. Pierwotne ustalenia F-/B-/A- bety zachowują znaczenie.
- Instrukcje środowiska/usług: `docs/setup/`; opis zachowania i szablony: `docs/reference/`; scenariusze: `docs/testing/`.
- `docs/archive/` pozostaje dla historycznych audytów i dawnych instrukcji niezwiązanych z realizacją epica. Obecność specyfikacji lub kodu nie oznacza statusu `done`.
- Gdy przenosisz plik, aktualizuj linki, ścieżki w instrukcjach i indeks. Linki w Markdown powinny być względne wobec dokumentu.
- Nie publikuj raportów z prawdziwymi kontami, identyfikatorami, treścią importów lub wynikami z produkcji. Do testów używaj danych syntetycznych i wydzielonego środowiska.

## Sprawdzenia przed zmianą i przed publikacją

W skonfigurowanym środowisku backendu uruchom bazową kontrolę repo:

```powershell
python scripts\ci_check.py
```

Testy PostgreSQL wymagają osobnej lokalnej bazy `*_test` z `TEST_DATABASE_URL`; fixture wykonuje `TRUNCATE`. Test pominięty nie jest testem zaliczonym. Dodatkowe kontrole Androida i wydania dobieramy według [planu bety](docs/epics/E-001-google-play-beta/sources/analiza-2026-11-17.md#10-macierz-testów-akceptacyjnych).

Zmiana wyłącznie dokumentacji nie wymaga budowania APK. Sprawdź odnośniki i `git diff --check`. Przed commitem przejrzyj także listę dodawanych plików:

```powershell
git status --short
git diff --stat
git diff --cached --stat
git diff --cached --name-status
```

Nie dodawaj plików ignorowanych przez `git add -f`, nie uruchamiaj produkcyjnych skryptów w celu „sprawdzenia” repo. Commit/push, deploy, operacje na produkcji i przepisywanie historii wymagają osobnego uzgodnienia.
