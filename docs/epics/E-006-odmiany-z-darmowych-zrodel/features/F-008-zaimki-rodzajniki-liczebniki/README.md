# E-006/F-008 · Odmiana zaimków, rodzajników i liczebników

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Zaimki (`pron`) i rodzajniki/określniki (`det`) są rozpoznawane jako części mowy, ale nie mają odmiany. Przykłady form, których dziś brakuje:
- ja/mnie/mi/mną, он/его/ему, er/ihn/ihm;
- der/die/das, il/lo/la/gli.

Liczebniki nie mają nawet własnej kanonicznej części mowy ([`pos_normalize.py`](../../../../../backend/app/services/pos_normalize.py)), a w polskim i rosyjskim odmieniają się przez przypadki, np. dwa/dwóch/dwoma.

## Rezultat

Zaimek, rodzajnik/określnik i liczebnik mają odmianę wszędzie tam, gdzie siatka z [F-002](../F-002-siatki-odmian/README.md) ją przewiduje.

## Zakres / poza zakresem

**Zakres:**
- `pron` i `det` w językach z odmianą;
- decyzja i ewentualne dodanie liczebnika jako części mowy w backendzie i w Androidzie;
- przebieg z [F-006](../F-006-ai-tylko-na-braki/README.md).

**Poza zakresem:**
- stopniowanie przysłówków (osobna decyzja);
- formy łączne przyimka z rodzajnikiem, np. do/na, du/au, jako osobne karty.

## Kryteria akceptacji

1. Dla listy testowej zaimków i rodzajników w każdym języku z ich odmianą status kompletności to `complete`.
2. Jeśli liczebnik zostanie dodany, rozpoznają go normalizacja części mowy w backendzie, import i Android, a kontrola UI strings przechodzi dla wszystkich 17 lokalizacji.

## Zależności

Warunek rozpoczęcia: [F-007](../F-007-rzeczowniki-i-przymiotniki/README.md).

## Otwarte decyzje

- **Liczebnik.** Czy dodajemy liczebnik jako nową część mowy? Decyduje właściciel produktu.
- **Stopniowanie przysłówków.** Czy wchodzi w zakres? Decyduje właściciel produktu.

## Dowody ukończenia

Brak.
