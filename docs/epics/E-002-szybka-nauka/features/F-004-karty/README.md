# F-004 · Szybki zapis i etapowa gotowość kart

**ID:** `E-002/F-004` · **Status:** `verification_required` · **Epic:** [E-002](../../README.md).

**Wartość:** zapis szybko wraca do użytkownika, znaczenia pojawiają się wcześnie, a ćwiczenie zaczyna się dopiero po przygotowaniu przykładów.

| Pełne ID | Task | Alias | Status |
|---|---|---|---|
| E-002/F-004/T-001 | [Koniec pętli learnable](./tasks/T-001-petla-learnable.md) | 03 | `verification_required` |
| E-002/F-004/T-002 | [Lekki zapis](./tasks/T-002-lekki-zapis.md) | 09 | `verification_required` |
| E-002/F-004/T-003 | [Nauka i powiązane osobno](./tasks/T-003-nauka-i-powiazane.md) | 10 | `verification_required` |
| E-002/F-004/T-004 | [Wcześniejsze znaczenia](./tasks/T-004-wczesniejsze-znaczenia.md) | 12 | `verification_required` |

**Zależności:** testy bazy i zapisy w tle z F-001; lekki zapis po końcu pętli i odpowiednich zmianach telefonu F-002/T-004; podział nauki po lekkim zapisie; znaczenia po podziale nauki. Rozróżnienie zależności kodu/wdrożenia z oryginalnych tasków zachowane.

## Akceptacja i granice

- Brak nieskończonego odpytywania i ponowień; brakująca odmiana „nie dotyczy” ma wynik końcowy.
- `examples_pending` pozwala oglądać glosy, ale status pozostaje `pending`/`preparing` do study finish.
- Ćwiczenie wymaga `learnable` i przykładów; `ready`/`content_is_complete`/`lexical_entries` nie są przyspieszane.
- Testy zapisów częściowych, wyścigów i scalania nie gubią gotowych fragmentów; weryfikacja według tasków.

Poza zakresem: uproszczenie modelu do jednego „gotowe”, przywrócenie pollingu i zmiana importu przy okazji.

**Źródła / dowody:** [schemat karty](../../../../reference/wzbogacanie-karty-schemat.md), [prompty i decyzje](../../sources/optymalizacja-requestow.md). Szczególnie dawne taski 10/12 pozostają kontraktami; brak nowego potwierdzenia testów/wdrożenia.
