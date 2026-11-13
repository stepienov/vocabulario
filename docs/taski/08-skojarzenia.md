# Task 08. Szukanie skojarzeń

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 4. Prompty, liczby i tabela napisów są tam. Ten task mówi, jak to wpiąć w kod i w jakiej kolejności.

## Zakres

Serwer:

1. Nowe klucze `assoc:{klucz}` (słowo) i `assoc:{klucz}:{runda}` (ósemki), klucz bazowy obcięty do 190 znaków.
2. `POST /lookup/category/cached`: słowo z wiersza albo z jednego wywołania luny.
3. `POST /lookup/category/expand` z polem `round`: ósemka z wiersza albo z jednego wywołania terry, 409 `assoc_round_not_ready`, zgodność ze starszym telefonem.
4. `round` w kluczu `_inflight`, zapisy w tle, połączenie zwolnione na czas modelu.

Telefon:

5. Nowa sesja skojarzeń zamiast `LookupSession` w `CategoryLookupCoordinator`: dwa pytania naraz, filtr pierwszego słowa, rundy 2 i 3, bez workera.
6. Napisy.

Poza zakresem: wiersze `cat:` (zostają w tabeli, nikt ich nie czyta), `associations_l2` na kartach.

## Zależności

- Task 02 (`reasoning_effort`, zapisy w tle), task 04 (szybka gałąź, `local_membership`, historia w tle), task 05 (`NOUN_ARTICLE_RULE`), task 06 (zestawienie poza wspólnym zadaniem, `added`).
- Task 07 na telefonie: zestawienie z Room, stan „przynależność nieznana”, parametr `singleRequest` w `LookupSession`.

## Pliki

Serwer:

- `backend/app/schemas/__init__.py`: `LookupRequest.round: int | None = None`,
- `backend/app/ai/prompts/v1.py`: `ASSOC_WORD_SYSTEM`, `ASSOC_WORD_USER`, `ASSOC_SCENE_SYSTEM`, `ASSOC_SCENE_USER`,
- `backend/app/services/llm.py`: `lookup_category_draft`, `lookup_category_expand`,
- `backend/app/services/lexical.py`: `_assoc_key`, `lookup_category_cached`, `lookup_category_expand`,
- `backend/app/services/lookup_category_jobs.py`: `_key`, `ensure_expand_task`, `await_lookup_category_expand`, `_run_expand`,
- `backend/app/api/v1/learning.py`: endpointy `lookup_category_cached`, `lookup_category_expand`,
- testy: `backend/tests/test_lookup_category.py`.

Telefon:

- `android/app/src/main/java/com/vocabulario/app/data/lookup/CategoryLookupCoordinator.kt`, nowy `AssociationSession.kt` w tym pakiecie,
- `android/app/src/main/java/com/vocabulario/app/data/LearningRepository.kt`: `lookupCategoryCached`, `lookupCategoryExpand(text, round)`,
- `android/app/src/main/java/com/vocabulario/app/data/sync/LookupPollWorker.kt`, `AppVisibilityHandler.kt`,
- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt`, `HomeScreen.kt`,
- `android/app/src/main/res/values*/strings.xml` (17 plików),
- testy: nowy `AssociationSessionTest.kt`.

## Zachowanie serwera

### Klucze

```python
def _assoc_key(self, text: str, round: int | None = None) -> str:
    base = "assoc:" + self._query_cache_key(text)[:190]
    return base if round is None else f"{base}:{round}"
```

Najdłuższy klucz: 6 + 190 + 2 = 198 znaków, mieści się w `input_norm VARCHAR(200)`.

### `category/cached`

- `local_membership=true`: ta sama szybka gałąź co w tasku 04 (jedno zapytanie profil + wiersz), z kluczem `_assoc_key(text)`.
- Wiersz z kandydatami: odpowiedź, `source=db`, `ai_complete=false`.
- Brak wiersza: `commit` (połączenie wraca do puli), jedno `llm.lookup_category_draft` (luna, `reasoning_effort="none"`, `max_tokens=120`, prompt z punktu 4 z `NOUN_ARTICLE_RULE`). Wynik przez `_raw_to_candidates`, najwyżej 1 kandydat, zapis `_merge_into_query_cache(pair, _assoc_key(text), …)` z `ai_complete=false`, `commit`, odpowiedź `source=ai`.
- Pusty wynik modelu: wiersza nie ma, odpowiedź pusta.
- Bez `_db_first_candidates`, bez `lexical_entries`, bez `_fuzzy_l1_db_candidates`.
- Historia i `hit_count` w tle (task 04).

### `category/expand`

`effective_round = body.round or 1`. Zadanie w `lookup_category_jobs` z kluczem `(user_id, profile_id, "assoc:" + norm, effective_round)`.

W zadaniu, `LexicalService.lookup_assoc_round(user_id, profile_id, text, round)`:

```
round > 3: LookupOutcome([], "db", True, added=0)
T1: profile; row = wiersz _assoc_key(text, round)
    row z kandydatami: return (kandydaci, "db", True, added=len)
    round >= 2 i brak wiersza round-1 z kandydatami: raise AssocRoundNotReady
    already = kanoniczne lemy z wiersza słowa i rund 1..round-1
    commit
model: llm.lookup_category_expand(text, app_lang, learning_lang, already)
       terra, reasoning_effort="none", max_tokens=400, prompt z punktu 4
       incoming = _raw_to_candidates(raw), bez lem, których klucz kanoniczny jest w already
T2: INSERT wiersza round ON CONFLICT (lang_pair, input_norm) DO NOTHING
    konflikt: odczyt wiersza zwycięzcy i jego kandydaci
    wiersz z ai_complete=true
    return (kandydaci, "ai", True, added=len)
```

Pusty wynik modelu nie tworzy wiersza. Następna runda dostanie wtedy 409, a telefon po pustej doklejce i tak pokazuje „brak dalszych skojarzeń”.

Kolejność kandydatów zostaje z modelu (4 rzeczowniki, 2 czasowniki, 2 przymiotniki), tylko przez `sanitize_lookup_candidates`. `rank_category_candidates` na tej ścieżce nie jest wołane.

Endpoint:

- `AssocRoundNotReady`: `api_error(409, "assoc_round_not_ready", ...)`,
- `body.round is None` (starszy telefon): na początek listy kandydaci z wiersza `_assoc_key(text)` (słowo), potem ósemka. Starszy `LookupSession` zastępuje listę wynikiem expand i bez tego zgubiłby pierwszy kafelek,
- `local_membership=false`: zestawienie z kartami poza zadaniem, jak w tasku 06,
- `added` w odpowiedzi.

`_run_expand` nie ładuje `User`. Historia przy świeżym modelu w commicie `T2`, przy trafieniu w wiersz w tle.

### Usunięcie starej ścieżki

`_category_draft_candidates`, `LOOKUP_CATEGORY_DRAFT_PROMPT_V1`, `LOOKUP_CATEGORY_EXPAND_PROMPT_V1`, `LOOKUP_CATEGORY_DRAFT_LIMIT`, `_category_cache_key` i `CATEGORY_QUERY_PREFIX` w kluczu `_inflight` znikają, jeśli `rg` nie pokaże innego użycia. Stare `_already_block` znika razem z nimi (task 06 ma już nowy nagłówek).

## Zachowanie telefonu

### `AssociationSession`

Stan:

```kotlin
data class AssociationState(
    val generation: Long, val query: String,
    val word: LookupCandidate?, val wordLoading: Boolean,
    val rounds: List<List<LookupCandidate>>,   // ósemki 1..3 w kolejności
    val roundLoading: Int?,                    // runda w toku
    val exhausted: Boolean,                    // „brak dalszych skojarzeń”
    val error: String?, val notice: String?,
)
```

`start(query)`:

- nowa generacja, oba pytania naraz: `lookupCategoryCached(query)` i `lookupCategoryExpand(query, round = 1)`,
- słowo: pierwszy kandydat odpowiedzi albo `null`,
- runda 1: kandydaci bez tych, których `canonicalLemma` (task 07) równa się `canonicalLemma(word.lemma)`, bez względu na część mowy. Filtr liczy się przy każdej publikacji, bo słowo i runda wracają w dowolnej kolejności,
- oba puste: komunikat jak dziś przy pustym wyniku,
- bez `enqueueLookup`, bez `refreshFromCache` w pętli.

`more()`:

- działa, gdy `rounds.size` to 1 albo 2, nic nie jest w toku i `!exhausted`,
- `lookupCategoryExpand(query, round = rounds.size + 1)`,
- wynik po odfiltrowaniu słowa i lem z poprzednich rund (klucz kanoniczny): dopisany jako nowa runda,
- pusty wynik albo runda 3: `exhausted = true`,
- 409 `assoc_round_not_ready`: bez zmiany stanu, przycisk aktywny,
- inny błąd: `notice` = `err_lookup_expand`, przycisk aktywny.

`retryPending()` (powrót do aplikacji): gdy runda albo słowo były w toku, to samo pytanie jeszcze raz. Serwer odda wiersz albo dołączy do trwającego zadania.

`HomeViewModel` dostaje kafelki jako `listOfNotNull(word) + rounds.flatten()`, przez to samo zestawienie z Room co w tasku 07.

### Worker

`CategoryLookupCoordinator` nie woła `enqueueLookup`. `AppVisibilityHandler.onStop` nie kolejkuje workera dla skojarzeń. Gałąź kategorii w `LookupPollWorker` znika. Parametr `singleRequest` w `LookupSession` (task 07) i gałąź `false` znikają, bo nikt jej już nie używa.

### Ekran

- pod pierwszym kafelkiem `lookup_assoc_searching`, dopóki runda 1 nie dojdzie,
- przycisk `lookup_assoc_more` pod listą, gdy jest runda 1 albo 1 i 2, nic nie jest w toku i `!exhausted`,
- w trakcie rundy 2 albo 3 pod listą dotychczasowe kółko,
- `lookup_assoc_no_more`, gdy `exhausted`,
- checkbox `search_by_category` z nowym tekstem.

Napisy według tabeli z punktu 4. `search_by_category` zmienia tekst we wszystkich 17 plikach (`values/` i `values-en`: „Search associations”, `values-pl`: „Szukaj skojarzeń”, pozostałe: tłumaczenie). To zmiana istniejącego klucza, więc `scripts/i18n_apply.py` jej nie zrobi: edycja ręczna w każdym pliku i w `scripts/i18n_pack.json`. Trzy nowe klucze idą zwykłym trybem z README.

## Kroki

1. Serwer: `_assoc_key`, prompty, `llm`.
2. Serwer: `category/cached`, `category/expand`, `lookup_category_jobs`, testy. Wdrożyć. Starszy telefon działa dalej (słowo + ósemka z expand).
3. Telefon: `AssociationSession` z testami, koordynator, ekran, napisy, usunięcie workera.

## Sprawdzenie

Testy serwera (`pytest`):

- wpis o długości 200 znaków: `category/cached` i `category/expand` z `round=3` kończą się 200, klucze mają najwyżej 200 znaków,
- `round=2` bez wiersza rundy 1: 409 `assoc_round_not_ready`,
- `round=1` i `round=2` naraz: dwa osobne zadania w `_inflight`, dwa `round=2` naraz: jedno,
- dwa równoczesne zadania `round=1` z dwóch kont tej samej pary (atrapa modelu): jeden wiersz `:1`, obie odpowiedzi te same,
- `round` brak: odpowiedź zaczyna się od słowa, potem ósemka,
- `round=4`: pusto, bez modelu,
- atrapa terry oddaje lemę z rundy 1 w rundzie 2: lema odfiltrowana,
- atrapa `client.chat.completions.create`: luna `max_completion_tokens=120`, terra `400`, oba `reasoning_effort="none"`.

Testy telefonu (`./gradlew testDebugUnitTest`):

- `AssociationSessionTest`: słowo `la pradera` i runda z `pradera` dają rundę bez `pradera` niezależnie od kolejności odpowiedzi; `more` po rundzie 3 nie woła sieci; pusta runda 2 ustawia `exhausted`; 409 zostawia przycisk.

Produkcja i telefon: lista z sekcji „Jak sprawdzimy” w punkcie 4 dokumentu źródłowego, w całości. Dodatkowo:

- `app_logs.duration_ms`: `category/cached` przy nowym słowie poniżej 2 s, `category/expand` rundy 1 poniżej 3,5 s (dziś p50 6,7 s i 13,4 s, z ósemką z luny p50 18,2 s),
- starsza wersja telefonu: po zaznaczeniu checkboxa widzi słowo i ósemkę, bez błędu.

## Ryzyka

- Klasyfikator wietnamski w pierwszym słowie (`cái nhà`). Przyjęte w punkcie 4.
- Pusta runda nie tworzy wiersza, więc następna osoba z tym wpisem znowu woła model dla tej rundy. To koszt jednego wywołania terry na osobę, tylko dla wpisów, przy których model nic nie znajduje. Przy pomiarze żadna runda nie wróciła pusta.
