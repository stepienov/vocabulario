# E-002 · Szybkie wyszukiwanie i gotowość do nauki

**Status:** `verification_required` — zachowane historyczne specyfikacje, bez nowej deklaracji wdrożenia.  
**Odbiorca:** użytkownik wyszukujący, dodający i importujący słowa.

## Problem i rezultat biznesowy

Długie żądania, wielokrotne podróże do bazy i brak końca odpytywania opóźniały dojście do nauki. Epic ma zapewnić szybką pierwszą treść, przewidywalne dociąganie i ograniczony koszt sieci/AI, bez osłabienia jakości kart i izolacji danych.

## Features

| Feature | Zakres dawnych tasków | Status |
|---|---|---|
| [F-001 · Fundamenty](./features/F-001-fundamenty/README.md) | 00, 01, 02: testy bazy, lokalizacja API, zapisy w tle | `verification_required` |
| [F-002 · Wyszukiwanie](./features/F-002-wyszukiwanie/README.md) | 04–07: cache, pierwsze słowo, więcej, Room | `verification_required` |
| [F-003 · Skojarzenia](./features/F-003-skojarzenia/README.md) | 08 | `verification_required` |
| [F-004 · Karty](./features/F-004-karty/README.md) | 03, 09, 10, 12: koniec pętli, zapis, gotowość i znaczenia | `verification_required` |
| [F-005 · Import](./features/F-005-import/README.md) | 11 | `verification_required` |

## Miary sukcesu, kontrakty i zamknięcie

- Historyczne cele: cache w ułamku sekundy, pierwsze słowo około 1 s, dociągnięcie i skojarzenia 1–2 s, fiszka około 5 s, zatwierdzenie importu około 10 s, glosy około 1–3 s. To cele dawnych specyfikacji, **nie aktualne SLA ani nowe wyniki**; przed `ready` do nowej pracy ustalić referencyjny build, urządzenie i scenariusz.
- Każdy task ma własne sprawdzalne warunki w sekcji „Sprawdzenie”; wyniki lokalne, PostgreSQL, po deployu i na telefonie są oddzielne.
- `learnable` ≠ `ready`; ćwiczenia wymagają także przykładów. Same glosy z `examples_pending` nie odblokowują ćwiczeń.
- `ready`, `content_is_complete` i `lexical_entries` dopiero po pełnym wzbogaceniu.
- Import: 25 pozycji/job i 25 kart/profil/dobę UTC, bez `import_verify`; następna karta po `learnable` albo zapisie adaptacyjnym.
- Żadnego nieograniczonego pollingu, nieuzasadnionych wywołań LLM ani powrotu voice/STT.

Zamknięcie wymaga potwierdzenia wszystkich przyjętych AC na określonej wersji i zapisania odstępstw. Nie uruchamiamy 13 tasków od początku: najpierw porównanie specyfikacji z kodem i dowodami. Nie zmieniamy produkcji w ramach porządkowania dokumentacji.

## Źródła i zależności

- [Instrukcja realizacji i historyczny graf zależności](./sources/instrukcja-realizacji.md) — zachowane dawne numery 00–12.
- [Decyzje, prompty i pomiary](./sources/optymalizacja-requestow.md) — źródło z listopada 2026, nie bieżący stan produkcji.
- [Mapa starych numerów na pełne ID](../migracja.md#optymalizacja).
- [Schemat wzbogacania](../../reference/wzbogacanie-karty-schemat.md) i [lookup](../../reference/lookup-zasady.md).

Zależności techniczne w treści przeniesionych tasków pozostają niezmienione; stare numery są jednoznacznymi aliasami. Backend i Android mają osobne wydania. E-001 korzysta z tych kontraktów jako kontroli regresji.

**Dowody ukończenia:** nie uzupełniano podczas migracji.
