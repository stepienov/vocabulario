# E-006/F-004 · Darmowe źródła odmian jako pierwszy krok

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Każda odmiana pochodzi dziś z płatnego zapytania. W otwartych słownikach jest za darmo dostępna i opisana gramatycznie dla popularnych słów w 13 odmiennych językach nauki. Pomiar na pojedynczych słowach jest w [zestawieniu](../../sources/odmiany-i-zrodla-2026-11-27.md). Przykład z tego pomiaru: Kaikki ma dla polskiego „kot” 20 form, a dla tureckiego „gelmek” 941.

## Rezultat

- Backend ma własną, aktualizowaną kopię darmowych danych odmian.
- Wyszukiwanie odbywa się po języku, lemacie i części mowy, bez zależności od zewnętrznego serwera w momencie tworzenia karty.
- Dla każdego języka jest wybrane źródło główne i ewentualne źródło dodatkowe.

## Zakres / poza zakresem

**Zakres:**
- import danych Wiktionary/Kaikki (JSONL) dla 13 języków;
- dla wybranych języków narzędzia specyficzne:
  - polski: Morfeusz 2/SGJP;
  - rosyjski: pymorphy3;
  - angielski: LemmInflect;
  - języki romańskie: mlconjug3 lub verbecc;
  - portugalski: MorphoBr;
  - japoński: JMdict z regułami koniugacji;
- model przechowywania i indeksy;
- cykliczna aktualizacja danych;
- przy wielu wpisach o tej samej pisowni wybór wpisu według części mowy;
- zapis źródła i wersji danych przy każdej odmianie.

**Poza zakresem:**
- mapowanie tagów źródła na klucze aplikacji — należy do [F-005](../F-005-mapowanie-form/README.md);
- znaczenia, tłumaczenia i przykłady ze źródeł;
- źródła płatne;
- odpytywanie zewnętrznego API przy każdej karcie.

## Kryteria akceptacji

1. Dla syntetycznej listy popularnych słów, ustalonej przed `ready` i obejmującej każdy język i każdą odmienną część mowy, wyszukiwanie zwraca wpis albo jawny brak.
2. Słowo o kilku częściach mowy, np. arabskie كتب, zwraca tylko wpis o żądanej części mowy.
3. Aktualizacja danych nie zmienia bez wiedzy użytkowników form już zapisanych we wspólnej treści kart. Zasadę takich zmian ustalamy z [E-005/F-001](../../../E-005-wspolna-tresc-kart/features/F-001-wspolna-tresc/README.md).
4. Dane i narzędzia mają licencję dopuszczającą użycie komercyjne, potwierdzoną w [F-010](../F-010-atrybucja-zrodel/README.md).
5. Rozmiar danych, czas wyszukiwania i czas aktualizacji są zmierzone na środowisku zbliżonym do produkcji.

## Zależności

- Warunek rozpoczęcia: brak.
- Warunek integracji: [F-005](../F-005-mapowanie-form/README.md).
- Warunek wydania: [F-010](../F-010-atrybucja-zrodel/README.md).

## Otwarte decyzje

- **Przechowywanie danych.** Gdzie trzymać dane (PostgreSQL czy pliki przy backendzie) i jaki jest dopuszczalny rozmiar w Railway? Wykonawca proponuje, właściciel akceptuje koszt infrastruktury.
- **Portugalski BR/PT.** Większość źródeł nie rozdziela wariantów. Formy niezgodne z wariantem trafiają do AI jako braki.

## Dowody ukończenia

Brak.
