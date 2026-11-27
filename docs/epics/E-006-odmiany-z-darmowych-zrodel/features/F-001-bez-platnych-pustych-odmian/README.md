# E-006/F-001 · Koniec płatnych zapytań o odmianę bez wyniku

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Backend wysyła płatne zapytanie `inflection` w dwóch sytuacjach, w których nie może ono dać użytecznego wyniku:

1. **Rzeczownik i przymiotnik we wszystkich 16 językach.**
   - [`inflect_pos_key`](../../../../../backend/app/lsp/enrichment.py) kieruje rzeczownik i przymiotnik do odmiany.
   - [Prompt](../../../../../backend/app/lsp/prompts.py) opisuje tylko czasowniki i każe zwrócić `nouns: null` oraz `adjectives: null`.
   - Wtedy [`has_required_inflection`](../../../../../backend/app/lsp/enrichment.py) zwraca fałsz. Karta nie przechodzi do stanu complete, więc ponowienia znów wywołują model.
   - Android i tak nie wyświetla odmiany rzeczownika ani przymiotnika ([`CardInflection.kt`](../../../../../android/app/src/main/java/com/vocabulario/app/data/CardInflection.kt)).
2. **Czasownik w chińskim (zh) i wietnamskim (vi).** Te języki nie odmieniają czasowników. Manifesty deklarują jednak czasy, więc model zwraca w zasadzie tę samą formę, czasem z partykułą.

## Rezultat

- **Rzeczownik i przymiotnik:** status odmiany to `not_applicable` i AI nie jest wywoływane. Karta może dojść do stanu complete bez ponowień. To rozwiązanie tymczasowe, które zastąpi prawdziwa odmiana z [E-006/F-007](../F-007-rzeczowniki-i-przymiotniki/README.md).
- **Czasownik zh/vi:** status odmiany to `not_applicable` na stałe i AI nie jest wywoływane.
- **Pozostałe języki i czasowniki:** bez zmian.

## Zakres / poza zakresem

**Zakres:**
- przypisanie POS do odmiany: tylko czasowniki z języków, które je odmieniają;
- warunek pełnej karty;
- ponowienia side jobs;
- testy backendu.

**Poza zakresem:**
- prawdziwa odmiana rzeczownika i przymiotnika — należy do [E-006/F-007](../F-007-rzeczowniki-i-przymiotniki/README.md);
- zmiany w Androidzie;
- przeliczanie historycznych kart.

## Kryteria akceptacji

1. Dla rzeczownika i przymiotnika w każdym z 16 języków przygotowanie karty nie wywołuje `inflection`. W teście sprawdza to fałszywy LLM z licznikiem wywołań.
2. Dla czasownika zh/vi nie ma wywołania `inflection`, a karta dochodzi do stanu complete.
3. Dla czasownika w pozostałych 14 kodach L2 jest dokładnie jedno wywołanie `inflection`, jak dotąd.
4. Karta rzeczownika lub przymiotnika z kompletem pozostałych danych przechodzi `content_is_complete` i nie zostaje zaplanowana do ponowienia odmiany.
5. Zmiana nie przesuwa momentu `learnable` ani `ready` przed pełnym wzbogaceniem karty: znaczenia, przykłady, słowa powiązane i podobne nadal są wymagane.
6. `python scripts/ci_check.py` przechodzi.

## Zależności

Brak zależności od innych featurów. Obowiązują inwarianty z [E-002/F-004](../../../E-002-szybka-nauka/features/F-004-karty/README.md).

## Otwarte decyzje

- **Czasownik zh/vi.** W kartach czasowników zh/vi zniknie sekcja „odmiana”. Czy informację o partykułach aspektu (了/着/过 w zh, đã/đang/sẽ w vi) przenieść do notatki gramatycznej karty, czy pominąć? Decyduje właściciel produktu. Do czasu decyzji status pozostaje `draft`.
- **Istniejące karty.** Czy karty rzeczowników i przymiotników zatrzymane dziś przed stanem complete przez brak odmiany mają zostać domknięte jednorazowo? Decyduje właściciel produktu.

## Dowody ukończenia

Brak.
