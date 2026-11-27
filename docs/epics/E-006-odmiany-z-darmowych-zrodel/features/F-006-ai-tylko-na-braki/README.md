# E-006/F-006 · OpenAI tylko dla słów i form, których nie dało darmowe źródło

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Dziś [prompt odmiany](../../../../../backend/app/lsp/prompts.py) zawsze prosi o cały paradygmat, niezależnie od tego, co już wiadomo.

## Rezultat

Odmiana karty przechodzi stały przebieg:
1. Pobranie formy ze źródła ([F-004](../F-004-darmowe-zrodla/README.md)).
2. Mapowanie na klucze aplikacji ([F-005](../F-005-mapowanie-form/README.md)).
3. Sprawdzenie kompletności ([F-003](../F-003-kontrola-kompletnosci/README.md)).
4. Decyzja na podstawie wyniku sprawdzenia:

| Wynik kontroli | Działanie | Wywołanie AI |
|---|---|---|
| `complete` | zapis do karty i do wspólnej treści | brak |
| `partial` | do OpenAI trafiają gotowe formy jako kontekst i lista brakujących pól; model zwraca tylko te pola; formy ze źródła się nie zmieniają; wynik ponownie przechodzi kontrolę | tylko na braki |
| `missing` (słowo nieznane albo inna część mowy) | pełna odmiana z OpenAI, jak dziś | pełne |
| `not_applicable` | brak sekcji odmiany | brak |

Przy każdej odmianie zapisujemy, które pola pochodzą ze źródła, a które z AI. Ten zapis służy do pomiaru i atrybucji.

## Zakres / poza zakresem

**Zakres:**
- orkiestracja w enrichment;
- prompt „uzupełnij tylko brakujące pola”;
- telemetria liczby wywołań i ich celu (`purpose`) w podziale na wynik kontroli;
- ponowienia przy statusie `partial` po odpowiedzi AI.

**Poza zakresem:**
- zmiana innych wywołań AI karty;
- korekta form ze źródła przez AI.

## Kryteria akceptacji

1. Fałszywy LLM w testach potwierdza, że dla `complete` nie ma wywołania, a dla `partial` prompt zawiera wyłącznie brakujące pola i nie zmienia form ze źródła.
2. Po odpowiedzi AI, która nadal nie uzupełnia wszystkich pól, obowiązuje limit ponowień zgodny z obecnymi zasadami side jobs. Karta nie wpada w pętlę.
3. Telemetria pozwala policzyć odsetek odmian bez AI dla każdej pary język × część mowy. Jest to miara z README epiku.
4. Przebieg zachowuje inwarianty `learnable`/`ready` z [E-002/F-004](../../../E-002-szybka-nauka/features/F-004-karty/README.md) oraz wspólną treść z [E-005/F-001](../../../E-005-wspolna-tresc-kart/features/F-001-wspolna-tresc/README.md).
5. Włączanie działa osobno dla każdego języka, tak by przełączać języki pojedynczo.

## Zależności

Warunek rozpoczęcia: [F-003](../F-003-kontrola-kompletnosci/README.md), [F-004](../F-004-darmowe-zrodla/README.md) i [F-005](../F-005-mapowanie-form/README.md).

## Otwarte decyzje

**Próg odsetka odmian bez AI.** Ustalamy go po pierwszym pomiarze, przed `ready`. Decyduje właściciel produktu.

## Dowody ukończenia

Brak.
