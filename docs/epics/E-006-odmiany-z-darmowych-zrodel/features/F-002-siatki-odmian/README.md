# E-006/F-002 · Siatki odmian dla odmiennych części mowy w każdym języku

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Manifesty LSP (`backend/app/lsp/<kod>/manifest.yaml`) dobrze opisują tylko czasowniki, a i tam są luki:
- **Rzeczownik:** w [modelu](../../../../../backend/app/lsp/models.py) ma tylko listy `cases`, `numbers` i `genders`.
- **Przymiotnik:** ma tylko flagę `full_declension`, bez stopniowania i bez osi zgody.
- **Zaimki, rodzajniki i liczebniki:** nie mają w manifeście żadnej sekcji.
- **Japoński i koreański:** manifesty wymagają siatki 6 osób, choć te języki nie odmieniają czasownika przez osoby.
- **Koreański i turecki:** przymiotnik ma `full_declension: false`, mimo że koreański przymiotnik odmienia się jak czasownik.
- **Turecki:** rzeczownik nie ma przypadków.

Bez dokładnej listy wymaganych form nie da się sprawdzić, czy odmiana jest pełna ([E-006/F-003](../F-003-kontrola-kompletnosci/README.md)).

## Rezultat

Każdy z 16 kodów L2 ma w manifeście, dla każdej odmiennej części mowy, **jawną listę wymaganych pól**, czyli osie i ich wartości. Przykłady:
- polski rzeczownik: 7 przypadków × 2 liczby;
- niemiecki przymiotnik: odmiana mocna, słaba i mieszana × rodzaj × przypadek, plus stopniowanie.

Części mowy bez odmiany w danym języku są oznaczone jawnie jako nieodmienne.

## Zakres / poza zakresem

**Zakres:**
- model manifestu i jego walidacja przy starcie;
- siatki dla czasownika, rzeczownika, przymiotnika, zaimka, rodzajnika i liczebnika we wszystkich 16 manifestach;
- poprawki obecnych siatek czasowników: lista w [zestawieniu](../../sources/odmiany-i-zrodla-2026-11-27.md);
- synchronizacja z Androidem przez `scripts/lsp_sync.py`.

**Poza zakresem:**
- pobieranie i generowanie form;
- wyświetlanie w Androidzie.

## Kryteria akceptacji

1. Każdy manifest wczytuje się, a test sprawdza dla każdej pary język × część mowy jedno z dwóch: siatka istnieje albo POS jest jawnie nieodmienny.
2. Siatki są zgodne z tabelą braków w [zestawieniu](../../sources/odmiany-i-zrodla-2026-11-27.md). Każda różnica ma zapisane uzasadnienie.
3. Ja i ko nie mają siatki osobowej; mają osie istotne dla tych języków, np. poziom grzeczności i przeczenie.
4. Kontrola synchronizacji LSP w `python scripts/ci_check.py` przechodzi.

## Zależności

Brak warunku rozpoczęcia. Na tym featurze opierają się [F-003](../F-003-kontrola-kompletnosci/README.md), [F-007](../F-007-rzeczowniki-i-przymiotniki/README.md), [F-008](../F-008-zaimki-rodzajniki-liczebniki/README.md) i [F-009](../F-009-odmiany-w-androidzie/README.md).

## Otwarte decyzje

**Zakres siatki dla ucznia.** Czy pokazujemy pełny paradygmat, czy wybór form najważniejszych dla ucznia? Przykład: czy arabski ma pokazywać wszystkie 13 osób czasownika i liczbę podwójną. Decyduje właściciel produktu dla każdego języka, na podstawie propozycji wykonawcy.

## Dowody ukończenia

Brak.
