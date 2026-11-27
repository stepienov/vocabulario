# E-006/F-005 · Mapowanie form ze źródeł na klucze aplikacji

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Źródła opisują formy tagami, np. `genitive, singular` albo `formal, past`. Aplikacja używa kluczy z manifestu, np. `dopelniacz/sg` albo `prateritum/ich`. Nie wszystkie formy w źródle są gotowe:
- w hiszpańskim i włoskim brakuje czasów złożonych, np. *he comido*;
- w angielskim jest tylko 5 form podstawowych.

## Rezultat

Dla każdego języka istnieje mapowanie tagów źródła na pola siatki z [F-002](../F-002-siatki-odmian/README.md). Brakujące formy złożone są tworzone regułą z czasownika posiłkowego i imiesłowu, bez AI. Wynik przechodzi przez [F-003](../F-003-kontrola-kompletnosci/README.md).

## Zakres / poza zakresem

**Zakres:**
- mapowanie tagów dla 14 odmiennych języków;
- reguły form złożonych;
- wybór wariantu, np. vosotros, BR/PT;
- odrzucanie form archaicznych i dialektalnych, jeśli siatka ich nie zawiera.

**Poza zakresem:**
- formy, których nie ma w źródle i których nie da się złożyć regułą — należą do [F-006](../F-006-ai-tylko-na-braki/README.md).

## Kryteria akceptacji

1. Dla listy testowej z [F-004](../F-004-darmowe-zrodla/README.md) testy porównują wynik mapowania z oczekiwanymi formami. Wzorzec oczekiwanych form przygotowuje się ręcznie dla każdego języka i części mowy.
2. Hiszpańskie *comer* i angielskie *go* dają status `complete` bez AI: czasy złożone wynikają z reguł.
3. Każdy nierozpoznany tag źródła jest logowany w zestawieniu do przeglądu i nie trafia do karty.

## Zależności

- Warunek rozpoczęcia: [F-002](../F-002-siatki-odmian/README.md).
- Warunek integracji: [F-003](../F-003-kontrola-kompletnosci/README.md) i [F-004](../F-004-darmowe-zrodla/README.md).

## Otwarte decyzje

Brak.

## Dowody ukończenia

Brak.
