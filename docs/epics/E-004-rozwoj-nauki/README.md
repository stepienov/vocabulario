# E-004 · Skuteczność nauki i rozwój produktu

**Status:** `parked` — uporządkowane hipotezy, nie zatwierdzony zakres wdrożenia.  
**Odbiorca:** osoba ucząca się regularnie i powracająca po przerwie.  
**Horyzont:** po stabilizacji bety, bez dokładania nowych funkcji do E-001.

## Problem i cel biznesowy

Bogata karta i SRS mają prowadzić do trwałego zapamiętania i używania słów, a nie tylko odhaczania ćwiczeń. Chcemy zmniejszyć porzucanie po przerwie oraz sprawdzić, które ćwiczenia kontekstowe dają rzeczywistą wartość przy kontrolowanym koszcie.

## Hipotezy pogrupowane w features

| Feature | Problem / hipoteza | Status |
|---|---|---|
| [F-001 · Regularność](./features/F-001-regularnosc/README.md) | Powrót bez przytłaczającej kolejki, przewidywalne obciążenie i wyjaśnienie SRS | `parked` |
| [F-002 · Zaufanie do treści](./features/F-002-zaufanie-do-tresci/README.md) | Uczeń nie utrwala błędów; może zgłosić problem i rozumie gotowość karty | `parked` |
| [F-003 · Kontekst słów](./features/F-003-kontekst/README.md) | Tekst ze słów ucznia pomaga przenieść pamięć fiszki na użycie | `parked` |
| [F-004 · Aktywne użycie](./features/F-004-aktywne-uzycie/README.md) | Odtwarzanie fraz, odmiany i zdań uzupełnia odtwarzanie samego hasła | `parked` |
| [F-005 · Samodzielność](./features/F-005-samodzielnosc/README.md) | Cel, samoocena i powiązania pomagają wybrać skuteczną strategię nauki | `parked` |

To podział [analizy z 23.08.2026](./sources/analiza-pedagogiczna-produktowa.md), nie potwierdzenie braków w dzisiejszym kodzie. [Wizualizacja źródłowa](./sources/pedagogy-product-gap.canvas.tsx) też przedstawia historyczne hipotezy.

## Miary i decyzje przed realizacją

Przed `ready` porównać hipotezy z aktualną aplikacją, zebrać bazowy odsetek ukończenia dziennych powtórek i powrotu po przerwie, dobrać ocenę odroczonego przypomnienia/użycia słów i budżet AI. Wtedy zatwierdzić progi i pojedynczy wycinek; nie deklarujemy dziś poprawy bez badania.

Tasków jeszcze nie ma: warianty, miary i zakres wymagają discovery. Gdy temat stanie się odrębnym przedsięwzięciem, można utworzyć powiązany epic z kolejnym numerem i wskazać, że przejmuje zakres; istniejących ID nie przenumerowujemy.

## Zależności i ograniczenia

- Ochrona danych i samodzielna obsługa konta z [E-001](../E-001-google-play-beta/README.md) są wcześniejszym priorytetem.
- Obowiązują kontrakty gotowości i kosztów [E-002](../E-002-szybka-nauka/README.md). Podgląd glos nie jest jeszcze ćwiczeniem.
- Paczki startowe mają własnego właściciela: [E-003](../E-003-paczki-startowe/README.md), bez dublowania feature'a.
- Historyczne propozycje mówienia/voice/STT **nie są przywracane ani rekomendowane do realizacji**. Zachowanie źródła nie zmienia tej decyzji.
- Płatności, inne platformy, panel nauczyciela, gamifikacja i marketplace są poza zakresem tych features. Dawna tabela monetyzacji to hipoteza, nie polityka cenowa.
- Historie dopiero po jakości treści i opanowaniu obciążenia powtórkami; nie generujemy nowej pracy dla osoby z zaległościami.

**Zamknięcie / dowody:** po wyborze zakresu, ustaleniu progów i pomiarze efektu edukacyjnego; obecnie brak.
