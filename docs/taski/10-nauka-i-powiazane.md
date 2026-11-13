# Task 10. Rdzeń karty dzielony na naukę i powiązane

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 6. Schemat czasów i stanów: `docs/wzbogacanie-karty-schemat.md`. Prompty są w punkcie 6, w tym zdanie o `headword_note` i REL2.

## Zakres

Serwer:

1. Dwa nowe wywołania terry zamiast `enrich_core`: `enrich_study` i `enrich_related`, oba `reasoning_effort="none"`, limit 2200.
2. `assemble_core_card` dzielone na `assemble_study_card` i `assemble_related_part`.
3. `run_lemma_enrichment` puszcza cztery zadania naraz (nauka, powiązane, słowa podobne, odmiana) i oddaje wyniki przez wywołania zwrotne w kolejności powrotu.
4. Znacznik `related_pending` i warunek w `content_is_complete`.
5. Zapis każdej części przez ponowny odczyt karty, `learnable` po nauce, powiązane doklejane od razu, `ready` po wszystkim.
6. Ponowienie samej brakującej części, w tym samych powiązanych.

Telefon:

7. Sekcje powiązanych, słów podobnych i odmiany z kółkiem, dopóki karta nie jest `ready` i jest odpytywana.

Poza zakresem: prompty `similar_words` i `inflection` (bez zmian), import (task 11), karty adaptacyjne (zwrot, konstrukcja, `other`: dotychczasowe jedno wywołanie).

## Zależności

- Task 02: `reasoning_effort`, zapisy `llm_usage` w tle.
- Task 03: wspólny warunek odmiany, limit ponowień, `enrichment_active`.
- Task 09: hydracja przed semaforem, `attach_card_to_word_family` w zadaniu.

## Pliki

Serwer:

- `backend/app/ai/prompts/v1.py`: `ENRICH_STUDY_SYSTEM`, `ENRICH_STUDY_USER`, `ENRICH_RELATED_SYSTEM`, `ENRICH_RELATED_USER`,
- `backend/app/services/llm.py`: `enrich_study`, `enrich_related`,
- `backend/app/lsp/enrichment.py`: `assemble_study_card`, `assemble_related_part`, `run_lemma_enrichment`, `side_jobs_need_retry`, `finish_side_jobs`, `merge_side_jobs`,
- `backend/app/services/related_articles.py`: `fill_related_articles_on_core` dostaje samą część powiązaną (bez zmiany logiki),
- `backend/app/services/card_jobs.py`: `content_is_complete`, `_enrich_lemma_staged`, `_persist_enrichment_result`,
- testy: `backend/tests/test_enrichment_pipeline.py`, `test_related_articles.py`, `test_word_family.py`, `test_examples_merge.py`.

Telefon:

- `android/app/src/main/java/com/vocabulario/app/ui/card/CardDetailContent.kt`, `FlashcardBackContent.kt`,
- miejsca, które je wołają (`enrichmentStatus` i nowy parametr `sectionsLoading`).

## Zachowanie serwera

### Wywołania

```python
async def enrich_study(self, profile, lemma, pos, gloss) -> dict      # purpose="enrich_study"
async def enrich_related(self, profile, lemma, pos, gloss) -> dict    # purpose="enrich_related"
```

Oba: `self.lookup_model`, `reasoning_effort="none"`, `max_tokens=2200`, bez temperatury, `json_object`, prompty z punktu 6 z `lang_name_en`. W systemie nauki na końcu zdanie o `headword_note`.

Walidacja nauki: `_core_examples_valid` jak dziś. Gdy zdań brakuje, dotychczasowe dociągnięcie `examples` (to samo co w `_fetch_core_with_examples`), z tym samym limitem prób.

### Składanie

`assemble_study_card(profile, lemma, pos, study) -> dict` robi z dzisiejszego `assemble_core_card` część nauki:

- hasło: `_same_headword`, `prefer_citation_headword`, część mowy (`phrase`/`construction` z wpisu zostaje),
- `_normalize_usages`, `strip_prepositional_construction_meanings`, `MAX_MEANINGS`,
- `ui_hints` z manifestu (`script`, `rtl`, `inflection_kind`, `show_conjugation` przy `inflect_pos_key == "verb"`),
- `ipa`, `headword_note` przez `normalize_headword_note`,
- `synonyms_l2`, `antonyms_l2`, `word_family_l2`, `associations_l2`, `similar_words` puste listy, `inflection` i `conjugation` `None`,
- `language_specific` `{}`, `notes` i `confidence` `None`,
- `related_pending: True`,
- `repair_strings` na końcu.

`assemble_related_part(profile, lemma_final, pos_final, related) -> dict`:

- `fill_related_articles_on_core(llm, related, learning_lang)` przed normalizacją, tylko gdy rzeczownikowi brakuje `article` (jak dziś),
- `_normalize_related_words` dla czterech list (synonimy i przeciwieństwa z `fallback_pos=pos_final`),
- `filter_word_family`, `filter_associations`, jak dziś,
- zwraca same cztery listy.

`drop_related_missing_articles` działa tam, gdzie dziś, przy zapisie karty.

### Orkiestracja

`run_lemma_enrichment(profile, lemma, pos, *, gloss_hint, on_study, on_related, require_similar=False, llm=None) -> dict`:

- start czterech zadań: `enrich_study`, `enrich_related`, `fetch_similar_words`, `fetch_lsp_inflection`, wszystkie na lemie i części mowy z wpisu,
- pętla `asyncio.wait(..., return_when=FIRST_COMPLETED)`. Wywołania zwrotne idą jedno po drugim z tej pętli, nigdy równolegle, bo dzielą jedną `AsyncSession`,
- nauka wróciła: `card = assemble_study_card(...)`, `await on_study(card)`. Gdy powiązane wróciły wcześniej, idą razem z nauką w tym samym `on_study` (pole w `card`, bez `related_pending`),
- powiązane wróciły po nauce: `await on_related(part)`,
- `side_jobs_need_retry` po nauce, gdy lema albo część mowy się zmieniły: ponownie słowa podobne, odmiana i powiązane na nowej lemie. Wyniki starych zadań tych części są odrzucane,
- błąd nauki: anulowanie pozostałych zadań, wyjątek w górę (dzisiejsze `_apply_enrich_retry`, karta `preparing`),
- błąd powiązanych: karta zostaje z `related_pending`, wynik końcowy bez powiązanych,
- wynik: karta z nauką, powiązanymi (jeśli są), słowami podobnymi i odmianą przez `merge_side_jobs` (z regułą „nie dotyczy” z taska 03).

### Zapis w `card_jobs`

`_enrich_lemma_staged`:

- `on_study(card)`: `await db.refresh(card_row, with_for_update=True)`, `_apply_content_fields` z treścią nauki (i powiązanych, jeśli przyszły razem), `enrichment_status = learnable`, `commit`, `notify_cards_ready`,
- `on_related(part)`: ponowny odczyt `FOR UPDATE`, doklejenie czterech list do aktualnego `content`, usunięcie `related_pending`, `sync_word_family`, `commit`, potem `attach_card_to_word_family` (z `source_card_id` z taska 09) i `commit`. Bez powiadomienia,
- koniec: ponowny odczyt, doklejenie słów podobnych i odmiany do aktualnego `content`, `_persist_enrichment_result`. `ready` i zapis do `lexical_entries` tylko przy `content_is_complete`.

`content_is_complete` dostaje warunek `not content.get("related_pending")`. Stare treści tego klucza nie mają, więc dalej są pełne.

`finish_side_jobs` (ponowienie karty `learnable`): `need_related = bool(content.get("related_pending"))`. Woła tylko brakujące części: powiązane, słowa podobne, odmianę. Limit ponowień z taska 03 obejmuje też powiązane.

`attach_card_to_word_family` przenosi się z miejsca „po wyniku modelu” (task 09) do `on_related`, bo potrzebuje `word_family_l2`. Przy karcie, której powiązane padły, rodzina dochodzi przy ponowieniu.

## Zachowanie telefonu

Wymaganie ekranu: `docs/wzbogacanie-karty-schemat.md`, sekcja „Ekran, niezależnie od widoku”.

Dziś serwer już nie przerywa dociągania, gdy użytkownik wyjdzie. `spawn_enrich` (`backend/app/services/card_jobs.py`) jest zadaniem procesu API, nie żądania HTTP. Zamknięcie aplikacji, wyjście z nauki i zamknięcie karty go nie kasują. Telefon tylko przestaje pytać.

Ekran tego nie wykorzystuje. `CardDetailContent` przy `pending` i `preparing` rysuje jeden napis `card_preparing` zamiast karty z sekcjami. Pusta sekcja jest ukryta (`synonymsL2.isNotEmpty()` i tak samo przeciwieństwa, rodzina, skojarzenia, słowa podobne, odmiana). Podgląd z listy to kopia `HomeViewModel.detailCard`. Nauka to osobna kopia `LearningViewModel.selectedCard`. Odpytywanie listy żyje w `HomeViewModel.startPollingIfNeeded` (co 2,5 s, karty z otwartej listy i z wyniku szukania). Odpytywanie nauki żyje w `LearningViewModel` (co 3 s, najwyżej 20 razy) i ginie razem z tym ekranem. Otwarta karta nie dostaje nowego wiersza, dopóki któreś z tych odpytywań nie zapisze go do swojej kopii.

### Instrukcja

Jedno odpytywanie karty żyje tak długo jak proces aplikacji, obok `LookupCoordinator`, nie w ViewModelu ekranu. `onStop`, `clearSelection` i wyjście z fiszki go nie anulują. Bierze `GET /cards/{id}` co 2,5 s dla kart, które nie są `ready` i dla których `EnrichmentPollPolicy.shouldKeepPolling` jeszcze jest prawdziwe. Każdy GET robi dotychczasowe `refreshCardsFromServer` (zapis do Room).

Podgląd z listy (`ListCardDetailOverlay`), nauka (`LearningScreen`) i fiszka czytają tę kartę z Room po `id`, nie ze zrzutu w ViewModelu. Nowy wiersz w Room podmienia otwarty ekran. Osobnego gestu odświeżenia nie ma.

`CardDetailContent` / `FlashcardBackContent` dostają `stillPolling` z `EnrichmentPoller.pollingIds`. Kółko liczy `CardSectionWaiting` (`android/.../EnrichmentStatus.kt`):

- znaczenia: puste i status `pending`/`preparing` i nadal odpytywane,
- synonimy / przeciwieństwa / rodzina / skojarzenia: puste i nadal odpytywane oraz (`related_pending == true` albo status przed `learnable`; przy `related_pending == false` bez kółka),
- odmiana: brak conjugacji i status jeszcze w `needsPoll` i nadal odpytywane.

Dla każdej sekcji: jest treść → treść; pusto i warunek kółka → nagłówek i kółko; pusto bez warunku → ukryte. Wejście w ćwiczenie jest aktywne, gdy znaczenia już są (`learnable`), także gdy reszta sekcji ma kółko.

Nie dodawać anulowania `spawn_enrich` przy zmianie ekranu. Takiego wywołania w telefonie nie ma i nie dochodzi.

## Kroki

1. Prompty i dwa wywołania, test atrapy parametrów.
2. `assemble_study_card`, `assemble_related_part`, testy porównujące z dzisiejszym `assemble_core_card` na tych samych danych (to samo hasło, te same zwroty, te same listy po filtrach).
3. `related_pending` w `content_is_complete`, test starych treści.
4. `run_lemma_enrichment` z pętlą i wywołaniami zwrotnymi, testy kolejności.
5. `_enrich_lemma_staged` i `finish_side_jobs`.
6. Telefon.
7. Usunięcie `enrich_core` i `ENRICHMENT_CORE_STATIC_V1`, jeśli `rg` nie pokaże innego użycia (karty adaptacyjne mają osobny prompt).

## Sprawdzenie

Testy serwera (`pytest`):

- atrapa `client.chat.completions.create`: `enrich_study` i `enrich_related` z `reasoning_effort="none"`, `max_completion_tokens=2200`, modelem `llm_lookup_model`,
- kolejność „powiązane przed nauką”: jeden zapis `learnable` z powiązanymi, bez `related_pending`,
- kolejność „nauka, powiązane, reszta”: `learnable` z `related_pending`, potem bez, potem `ready`,
- błąd powiązanych: karta `learnable` z `related_pending`, brak wiersza w `lexical_entries`, ponowienie woła tylko `enrich_related`,
- nauka zmienia lemę: słowa podobne, odmiana i powiązane wołane drugi raz z nową lemą,
- stara treść bez `related_pending`, z resztą pełną: `content_is_complete` prawdziwe,
- zapis powiązanych po zmianie `content` przez inny zapis (test zmienia `content` między wywołaniami): zmiana nie ginie.

Produkcja (po 01, 02, 03, 09), konto kontrolne: lista z sekcji „Jak sprawdzimy” w punkcie 6, w całości. Dodatkowo:

- od wiersza `learning_cards` do `learnable`: poniżej 8 s (dziś około 24 s okna rdzenia plus zapisy),
- od wiersza do `ready`: poniżej 25 s przy typowej odmianie (dziś typowo 43 s),
- `pensar` ma `headword_note` z obocznością.

Telefon: po dodaniu karta jest na liście z hasłem i tłumaczeniem, zanim dojdą sekcje. Wejście w ćwiczenie działa, gdy są znaczenia, przy kółkach na reszcie. Zamknięcie karty, przerwanie nauki i wyjście z aplikacji nie kasują zadania. Otwarta karta (lista, podgląd, nauka) podmienia kółko na treść bez ponownego otwarcia. Sekcja, której zadanie już nie dociąga, nie ma kółka.

## Ryzyka

- Pola z rdzenia, których telefon nie pokazuje (`language_specific`, `notes`, `confidence`, część `ui_hints`), w nowych kartach są puste. `notes` czyta tylko porównanie poprawki w `card_corrections`. Przyjęte w punkcie 6.
- `headword_note` nie było w pomiarze. Jeśli model nie trzyma pola, `normalize_headword_note` oddaje `None` i notka nie pokazuje się, bez innych skutków. Sprawdza to punkt `pensar`.
