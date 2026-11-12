# Task 12. Wcześniejsze znaczenia (rozcięcie nauki)

Dokument źródłowy: `docs/optymalizacja-requestow.md`, punkt 6a. Schemat: `docs/wzbogacanie-karty-schemat.md` (wiersz „Same znaczenia” i sekcja 6a).

## Zakres

Serwer:

1. Zamiast jednego `enrich_study`: `enrich_meanings` + `enrich_study_finish` (glosy z pierwszego callu są wejściem i nie wolno ich przepisać).
2. `run_lemma_enrichment` startuje pięć torów: meanings, related, similar, inflection od razu; study_finish dopiero po meanings.
3. Po meanings: zapis treści (glosy, bez examples), znacznik `examples_pending: true`, status zostaje `pending`/`preparing`, `notify_cards_ready`.
4. Po study_finish: dotychczasowe `learnable` (`on_study`), zdjęcie `examples_pending`, `related_pending` jak w tasku 10.
5. `ready` / `content_is_complete` / `lexical_entries` **bez zmian** względem taska 10.
6. Usunięcie ścieżki „jeden `enrich_study` z przykładami” z `run_lemma_enrichment` (metoda może zostać na czas migracji testów, ale pipeline lemma jej nie woła).

Telefon:

7. Kafelek i otwarcie karty: gdy są glosy (nawet bez zdań), nie traktować jak pustego „Tworzę…” — widać znaczenia, spinnery na zdaniach / powiązanych / podobnych / odmianie.
8. `CardSectionWaiting`: rozróżnienie braku glos vs braku zdań przy glosie.
9. Ćwiczenie (fiszka / wpisywanie) nadal tylko przy `learnable` (są examples) — bez zmian `content_is_learnable` / `isStudyable`.

Poza zakresem: import (11), karty adaptive, prompty similar/inflection, zmiana semantyki `ready`.

## Zależności

- Task 10: cztery tory, `related_pending`, `on_study` / `on_related`, spinnery sekcji.
- Task 09: hydracja przed semaforem.
- Task 03: limity odpytywania.

## Warunek startu

- W kodzie są `enrich_study`, `enrich_related`, `run_lemma_enrichment` z pętlą `FIRST_COMPLETED`, `assemble_study_card`, `related_pending` w `content_is_complete`.
- `rg "enrich_study" backend/app` pokazuje wywołanie z `_fetch_study_with_examples` / pipeline lemma.

## Pliki

Serwer:

- `backend/app/ai/prompts/v1.py`: `ENRICH_MEANINGS_SYSTEM/USER`, `ENRICH_STUDY_FINISH_SYSTEM/USER` (treść z punktu 6a),
- `backend/app/services/llm.py`: `enrich_meanings`, `enrich_study_finish` (`purpose` jak niżej, `reasoning_effort="none"`, limity tokenów z 6a),
- `backend/app/lsp/enrichment.py`: `assemble_meanings_card`, przebudowa `run_lemma_enrichment`, ewentualnie cienki `assemble_study_card` po finish,
- `backend/app/services/card_jobs.py`: `_enrich_lemma_staged` — `on_meanings`, dotychczasowe `on_study` / `on_related`,
- testy: `backend/tests/test_enrichment_pipeline.py`, nowy `test_enrich_meanings_split.py` (parametry calli + kolejność callbacków + gloss lock).

Telefon:

- `android/.../EnrichmentStatus.kt` (`CardSectionWaiting`),
- `CardDetailContent.kt`, `FlashcardBackContent.kt` (spinner zdań przy glosie),
- `HomeScreen.kt` (kafelek: nie `compactActions` / nie samo kółko „tworzę”, gdy content ma glosy bez examples; przycisk podglądu karty dostępny).

## Zachowanie serwera

### Wywołania

```python
async def enrich_meanings(self, profile, lemma, pos, gloss) -> dict
    # purpose="enrich_meanings", max_tokens=800, reasoning_effort="none", lookup_model

async def enrich_study_finish(self, profile, lemma, pos, locked_meanings: list[dict]) -> dict
    # purpose="enrich_study_finish", max_tokens=2200, reasoning_effort="none", lookup_model
    # locked_meanings = [{"gloss_l1": "..."}, ...] w kolejności
```

`enrich_related`, `similar_words`, `inflection` bez zmian względem taska 10.

### Orkiestracja

`run_lemma_enrichment(...)`:

- t0: `enrich_meanings` ∥ `enrich_related` ∥ `similar` ∥ `inflection`,
- po meanings: `assemble_meanings_card` → `await on_meanings(card)` (glosy, `examples_pending: true`, puste examples/usages, `related_pending` jeśli related jeszcze nie ma),
- dopiero potem start `enrich_study_finish` z zablokowanymi glosami,
- po finish: jak dzisiejszy `on_study` (learnable), scalić IPA/note/examples/usages, zdjąć `examples_pending`,
- related przed/po meanings: jak dziś (merge w on_meanings albo `on_related`),
- błąd meanings: anuluj finish (nie startuj), related/similar/infl anuluj, retry jak dziś przy padniętej nauce,
- błąd finish: karta ma glosy, status wraca do pętli ponowień nauki; nie ustawiać `learnable`,
- `ready` dopiero przy `content_is_complete` (bez zmian).

### Prompty

Dokładne brzmienie: `docs/optymalizacja-requestow.md` punkt 6a. Nie parafrazować.

### Zapis

`on_meanings`: `db.refresh(..., with_for_update=True)`, `_apply_content_fields`, **nie** zmieniać na `learnable`, commit, `notify_cards_ready`.

`on_study` (po finish): jak task 10.

## Zachowanie telefonu

- Glosy w content bez examples → sekcja znaczeń pokazuje glosy; przy każdym znaczeniu lub pod listą kółko „zdania”, dopóki `examples_pending` albo brak examples i status w `needsPoll`.
- Kafelek listy: przy glosach bez examples nie pokazywać stanu „tylko tworzę” (kółko blokujące podgląd). Podgląd karty otwarty. Ćwiczenie z listy / nauki nadal wymaga `learnable`.
- `related` / odmiana / podobne: bez zmian reguł z taska 10 (+ poprawki spinnera odmiany już w kodzie).

## Kroki

1. Prompty + `enrich_meanings` / `enrich_study_finish`, test atrapy parametrów.
2. `assemble_meanings_card`, gloss-lock w finish, testy.
3. `run_lemma_enrichment` + `_enrich_lemma_staged` (`on_meanings`).
4. Telefon: waiting + kafelek + spinnery zdań.
5. Usunięcie użycia `_fetch_study_with_examples` / pełnego `enrich_study` z pipeline lemma, jeśli `rg` nie pokaże innego potrzebnego użycia.

## Sprawdzenie

Lokalnie (`pytest`):

- atrapa: `enrich_meanings` i `enrich_study_finish` z `reasoning_effort="none"`, właściwe `max_completion_tokens`, model `llm_lookup_model`,
- finish dostaje te same `gloss_l1` co meanings; odpowiedź z innym glossem → odrzucenie / retry w teście walidacji,
- kolejność: commit z glosami przed startem finish; `learnable` dopiero po finish,
- related przed meanings: jeden zapis z glosami + powiązanymi bez `related_pending` albo z doklejeniem wg reguł 10,
- stara treść bez `examples_pending`: zachowanie jak dziś.

Pomiar kontrolny (gołe API / lokalne, jak 12 listopada): first paint meanings p50 poniżej ~3 s na typowych hasłach; karty bez błędów walidacji; `ready` nie wcześniej niż complete.

## Ryzyka

- `learnable` może wyjść odrobinę później niż przy jednym `enrich_study` (finish czeka na meanings) — przyjęte: zysk jest na earlier paint, nie na fiszce.
- Model finish może próbować przepisać glosy — twarda walidacja + retry.
- Kafelek `pending` z glosami: stare telefony bez tej zmiany nadal pokażą „Tworzę…” do `learnable` — zgodność wstecz OK.
