# E-006/F-003 · Sprawdzanie, których form brakuje w odmianie

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Dziś odmiana liczy się jako gotowa, gdy cokolwiek w niej jest niepuste ([`has_required_inflection`](../../../../../backend/app/lsp/enrichment.py)). Walidacja nie sprawdza, czy są wszystkie formy:
- dla czasowników usuwa tylko placeholdery i zostawia nieznane klucze ([`conjugation.py`](../../../../../backend/app/ai/conjugation.py));
- dla rzeczowników i przymiotników nie istnieje ([`validate.py`](../../../../../backend/app/lsp/validate.py), `TODO`).

Przez to nie da się odróżnić odmiany pełnej od niepełnej. Do zapytania o same braki ([F-006](../F-006-ai-tylko-na-braki/README.md)) potrzebna jest dokładna lista brakujących pól.

## Rezultat

Jedna funkcja porównuje odmianę z siatką z [F-002](../F-002-siatki-odmian/README.md) i zwraca:
- status: `complete`, `partial`, `missing` albo `not_applicable` (język lub część mowy bez odmiany, np. chiński czasownik; zob. F-001 i F-006);
- listę brakujących pól;
- listę pól niezgodnych z siatką, czyli nieznanych kluczy.

Z tej funkcji korzystają warunek pełnej karty, ponowienia i [F-006](../F-006-ai-tylko-na-braki/README.md).

## Zakres / poza zakresem

**Zakres:**
- walidator dla wszystkich odmiennych części mowy;
- usuwanie kluczy spoza siatki;
- podpięcie walidatora do `has_required_inflection` i `content_is_complete`;
- testy jednostkowe.

**Poza zakresem:**
- pozyskiwanie form;
- ocena poprawności językowej samej formy, np. literówki.

## Kryteria akceptacji

1. Dla każdej siatki z F-002 testy obejmują trzy przypadki: komplet daje `complete`, brak jednego pola daje `partial` z dokładną listą brakujących pól, pusty wynik daje `missing`.
2. Nieznane klucze, np. `{"bogus": ...}` albo wymyślony czas, są odrzucane i nie liczą się do kompletności.
3. Karta jest „complete” tylko przy statusie odmiany `complete` lub `not_applicable`.
4. Istniejące, kompletne odmiany czasowników z obecnych testów nadal przechodzą.

## Zależności

Warunek rozpoczęcia: [E-006/F-002](../F-002-siatki-odmian/README.md).

## Otwarte decyzje

**Brakujące formy, które nie istnieją.** Formy brakujące w samym języku, np. czasowniki defektywne albo rzeczowniki tylko w liczbie mnogiej, muszą mieć jawne oznaczenie „brak formy”. Inaczej zawsze trafiałyby do AI. Wykonawca proponuje format.

## Dowody ukończenia

Brak.
