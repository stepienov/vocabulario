# F-002 · Szybkie i oszczędne wyszukiwanie

**ID:** `E-002/F-002` · **Status:** `verification_required` · **Epic:** [E-002](../../README.md).

**Wartość:** użytkownik szybko widzi pierwszą propozycję i przynależność do biblioteki, bez dodatkowych żądań dla każdego kafelka.

| Pełne ID | Task | Alias | Status |
|---|---|---|---|
| E-002/F-002/T-001 | [Cache](./tasks/T-001-cache.md) | 04 | `verification_required` |
| E-002/F-002/T-002 | [Pierwsze słowo](./tasks/T-002-pierwsze-slowo.md) | 05 | `verification_required` |
| E-002/F-002/T-003 | [Więcej propozycji](./tasks/T-003-wiecej-propozycji.md) | 06 | `verification_required` |
| E-002/F-002/T-004 | [Zestawienie z Room](./tasks/T-004-room.md) | 07 | `verification_required` |

**Zależności:** E-002/F-001/T-003 dla serwera, kolejne kroki cache → pierwsze słowo → dociągnięcie; telefon po kontrakcie tych odpowiedzi i E-002/F-004/T-001. Szczegóły w źródłowych sekcjach zależności.

**Akceptacja:** zachowany kontrakt lemma/gloss/exact, jedno żądanie szukania po stronie telefonu, przynależność z Room bez N+1, zgodność starszego klienta. Historyczne cele czasu nie są nowym wynikiem pomiaru; weryfikacja według sekcji „Sprawdzenie” każdego taska.

**Poza zakresem:** voice/STT, zmiana semantyki gotowości karty, nowe tryby szukania.

**Źródła / dowody:** [pomiary](../../sources/optymalizacja-requestow.md), [zasady lookup](../../../../reference/lookup-zasady.md). Brak nowej weryfikacji podczas migracji.
