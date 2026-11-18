# Mapa migracji dokumentacji

Jednorazowa mapa tożsamości, nie drugi backlog. Statusy są w dokumentach i indeksach rodziców. Starsze numery w źródłach pozostają aliasami, więc dawnych decyzji, promptów i zależności nie trzeba interpretować od nowa.

## Beta

`docs/plan-beta-google-play.md` → [źródłowa analiza E-001](./E-001-google-play-beta/README.md). Nowy punkt wejścia: [E-001](./E-001-google-play-beta/README.md).

| Dawne ID | Pełne ID i aktualny task |
|---|---|
| B-00 | [E-001/F-001/T-001 · Decyzje](./E-001-google-play-beta/features/F-001-prowadzenie-bety/tasks/T-001-decyzje-i-zakres.md) |
| B-01 | [E-001/F-002/T-001 · Release](./E-001-google-play-beta/features/F-002-wydanie-play/tasks/T-001-release-i-aktualizacja.md) |
| B-02 | [E-001/F-003/T-001 · Sesje backendu](./E-001-google-play-beta/features/F-003-sesja-i-offline/tasks/T-001-sesje-backendu.md) |
| B-03 | [E-001/F-003/T-002 · Sesja Androida](./E-001-google-play-beta/features/F-003-sesja-i-offline/tasks/T-002-sesja-androida.md) |
| B-04 | [E-001/F-004/T-001 · Hasła](./E-001-google-play-beta/features/F-004-email-i-hasla/tasks/T-001-haszowanie-hasel.md) |
| B-05 | [E-001/F-004/T-002 · Poczta](./E-001-google-play-beta/features/F-004-email-i-hasla/tasks/T-002-poczta-i-odzyskiwanie.md) |
| B-06 | [E-001/F-005/T-001 · Google](./E-001-google-play-beta/features/F-005-google/tasks/T-001-google-i-laczenie.md) |
| B-07 | [E-001/F-006/T-001 · Moje konto](./E-001-google-play-beta/features/F-006-zarzadzanie-kontem/tasks/T-001-moje-konto.md) |
| B-08 | [E-001/F-006/T-002 · Usuwanie](./E-001-google-play-beta/features/F-006-zarzadzanie-kontem/tasks/T-002-usuwanie-konta.md) |
| B-09a | [E-001/F-003/T-003 · Wynik sync](./E-001-google-play-beta/features/F-003-sesja-i-offline/tasks/T-003-wynik-synchronizacji.md) |
| B-09b | [E-001/F-003/T-004 · Kolejka/profil](./E-001-google-play-beta/features/F-003-sesja-i-offline/tasks/T-004-kolejka-i-profil.md) |
| B-10 | [E-001/F-004/T-003 · Odporność auth](./E-001-google-play-beta/features/F-004-email-i-hasla/tasks/T-003-odpornosc-auth.md) |
| B-11 | [E-001/F-007/T-001 · Prywatność](./E-001-google-play-beta/features/F-007-prywatnosc-i-wsparcie/tasks/T-001-prywatnosc-i-deklaracje.md) |
| B-12 | [E-001/F-007/T-002 · Wsparcie](./E-001-google-play-beta/features/F-007-prywatnosc-i-wsparcie/tasks/T-002-wsparcie-i-dostepnosc.md) |
| B-13 | [E-001/F-008/T-001 · Jakość](./E-001-google-play-beta/features/F-008-jakosc-i-operacje/tasks/T-001-bramki-jakosci.md) |
| B-14 | [E-001/F-001/T-002 · Uruchomienie](./E-001-google-play-beta/features/F-001-prowadzenie-bety/tasks/T-002-uruchomienie-bety.md) |

Ustalenia audytu **F-01…F-16** i scenariusze **A-01…A-24** pozostają w analizie z oryginalnym znaczeniem. Nie są nowymi ID features; nowe mają trzycyfrowy numer i rodzica.

## Optymalizacja

Dawne `docs/taski/` i plan `docs/optymalizacja-requestow.md` (następnie `docs/archive/performance/`) są w [E-002](./E-002-szybka-nauka/README.md). Instrukcja zbiorcza jest [materiałem źródłowym](./E-002-szybka-nauka/sources/instrukcja-realizacji.md), nie drugim rejestrem wykonania.

| Dawny task / plik w docs/taski | Pełne ID i aktualny task |
|---|---|
| 00 · 00-testy-na-postgresie.md | [E-002/F-001/T-001](./E-002-szybka-nauka/features/F-001-fundamenty/tasks/T-001-testy-postgresql.md) |
| 01 · 01-region-api-i-bazy.md | [E-002/F-001/T-002](./E-002-szybka-nauka/features/F-001-fundamenty/tasks/T-002-region-api-i-bazy.md) |
| 02 · 02-zapisy-pomocnicze-w-tle.md | [E-002/F-001/T-003](./E-002-szybka-nauka/features/F-001-fundamenty/tasks/T-003-zapisy-w-tle.md) |
| 03 · 03-petla-learnable.md | [E-002/F-004/T-001](./E-002-szybka-nauka/features/F-004-karty/tasks/T-001-petla-learnable.md) |
| 04 · 04-szybka-odpowiedz-z-cache.md | [E-002/F-002/T-001](./E-002-szybka-nauka/features/F-002-wyszukiwanie/tasks/T-001-cache.md) |
| 05 · 05-pierwsze-slowo-bez-slownika.md | [E-002/F-002/T-002](./E-002-szybka-nauka/features/F-002-wyszukiwanie/tasks/T-002-pierwsze-slowo.md) |
| 06 · 06-pelne-dociagniecie-i-wiecej.md | [E-002/F-002/T-003](./E-002-szybka-nauka/features/F-002-wyszukiwanie/tasks/T-003-wiecej-propozycji.md) |
| 07 · 07-telefon-szukanie-i-zestawienie.md | [E-002/F-002/T-004](./E-002-szybka-nauka/features/F-002-wyszukiwanie/tasks/T-004-room.md) |
| 08 · 08-skojarzenia.md | [E-002/F-003/T-001](./E-002-szybka-nauka/features/F-003-skojarzenia/tasks/T-001-skojarzenia.md) |
| 09 · 09-lekki-zapis-karty.md | [E-002/F-004/T-002](./E-002-szybka-nauka/features/F-004-karty/tasks/T-002-lekki-zapis.md) |
| 10 · 10-nauka-i-powiazane.md | [E-002/F-004/T-003](./E-002-szybka-nauka/features/F-004-karty/tasks/T-003-nauka-i-powiazane.md) |
| 11 · 11-import.md | [E-002/F-005/T-001](./E-002-szybka-nauka/features/F-005-import/tasks/T-001-import.md) |
| 12 · 12-wczesniejsze-znaczenia.md | [E-002/F-004/T-004](./E-002-szybka-nauka/features/F-004-karty/tasks/T-004-wczesniejsze-znaczenia.md) |

Nie zmieniono promptów ani wymagań tasków podczas przenoszenia. Ich historyczne wzmianki o innych numerach tasków odczytujemy przez tę tabelę.

## Pozostałe plany produktu

- Dawne `docs/epics.md` (następnie `docs/archive/product/epics.md`) i jedyny dawny epic **E-01** → [E-003 · Paczki startowe](./E-003-paczki-startowe/README.md); warianty zachowane w `sources/`.
- `docs/analiza-pedagogiczna-produktowa.md` i powiązany canvas (następnie `docs/archive/product/`) → [E-004 · Rozwój nauki](./E-004-rozwoj-nauki/README.md), z pięcioma odłożonymi features. Analiza i canvas zachowane w `sources/`.
- Gotowe zestawy z punktu 13 analizy należą do E-003, nie do drugiego feature'a E-004.
- Dawne sugestie głosu/STT, platform i monetyzacji pozostają kontekstem źródła, nie przyjętym zakresem implementacji.

## Co pozostaje poza hierarchią

Utrzymywane instrukcje, referencje i scenariusze pozostają w `setup/`, `reference/`, `testing/`. Historyczne audyty i dawna dystrybucja APK pozostają w [archiwum](../archive/README.md). Nie tworzymy sztucznych epików dla każdego audytu.
