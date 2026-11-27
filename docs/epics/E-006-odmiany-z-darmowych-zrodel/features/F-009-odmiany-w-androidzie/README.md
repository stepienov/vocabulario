# E-006/F-009 · Wyświetlanie odmian wszystkich części mowy w Androidzie

**Status:** `draft` · **Epic:** [E-006](../../README.md).

## Problem

Android czyta wyłącznie odmianę czasownika ([`CardInflection.kt`](../../../../../android/app/src/main/java/com/vocabulario/app/data/CardInflection.kt), [`CardDetailContent.kt`](../../../../../android/app/src/main/java/com/vocabulario/app/ui/card/CardDetailContent.kt), [`FlashcardBackContent.kt`](../../../../../android/app/src/main/java/com/vocabulario/app/ui/card/FlashcardBackContent.kt)). Odmiana rzeczownika, przymiotnika i zaimka, nawet zapisana na karcie, nie zostanie pokazana.

## Rezultat

Widok karty i tył fiszki pokazują odmianę każdej odmiennej części mowy w układzie właściwym dla języka. Przykłady:
- tabela przypadek × liczba dla polskiego rzeczownika;
- odmiana mocna, słaba i mieszana dla niemieckiego przymiotnika;
- poziomy grzeczności dla koreańskiego.

Formy nieregularne są wyróżnione.

## Zakres / poza zakresem

**Zakres:**
- model danych w Androidzie, w tym Room z obecnym JSON treści;
- komponenty tabel;
- etykiety osi ze wszystkimi 17 lokalizacjami;
- stany ładowania i braku odmiany;
- dostępność;
- wsparcie kart bez nowej sekcji, wydanych przed zmianą.

**Poza zakresem:**
- ćwiczenia na odmianę;
- zmiany backendu poza kontraktem pola.

## Kryteria akceptacji

1. Dla syntetycznych kart testowych każdego języka z nową odmianą widok karty i tył fiszki pokazują tabelę. Dowodem są zrzuty ekranu z telefonu lub emulatora.
2. Karta bez sekcji odmiany wygląda tak jak dziś.
3. Testy jednostkowe Androida i lint przechodzą: `:app:testDebugUnitTest :app:lintDebug :app:assembleDebug`.
4. `python scripts/check_ui_strings.py` przechodzi: nowe klucze są we wszystkich 17 lokalizacjach.

## Zależności

- Warunek rozpoczęcia: kształt danych z [F-002](../F-002-siatki-odmian/README.md).
- Warunek integracji: [F-007](../F-007-rzeczowniki-i-przymiotniki/README.md).
- Zgodność wydań: zmiana dotyczy wyłącznie Androida i nie trafia na Railway. Backend musi wysyłać nowe pole przed wydaniem aplikacji albo razem z nim.

## Otwarte decyzje

**Pełna tabela czy wybór form.** Na małym ekranie pokazujemy pełną tabelę czy wybór form najważniejszych dla ucznia? Decyzję łączymy z [F-002](../F-002-siatki-odmian/README.md). Decyduje właściciel produktu na podstawie podglądu.

## Dowody ukończenia

Brak.
