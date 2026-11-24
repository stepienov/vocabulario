# Epiki Vocabulario

Stały rejestr tematów produktu. **Epic → feature → opcjonalne taski.** Dokumenty zostają w swoich miejscach po zakończeniu; zmieniamy status i dopisujemy dowody, nie przenosimy do archiwum.

## Rejestr

| ID | Epic / rezultat biznesowy | Status | Priorytet |
|---|---|---|---|
| E-001 | [Beta Google Play](./E-001-google-play-beta/README.md) — tester sam instaluje aplikację, zarządza kontem i nie traci danych | `in_progress` — 8 features / 24 taski; trwa implementacja, dowody jeszcze przed nami | Teraz |
| E-002 | [Szybkie wyszukiwanie i gotowość do nauki](./E-002-szybka-nauka/README.md) — krótsze oczekiwanie bez nadmiarowych żądań | `verification_required` — zachowane kontrakty, nie zlecenie ponownej implementacji | Chronić przy zmianach |
| E-003 | [Paczki startowe](./E-003-paczki-startowe/README.md) — pierwsza wartość bez ręcznego budowania słownika | `parked` | Poza betą |
| E-004 | [Skuteczność nauki i rozwój produktu](./E-004-rozwoj-nauki/README.md) — utrzymanie regularności i używanie poznanych słów | `parked` — hipotezy do discovery | Poza betą |
| E-005 | [Wspólna treść kart](./E-005-wspolna-tresc-kart/README.md) — jedno źródło treści przy osobnym postępie i działaniu offline | `in_progress` — implementacja i walidacja lokalna; bez migracji/deployu | Do decyzji |

E-001 ma zamknięte decyzje biznesowe i przygotowane kontrakty; `ready` nie oznacza wdrożonej/odebranej aplikacji ani zgody na publikację. Implementacja wymaga osobnego zlecenia; realne ID/domena/Console/umowy/koszty i wyniki testów mają bramki we właściwych taskach.

## Praca z dokumentacją

- [Zasady, numeracja, statusy i wzory](./zasady.md) — jak dodawać i zamykać tematy.
- [Mapa migracji](./migracja.md) — dawne B-00…B-14, taski 00–12 i E-01 → nowe identyfikatory.
- [Mapa pozostałej dokumentacji](../README.md) — setup, referencje, testy i historyczne audyty.

Następny epic otrzyma **E-006**. Nie rezerwujemy numerów dla samych luźnych pomysłów i nie zmieniamy numeracji według kolejności wykonania.
