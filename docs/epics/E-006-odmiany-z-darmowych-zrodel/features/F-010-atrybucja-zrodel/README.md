# E-006/F-010 · Atrybucja darmowych źródeł w aplikacji

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Najszersze darmowe źródło (Wiktionary/Kaikki) oraz UniMorph, OpenCorpora i JMdict mają licencje CC BY-SA. Pozwalają one na użycie komercyjne, ale pod warunkami:
- trzeba podać źródło;
- udostępniane dalej dane pochodne muszą mieć tę samą licencję;
- nie wolno dodawać ograniczeń sprzecznych z licencją.

JMdict (EDRDG) ma też dodatkowe warunki, m.in. regularną aktualizację danych. Narzędzia na licencjach MIT, Apache, BSD i GPL wymagają zachowania informacji o licencji.

## Rezultat

- Aplikacja ma stały ekran „Źródła danych” z nazwami źródeł, licencjami i linkami.
- W backendzie jest rejestr źródeł i ich wersji.
- Wykorzystanie każdego źródła ma potwierdzenie prawne lub świadomie zaakceptowane ryzyko.

## Zakres / poza zakresem

**Zakres:**
- konsultacja prawna CC BY-SA dla płatnej aplikacji, w której na jednej karcie są dane ze źródła i treść z AI;
- konsultacja dodatkowych warunków EDRDG;
- ekran źródeł w Androidzie (17 lokalizacji);
- ewentualna informacja w dokumentach prawnych;
- informacje o licencjach narzędzi.

**Poza zakresem:**
- zmiany regulaminu niezwiązane ze źródłami.

## Kryteria akceptacji

1. Każde źródło i narzędzie użyte w [F-004](../F-004-darmowe-zrodla/README.md) ma wpis w rejestrze: nazwa, licencja, link, wersja danych.
2. Ekran „Źródła danych” jest dostępny w aplikacji. Zrzut ekranu jest dowodem.
3. Wynik konsultacji prawnej jest zapisany w dowodach tego featura, bez danych poufnych.
4. Jeśli zmieniają się opublikowane teksty prawne, mają one nowy identyfikator wersji zgodnie z [`legal_docs.py`](../../../../../backend/app/services/legal_docs.py).

## Zależności

- Warunek rozpoczęcia: lista źródeł z [F-004](../F-004-darmowe-zrodla/README.md).
- Warunek wydania: wydanie z danymi ze źródeł nie może się ukazać przed tym featurem.

## Otwarte decyzje

**Konsultacja prawna.** Kto ją prowadzi i jaki jest jej termin? Decyduje właściciel produktu. Bez jej wyniku status pozostaje `draft`.

## Dowody ukończenia

Brak.
