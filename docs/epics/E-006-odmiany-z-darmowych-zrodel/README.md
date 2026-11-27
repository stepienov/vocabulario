# E-006 · Odmiany z darmowych źródeł

**Status:** `draft` · **Priorytet:** do decyzji · **Odbiorca:** każdy użytkownik uczący się słów; właściciel produktu (koszt AI).

## Problem i rezultat

Odmiana słowa to największa pojedyncza pozycja kosztu AI przy tworzeniu karty. Każda odmiana pochodzi z płatnego zapytania `inflection`, chociaż dla popularnych słów te same formy są bezpłatnie dostępne w otwartych słownikach.

Część zapytań nie daje żadnego wyniku:
- **Rzeczowniki i przymiotniki** trafiają do modelu, ale prompt opisuje tylko czasowniki i każe zwrócić dla nich `null`.
- **Chiński i wietnamski** dostają „odmianę czasownika”, której te języki nie mają.

Aplikacja odmienia **wyłącznie czasowniki**. W 13 z 16 języków nauki odmieniają się też rzeczowniki, przymiotniki, zaimki lub rodzajniki. Manifesty LSP deklarują ich przypadki, liczby i rodzaje, ale nic tych danych nie generuje, nie sprawdza ani nie wyświetla.

**Rezultat:**
1. Odmiana pochodzi najpierw z darmowego źródła. OpenAI uzupełnia tylko te formy, których źródło nie dało, oraz słowa, których źródło nie zna.
2. Karta pokazuje odmianę wszystkich części mowy, które w danym języku się odmieniają.
3. Aplikacja nie płaci za zapytania, które z góry nie mogą dać wyniku.

Stan wyjściowy, braki dla każdego języka i sprawdzone źródła: [zestawienie z 27 XI 2026](./sources/odmiany-i-zrodla-2026-11-27.md).

## Features

| ID | Rezultat | Status |
|---|---|---|
| E-006/F-001 | [Koniec płatnych zapytań o odmianę bez wyniku](./features/F-001-bez-platnych-pustych-odmian/README.md) | `draft` |
| E-006/F-002 | [Siatki odmian dla odmiennych części mowy w każdym języku](./features/F-002-siatki-odmian/README.md) | `draft` |
| E-006/F-003 | [Sprawdzanie, których form brakuje w odmianie](./features/F-003-kontrola-kompletnosci/README.md) | `draft` |
| E-006/F-004 | [Darmowe źródła odmian jako pierwszy krok](./features/F-004-darmowe-zrodla/README.md) | `draft` |
| E-006/F-005 | [Mapowanie form ze źródeł na klucze aplikacji](./features/F-005-mapowanie-form/README.md) | `draft` |
| E-006/F-006 | [OpenAI tylko dla słów i form, których nie dało darmowe źródło](./features/F-006-ai-tylko-na-braki/README.md) | `draft` |
| E-006/F-007 | [Odmiana rzeczowników i przymiotników](./features/F-007-rzeczowniki-i-przymiotniki/README.md) | `draft` |
| E-006/F-008 | [Odmiana zaimków, rodzajników i liczebników](./features/F-008-zaimki-rodzajniki-liczebniki/README.md) | `draft` |
| E-006/F-009 | [Wyświetlanie odmian wszystkich części mowy w Androidzie](./features/F-009-odmiany-w-androidzie/README.md) | `draft` |
| E-006/F-010 | [Atrybucja darmowych źródeł w aplikacji](./features/F-010-atrybucja-zrodel/README.md) | `draft` |

Kolejność pracy wynika z zależności, nie z numerów featurów:
- F-001 nie zależy od innych featurów.
- F-002 → F-003 → F-004 i F-005 → F-006.
- F-007 wymaga F-002, F-003 i F-006.
- F-008 wymaga F-007.
- F-009 wymaga F-002 na start i F-007 do integracji.
- F-010 musi być gotowy przed pierwszym wydaniem z danymi ze źródeł F-004.

## Miary sukcesu

- **Brak zapytań bez wyniku:** zero płatnych wywołań `inflection` dla zh/vi i dla części mowy bez zdefiniowanej siatki (F-001).
- **Odmiana bez AI:** odsetek odmian zapisanych bez wywołania AI, liczony dla każdej pary język × część mowy. Próg ustalamy po pierwszym pomiarze na syntetycznej liście popularnych słów, przed statusem `ready` dla F-006.
- **Koszt odmiany na kartę:** pomiar przed zmianą i po niej w porównywalnym środowisku. Ta miara nie ma progu, bo darmowe źródło używamy niezależnie od skali oszczędności (decyzja z 27 XI 2026).
- **Bez regresji jakości:** odmiany czasowników z darmowego źródła nie mogą być gorsze niż obecne z AI. Przed włączeniem każdego języka ręcznie sprawdzamy próbkę słów.

## Zakres i poza zakresem

**W zakresie:**
- odmiana wszystkich odmiennych części mowy w 16 kodach L2;
- darmowe źródła przechowywane po stronie backendu;
- sprawdzanie kompletności i uzupełnianie braków przez AI;
- zapis odmiany we wspólnej treści karty;
- wyświetlanie w Androidzie;
- atrybucja i licencje.

**Poza zakresem:**
- znaczenia, przykłady, słowa powiązane i dystraktory — nadal z AI;
- płatne słowniki i płatne API;
- przywracanie wyszukiwania głosowego;
- zmiana zasad nauki;
- migracja historycznych kart bez osobnej decyzji.

## Decyzje

- **27 XI 2026:** darmowe źródło jest pierwszym krokiem nawet wtedy, gdy obejmuje tylko część słownictwa. Nie liczymy opłacalności przed rozpoczęciem prac.
- **27 XI 2026:** OpenAI dostaje listę brakujących form, a nie prośbę o cały paradygmat od nowa.

## Zależności, inwarianty i ryzyka

**Obowiązujące kontrakty:**
- **`learnable` ≠ `ready`** ([E-002/F-004](../E-002-szybka-nauka/features/F-004-karty/README.md)). Odmiana należy do pełnej treści karty. Darmowe źródło nie może przyspieszyć `ready`, `content_is_complete` ani zapisu do `lexical_entries` przed pełnym wzbogaceniem karty.
- **Jedna wspólna treść dla tej samej pary języków** ([E-005/F-001](../E-005-wspolna-tresc-kart/features/F-001-wspolna-tresc/README.md)). Odmiana ze źródła trafia do wspólnego wpisu i jest identyczna dla wszystkich użytkowników.
- **Tłumaczenia interfejsu:** każdy nowy tekst w UI musi mieć wersje we wszystkich 17 lokalizacjach.

**Ryzyka:**
- licencje CC BY-SA i dodatkowe warunki EDRDG wymagają konsultacji prawnej (F-010);
- portugalski BR i PT mają w większości źródeł wspólne dane;
- homografy różnych części mowy, np. arabskie كتب („pisał” i „książki”);
- jakość danych społecznościowych.

## Kryterium zamknięcia

Wszystkie features są `done`, a dowody obejmują:
- testy backendu dla każdego języka;
- pomiar odsetka odmian bez AI;
- porównanie kosztu przed zmianą i po niej;
- zrzuty ekranu odmian w Androidzie;
- zatwierdzoną atrybucję.

Dowody ukończenia: brak.
