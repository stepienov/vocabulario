# Zasady wyników wyszukiwania (lookup)

Wynik może być niepełny, bo „Pokaż więcej” dociąga kolejne wiersze. Nie może zawierać błędu. Każda zasada poniżej ma strażnika w kodzie, bo sam prompt jej nie gwarantuje.

## Kierunek

1. Użytkownik nie mówi, w którym języku pisze. Zapytanie czyta się w obu językach pary.
2. Homograf (droga, ser, para, list, gift, car, cane) zwraca znaczenia z obu języków: `el camino / droga` i `la droga / narkotyk`.
3. Pierwsze są wiersze, które trafiają w zapytanie w 100% po którejkolwiek stronie (hasło lub glosa). Między sobą zachowują kolejność modelu.
4. Wiersze z „Pokaż więcej” doklejają się na końcu listy.

## Hasło (lemma)

5. Hasło jest zawsze w języku nauki. Słowo języka ojczystego nigdy nie jest hasłem, także z rodzajnikiem (`drogi / drogi, kosztowny`, `la kobieta / kobieta`, `el oko / oko` są błędem).
6. Hasło jest formą słownikową, w jakiejkolwiek formie zapytanie zostało wpisane:
   - rzeczownik w liczbie pojedynczej, po hiszpańsku z rodzajnikiem `el`/`la` (wyjątek: pluralia tantum, np. `las gafas`);
   - przymiotnik w rodzaju męskim liczby pojedynczej (`bonito`, nie `la bonita` ani `bonitas`);
   - czasownik w bezokoliczniku (`querer` dla `quiero`).
7. Hiszpański rzeczownik bez rodzajnika (`grande / duży banknot`) odpada.
8. Imię i nazwa własna nie są słówkiem (`la Tania / Tania` odpada). Wyjątek: niemiecki, bo tam rzeczowniki piszemy wielką literą.

## Glosa (gloss)

9. Glosa jest tłumaczeniem w formie słownikowej języka ojczystego: przymiotnik w mianowniku rodzaju męskiego (`drogi`, nie `drogie`/`drodzy`/`drogiego`), czasownik w bezokoliczniku.
10. Glosa nigdy nie jest opisem gramatycznym („dopełniacz/biernik… od »drogi«” odpada).
11. Glosa nie jest kopią hasła, chyba że zapytanie to właśnie to słowo lub jego liczba mnoga (`el hotel / hotel` dla „hotel” i „hoteles” zostaje).

## Odmiana i literówki

12. Najpierw ustala się, do jakiego słowa należy wpisana forma, potem się je tłumaczy. „drogie”, „drodzy”, „drogiego” to przymiotnik drogi, więc `caro / drogi`. „drodze”, „drogę” to rzeczownik droga, więc `el camino / droga`. „costosas” to `costoso`.
13. Literówka o jedną zmianę (przestawienie sąsiednich liter, brakująca, nadmiarowa lub zła litera) w dowolnym z dwóch języków oznacza to słowo (`wdoa` to woda, `samohcód` to samochód, `preros` to perro).
14. Model podaje w polu `word` słowo, które odczytał. Jeśli to słowo różni się od zapytania, każdy wiersz musi je tłumaczyć: `word` jest hasłem albo jedną z glos. Wiersz, który tłumaczy co innego (`rozrodzian / rozrodziany` dla „rodzian”), odpada.
15. Etykieta części mowy złożona z dwóch („adjective/adverb”) przyjmuje pierwszą. Podciąg „verb” nie robi z przysłówka czasownika.

## Znane ograniczenie

- Literówka w słowie, które w obu językach pisze się tak samo („hotle”), zwraca pusty wynik. Poprawiona kopia `el hotel / hotel` wygląda dla kodu tak samo jak błędne `el oko / oko`. Pusty wynik jest niepełny, ale nie fałszywy.

## Jak sprawdzać zmianę

Ręczne zapytania przez prawdziwą ścieżkę serwisu (szkic, potem „Pokaż więcej”), z czystym cache, na formach odmienionych, a nie tylko na formach słownikowych:

- przypadki rzeczownika (drodze, drogę, rzece, książce, kobiecie, mleka);
- rodzaj, liczba i przypadek przymiotnika (drogie, drodzy, drogiego, ładna, tania, czerwone);
- odmiana czasownika (idę, idziesz, poszedł, jestem, mam, quiero, hablo);
- hiszpańska liczba mnoga i rodzaj (drogas, perros, gatos, costosas, cansadas, felices);
- literówki i przestawki w obu językach (kobeita, wdoa, kseiżka, czrewony, preros, gaezta);
- homografy w kilku parach języków (droga, ser, para, pies, list, gift, car, cane).
