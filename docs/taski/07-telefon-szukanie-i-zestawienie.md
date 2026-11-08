# Task 07. Telefon: jedno pytanie przy szukaniu i zestawienie kafelków z Room

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 1 (części „Telefon”), punkt 2 (ostatni akapit instrukcji), punkt 3 (część telefonu).

## Zakres

1. `LookupSession` i `LookupCoordinator`: jedno `lookup/cached`, bez workera, bez ponawiania `lookup/cached` w trakcie dociągania, automatyczne dociągnięcie tylko przy pustej odpowiedzi.
2. „Pokaż więcej propozycji” i „Nie ma więcej propozycji.”
3. Worker tylko do trwającego `lookup/expand`.
4. Nowa funkcja zestawienia kafelka z kartą, zgodna z serwerowym `select_live_card_for_lemma`, i czwarty stan kafelka „przynależność nieznana”.
5. `local_membership=true` w `lookup/cached` i `lookup/expand`.

Poza zakresem: szukanie skojarzeń i `CategoryLookupCoordinator` (task 08), zapis karty i 409 (task 09).

## Zależności

- Task 03: limit odpytywania kart. Kafelek dopasowany do karty `learnable` nie może uruchomić wiecznego odpytywania.
- Taski 04, 05, 06 na serwerze: `local_membership`, `more`, `added`, gałąź bez wiersza bez automatycznego dociągania. Telefon działa też ze starym serwerem: dostaje wtedy pola nauki (i tak nadpisane z Room), a `added` jest `null`.

## Pliki

- `android/app/src/main/java/com/vocabulario/app/data/api/Models.kt`: `LookupRequest`, `LookupResponse.added`, `LookupCandidate.membershipUnknown`,
- `android/app/src/main/java/com/vocabulario/app/data/LearningRepository.kt`: `lookupCached`, `lookupExpand`,
- `android/app/src/main/java/com/vocabulario/app/data/lookup/LookupCoordinator.kt`: `LookupCoordinator`, `LookupSession`, `LookupSessionState`,
- `android/app/src/main/java/com/vocabulario/app/data/lookup/LookupQueryPersistence.kt`: flaga `more`,
- `android/app/src/main/java/com/vocabulario/app/data/sync/LookupPollWorker.kt`,
- `android/app/src/main/java/com/vocabulario/app/AppVisibilityHandler.kt`,
- nowy `android/app/src/main/java/com/vocabulario/app/data/CardMembership.kt`,
- `android/app/src/main/java/com/vocabulario/app/data/local/db/Daos.kt`: lekkie zapytanie kart i obserwacja `lastPulledAt`,
- `android/app/src/main/java/com/vocabulario/app/data/local/OfflineStore.kt`,
- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt`: `applyLookupSession`, `candidateMatchesCard`, nowa akcja `showMoreSuggestions`,
- `android/app/src/main/java/com/vocabulario/app/ui/home/HomeScreen.kt`: `CandidateRow`, napis pod listą,
- `android/app/src/main/res/values*/strings.xml`: `lookup_more_suggestions`, `lookup_no_more_suggestions`,
- testy: `android/app/src/test/.../LookupSessionTest.kt`, `CandidateMatchesCardTest.kt`, nowy `CardMembershipTest.kt`.

## Zachowanie

### Żądania

`LookupRequest(text, profile_id, local_membership: Boolean = false, more: Boolean = false)`. Domyślne `false`, żeby `lookupCategoryCached`, `lookupCategoryExpand` i `api.lookup` z kolejki Oczekujących wysyłały to co dziś. `lookupCached` i `lookupExpand` przekazują `local_membership = true` jawnie. Retrofit używa `Json { encodeDefaults = true }` (`AppModule.kt`), więc pola idą zawsze.

`LookupResponse.added: Int? = null`.

### `LookupSession`

`runLookup(text, gen)`:

1. `lookup/cached` (z dotychczasowym jednym ponowieniem przy `IOException`).
2. Odpowiedź z co najmniej jedną propozycją: publikacja kafelków, `expanding = false`, `finishActive`. Także przy `ai_complete = false`. Koniec.
3. Pusta odpowiedź z `ai_complete = true`: `expanding = false`, koniec, jak dziś.
4. Pusta odpowiedź bez `ai_complete`: jedno `lookup/expand` (`more = false`). Bez równoległego `pollJob` i bez `pollCachedUntilReady`.
5. `lookup/expand` padło przy `IOException` po ponowieniu: jedno `lookup/cached`. Ma propozycje, to je pokazać. Nie ma, to błąd jak dziś.

`CategoryLookupCoordinator` tworzy tę samą klasę `LookupSession`. Nowe zachowanie włącza parametr konstruktora `singleRequest: Boolean`. `LookupCoordinator` podaje `true`, `CategoryLookupCoordinator` zostaje przy `false` (dzisiejsza logika z odpytywaniem) do taska 08. Bez tego szukanie kategorii na nowym telefonie przestałoby dociągać listę do około 21 słów, zanim serwer dostanie rundy skojarzeń. Gdy task 08 wyjdzie, gałąź `singleRequest = false` razem z `cachedPollDelayMs`, `cachedPollAttempts` i `pollCachedUntilReady` znika.

Nowa metoda `showMore()`:

- działa, gdy jest bieżące hasło i co najmniej jeden kafel,
- stan `loadingMore = true` (nowe pole `LookupSessionState`), pod listą dotychczasowe kółko dociągania,
- jedno `lookup/expand` z `more = true`,
- wynik przez `mergeLookupCandidates(current, response.candidates)`, kafelki, które już były, zostają,
- `response.added == 0`: `notice` = `lookup_no_more_suggestions`, lista bez zmian,
- błąd: `notice` = dotychczasowe `err_lookup_expand`, kafelki zostają,
- napis „Pokaż więcej propozycji” zostaje i można go tapnąć ponownie.

Generacja: nowe szukanie w trakcie `showMore` anuluje to zadanie, jak dziś przy `start`.

### `LookupCoordinator`

- `start(query)`: bez `backgroundJobs.enqueueLookup(...)`. Gdy pierwsza odpowiedź ma propozycje, wołamy `backgroundJobs.cancelLookup()`, żeby zadanie z poprzedniego szukania nie wysłało kolejnego `lookup/cached`.
- `retryPending()` (powrót do aplikacji): `refreshFromCache` tylko gdy `expanding` albo `loadingMore`. Dziś woła `lookup/cached` przy każdym powrocie, gdy pole hasła nie jest puste.

### Worker

`AppVisibilityHandler.onStop`: `enqueueLookup(replace = false)` tylko gdy zwykłe szukanie ma trwające `lookup/expand` (`expanding` po kroku 4 albo `loadingMore`). Warunek dla kategorii zostaje bez zmian do taska 08.

`LookupQueryPersistence` zapisuje obok hasła flagę `more` dla trwającego dociągania.

`LookupPollWorker.doWork`, gałąź zwykłego szukania: tylko `repository.lookupExpand(query, more = persistedMore)` i `acceptServerResult`. Bez `lookup/cached`. Gałąź kategorii bez zmian.

### Zestawienie z kartą

Nowy plik `CardMembership.kt`, czyste funkcje bez Androida:

```kotlin
data class CardMembershipRow(val id: String, val lemmaL2: String, val pos: String?,
                             val deckId: String?, val enrichmentStatus: String)

fun canonicalLemma(raw: String?): String
fun selectLiveCardForLemma(cards: List<CardMembershipRow>, lemma: String, pos: String?): CardMembershipRow?
```

`canonicalLemma` odtwarza `backend/app/core/lemma_keys.py`:

- przycięcie, NFKC, zamiana na małe litery jak `casefold` w Pythonie: `lowercase(Locale.ROOT)`, a potem `ß` → `ss` (najczęstsza różnica między `lowercase` a `casefold` w obsługiwanych językach),
- usunięcie `(…)` i `[…]`,
- każdy znak spoza kategorii Unicode L, M, N oraz spacji, `'` i `’` zamieniony na spację (`Character.getType`),
- zwinięcie spacji, zdjęcie `l'`/`l’` z początku,
- zdejmowanie z początku słów ze zbioru `_ARTICLES` (`el la los las le les un une der die das ein eine the a an il lo i gli o os as l`), po każdym zdjęciu znowu `l'`, do skutku.

Zbiór rodzajników jest kopią z `lemma_keys.py`. W obu plikach komentarz: zmiana tylko razem z drugim plikiem.

`selectLiveCardForLemma` odtwarza `select_live_card_for_lemma` z `backend/app/services/word_lists.py`:

- `want = normalizePosKey(pos)`, karta pasuje częścią mowy, gdy `want == "unknown"` i karta też `unknown`, albo gdy obie są równe,
- dokładna lema: `normalizeText` (przycięcie, małe litery, zwinięte białe znaki, NFC) karty równa propozycji: od razu ta karta,
- w innym razie klucz kanoniczny równy i niepusty: wygrywa karta z dłuższą `lemmaL2`.

`normalizePosKey` (`Constants.kt`) i `normalize_pos_bucket` (`pos_normalize.py`) to dwie różne implementacje. Test sprawdza na nich te same etykiety (`noun`, `rzeczownik`, `sustantivo masculino`, `verbo`, `adj`, `phrase`, `wyrażenie`, pusty) i ten sam wynik kubełka.

`sameLemmaAndPos` zostaje tylko w `mergeLookupCandidates`, `upsertListWord` i `mergeInFlightListWords`. `candidateMatchesCard` (używane przez `syncCandidatesFromWords` po odpytaniu kart) najpierw porównuje `learning_card_id`, potem woła `selectLiveCardForLemma`.

### Dane z Room

- `CachedCardDao`: `@Query("SELECT id, lemmaL2, pos, deckId, enrichmentStatus FROM cached_cards WHERE profileId = :profileId") fun observeMembershipRows(profileId: String): Flow<List<CardMembershipRow>>`. Bez `contentJson`, który przy kilkuset kartach jest głównym kosztem odczytu.
- `SyncMetaDao`: obserwacja `lastPulledAt` profilu (`Flow<String?>`).
- Przed implementacją sprawdzić, że `applyPullLocked` usuwa z `cached_cards` karty skasowane na serwerze. Inaczej skasowana karta dawałaby ikonę przy słowie, które serwer pozwoli dodać.

### `HomeViewModel`

Zestawienie działa na liście kafelków po `mergeLookupCandidates`, w jednym miejscu, przed zapisem do `_state`:

```
annotate(candidates, rows, lists, lastPulledAt, inFlightAdds)
```

- `lastPulledAt == null`: każdy kafelek dostaje `membershipUnknown = true` i puste pola nauki,
- inaczej dla każdego kafelka `selectLiveCardForLemma(rows, lemma, pos)`:
  - trafienie: `learning_card_id`, `in_learning`, `enrichment_status` z karty, `list_id` = `deckId` albo, przy pustym `deckId`, identyfikator listy systemowej z Room, `list_name` z lokalnej listy (lista systemowa: `R.string.list_learning`),
  - brak: pola nauki wyczyszczone (`learning_card_id`, `list_id`, `list_name`, `enrichment_status` = `null`, `in_learning = false`),
- kafelek, którego dodanie właśnie trwa (`inFlightAdds`, klucz lema + kubełek części mowy, ustawiany w `markCandidateOnList`, czyszczony po odpowiedzi albo `revertCreating`), zostaje bez zmian.

`HomeViewModel` łączy (`combine`) stan sesji szukania z `observeMembershipRows` i `lastPulledAt` aktywnego profilu. Każda zmiana kart w Room (koniec synchronizacji, nowa karta, usunięcie) zestawia kafelki jeszcze raz, bez sieci.

`LookupCandidate.membershipUnknown: Boolean = false` z `@Transient`, żeby nie szło do JSON.

### `CandidateRow`

Kolejność stanów prawej strony:

1. `membershipUnknown`: samo kółko, bez `CreatingCardHint`, bez akcji. Kafelek nie wchodzi do `enrichmentPollCardIds`, bo nie ma `learning_card_id`.
2. `isCreating`: kółko i „Tworzę kartę…”, jak dziś.
3. `onList`: ikona i nazwa listy, jak dziś.
4. W innym razie przycisk dodania.

### Napis pod listą

`lookup_more_suggestions` widać pod listą, gdy jest co najmniej jeden kafel, szukanie nie trwa (`!expanding`) i nie trwa `showMore`. Tap: `HomeViewModel.showMoreSuggestions()` → `lookupCoordinator.showMore()`. Komunikat `lookup_no_more_suggestions` idzie przez istniejące pole `notice`.

Napisy:

| Klucz | `values/` i `values-en` | `values-pl` |
|---|---|---|
| `lookup_more_suggestions` | Show more suggestions | Pokaż więcej propozycji |
| `lookup_no_more_suggestions` | No more suggestions. | Nie ma więcej propozycji. |

W pozostałych 14 plikach `values-*` tłumaczenie w tym języku.

## Kroki

1. Modele i repozytorium (`local_membership`, `more`, `added`).
2. `CardMembership.kt` z testami. To najpierw, bo nie zależy od reszty.
3. DAO i obserwacja.
4. `annotate` w `HomeViewModel`, `candidateMatchesCard`, `CandidateRow`.
5. `LookupSession` bez odpytywania, `showMore`, testy `LookupSessionTest`.
6. Worker i `AppVisibilityHandler`.
7. Napisy.

## Sprawdzenie

Testy (`./gradlew testDebugUnitTest`):

- `CardMembershipTest`, przypadki takie same jak na serwerze:
  - `prado` przy karcie `el prado` (rzeczownik): trafienie,
  - `el prado` przy karcie `prado`: trafienie,
  - `castillo (fortaleza)` przy karcie `el castillo`: trafienie,
  - `l'eau` przy karcie `eau`: trafienie,
  - propozycja bez części mowy przy karcie rzeczownika: brak,
  - propozycja rzeczownika przy karcie bez części mowy: brak,
  - obie bez części mowy: trafienie,
  - `play` czasownik przy karcie `play` rzeczownik: brak,
  - dwie karty kanonicznie równe: wygrywa dłuższa lema,
  - `Straße` przy karcie `STRASSE`: trafienie (jak `casefold`).
- `LookupSessionTest`:
  - odpowiedź z jedną propozycją i `ai_complete=false`: brak wywołania `lookupExpand`, `expanding=false`,
  - pusta odpowiedź: jedno `lookupExpand`, zero dodatkowych `lookupCached` w trakcie,
  - `showMore` z `added=0`: kafelki te same, `notice` ustawione,
  - `showMore` z nowym hasłem: stare kafelki zostają, nowe dochodzą.
- `CandidateMatchesCardTest` zaktualizowany do nowej reguły.

Telefon z serwerem po taskach 04–06, konto `nowy4@test.com`:

- `prado`, karty pobrane: jedno `POST /lookup/cached` w logu HTTP Railway z tego urządzenia, zero `lookup/expand`, zero `GET /cards/{id}` z powodu kafelków bez kart. Kafelek przy karcie ma ikonę i nazwę listy, inne mają przycisk dodania. Pod listą „Pokaż więcej propozycji”.
- Świeża instalacja przed pierwszą synchronizacją: kafelki od razu, po prawej kółko bez „Tworzę kartę…”, bez `GET /cards/{id}`. Po synchronizacji ikona albo przycisk, bez drugiego szukania.
- Nowe hasło z jednym słowem z punktu 2: brak automatycznego `lookup/expand`. Hasło, przy którym luna oddaje pustkę: jedno `lookup/expand` bez `lookup/cached` w trakcie.
- Tap „Pokaż więcej propozycji”: jedno `lookup/expand` z `more=true`. Przy `added=0` napis „Nie ma więcej propozycji.”
- Minimalizacja w trakcie `lookup/expand`: worker woła tylko `lookup/expand`. Minimalizacja po wyniku: worker nie startuje. Powrót do aplikacji z widocznym, skończonym wynikiem: zero żądań szukania.
- Tap dodania przy każdym słowie bez ikony na koncie z 492 kartami nie daje 409 (pięć różnych haseł, w tym z rodzajnikiem i z nawiasem).
- Język interfejsu bez własnego pliku (na przykład szwedzki w ustawieniach systemu) pokazuje angielski napis, bez `Resources.NotFoundException`.

## Ryzyka

- Rozjazd z serwerem przy rzadkich etykietach części mowy albo znakach. Skutek: przycisk dodania przy duplikacie i 409, który obsługuje task 09 (synchronizacja i ponowne zestawienie).
- `combine` z Room przy każdej zmianie kart przelicza wszystkie kafelki. Przy kilkuset kartach i kilku kafelkach to pojedyncze milisekundy. Liczyć w `Dispatchers.Default`.
