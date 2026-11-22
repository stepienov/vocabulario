# F-001 · Fundamenty wydajności i wiarygodnych testów

**ID:** `E-002/F-001` · **Status:** `verification_required` · **Epic:** [E-002](../../README.md).

**Wartość:** każde żądanie nie czeka niepotrzebnie na odległą bazę i zapisy pomocnicze, a zmiany współbieżności da się sprawdzić.

| Pełne ID | Task | Alias | Status |
|---|---|---|---|
| E-002/F-001/T-001 | [Testy PostgreSQL](./tasks/T-001-testy-postgresql.md) | 00 | `verification_required` |
| E-002/F-001/T-002 | [Region i replika API](./tasks/T-002-region-api-i-bazy.md) | 01 | `verification_required` |
| E-002/F-001/T-003 | [Zapisy pomocnicze w tle](./tasks/T-003-zapisy-w-tle.md) | 02 | `verification_required` |

**Zakres / zależności:** testy bazy i konfiguracja infrastruktury niezależne; zapisy w tle po testach bazy, porównanie czasów po ustaleniu konfiguracji API. Zależności i zgody operacyjne z oryginalnych tasków pozostają wiążące.

**Akceptacja:** izolowany PostgreSQL faktycznie testuje zachowania transakcyjne; metryki/logi nie blokują odpowiedzi, ale ich błędy są raportowane; wyniki porównujemy na tym samym środowisku. Dokładne warunki i testy w taskach.

**Poza zakresem:** deploy/zmiana regionu bez osobnego zlecenia, automatyczna ingerencja w produkcję.

**Źródła i dowody:** [decyzje i pomiary](../../sources/optymalizacja-requestow.md), [instrukcja](../../sources/instrukcja-realizacji.md). Aktualnych dowodów nie dopisywano podczas migracji.
