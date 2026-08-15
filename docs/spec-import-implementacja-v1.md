# Import słówek — specyfikacja techniczna i implementacyjna (v1)

Data: 2026‑08‑11
Powiązany dokument analityczny: `docs/plan-import-refaktor-2026-08-11.md`
Status: **gotowe do implementacji** (decyzje zapadły — patrz §1).

Ten dokument jest kontraktem implementacyjnym: dokładny model stanu, kształt API, schematy, listy zmienianych plików, stringi i18n oraz testy. Agent implementujący powinien trzymać się tego dokumentu; wszystko poza nim wymaga pytania.

---

## 1. Zablokowane decyzje (wejście do implementacji)

| Temat | Decyzja |
|---|---|
| Przepływ | **Zostaje ręczny przegląd/odznaczanie** pozycji przed zapisem. |
| Wybór listy | **Przed** przetwarzaniem (ekran startowy importu). |
| Trwałość zadania | **Singleton (Hilt) + DataStore** — przeżywa nawigację i restart aplikacji. |
| Model AI (layout preserve) | **Jeden „one‑shot” na import**, model konfigurowalny; domyślnie **najmocniejszy model OpenAI** dostępny na koncie. Opus 4.8 (Anthropic) = opcja po dodaniu klucza Anthropic (patrz §7). |
| Limit importu | **Maks. 50 kart** na jeden import (twardy limit UI + backend). Powyżej — blokada z komunikatem. |
| Zwroty/konstrukcje | **Importować** (jako `construction`/`phrase`), ale **wyraźnie oznaczać** w przeglądzie. |
| Dwustronność (preserve) | **Tylko gdy AI pewnie otaguje L2/L1**; inaczej karta jednokierunkowa (l2→l1). |

> Uwaga o modelu: Opus 4.8 nie jest dostępny przez API OpenAI. Dopóki jest tylko konto OpenAI, `llm_import_layout_model` ustawiamy na najmocniejszy model OpenAI (np. najwyższy wariant reasoning GPT‑5 na koncie). Kod ma być provider‑agnostyczny, żeby przełączenie na Opus było zmianą konfiguracji, nie refaktorem.

---

## 2. Docelowy przepływ i maszyna stanów

### 2.1. Przepływ użytkownika

```
[Dodaj] → „Z pliku” / „Wklej”
  → EKRAN STARTOWY IMPORTU (jeden dialog):
        • źródło: plik (nazwa) lub wklejka
        • tryb: „Karty Vocabulario” | „Zachowaj fiszki”
        • lista docelowa: wybór istniejącej / utworzenie nowej
        • [Importuj]
  → walidacja limitu (≤50) — inaczej błąd i powrót
  → PROCESSING (Dodaj zablokowane; spinner + „Analizuję {źródło}…”;
                spinner przy zakładce; [Przerwij] → modal potwierdzenia)
  → REVIEW (modal z listą pozycji: odznaczanie, oznaczone zwroty/konstrukcje,
            sekcja „nierozpoznane”; [Anuluj] / [Zapisz N])
  → COMMITTING (Dodaj zablokowane; „Zaimportowano x/total”; [Przerwij])
  → DONE (modal wyników: „Dodano X, duplikaty Y[, błędy Z]”; [Pokaż listę] / [OK])
```

Blokada „Dodaj” obowiązuje w stanach **Processing** i **Committing** (search/„Z pliku”/„Wklej” niedostępne, komunikat + spinner). Stan **Review** to modal nad ekranem — reszta aplikacji dostępna.

### 2.2. Semantyka licznika (ważne — bez tego UX rozjedzie się z implementacją)
- **Processing**: analiza AI to pojedyncze wywołanie → licznik nieokreślony (spinner + „Analizuję {źródło}…”). Nie udajemy `x/total`.
- **Committing**: `processed/total`, gdzie `total` = liczba zaznaczonych pozycji, `processed` rośnie po każdej utworzonej/pominiętej karcie.
- **DONE** = karty **utworzone**. Enrichment (tryb vocabulario) leci **dalej w tle** i ma własny wskaźnik na kafelkach (istniejący `enrichment_status`/polling). „Koniec importu” ≠ „wszystko wzbogacone”.

### 2.3. Maszyna stanów (kontrakt)

Stany: `Idle | Processing | Review | Committing | Done | Error`.

| Z | Event | Do | Efekty |
|---|---|---|---|
| Idle | `start(source, mode, listId)` | Processing | zapis snapshotu do DataStore; blokada Dodaj |
| Processing | `analyzed(items, invalid)` | Review | `total=items.size` (do committing); modal review |
| Processing | `error(msg)` | Error | odblokowanie; komunikat |
| Processing | `cancel()` (po potwierdzeniu) | Idle | porzucenie; odblokowanie |
| Review | `toggleItem(key)` | Review | aktualizacja `deselectedKeys` |
| Review | `confirm()` | Committing | start zapisu na `targetListId` |
| Review | `cancel()` | Idle | porzucenie |
| Committing | `progress(n)` | Committing | `processed=n` |
| Committing | `done(result)` | Done | modal wyników |
| Committing | `cancel()` (po potwierdzeniu) | Done | stop bezpieczny; wynik częściowy (utworzone zostają) |
| Committing | `error(msg)` | Error | wynik częściowy + komunikat |
| Done | `dismiss()` | Idle | czyszczenie snapshotu |
| Error | `dismiss()` | Idle | czyszczenie snapshotu |

### 2.4. Zasady przywracania po restarcie (DataStore)
Przy starcie aplikacji `ImportController` czyta snapshot i:
- `Idle | Done | Error` → jak zapisano (Done/Error pokazują modal raz, potem Idle).
- `Review` → przywróć modal review (pozycje są w snapshocie; ≤50 kart mieści się swobodnie).
- `Processing` → oznacz jako `Error("Import przerwany — spróbuj ponownie")` (analiza AI nie została dokończona, nic nie zapisano).
- `Committing` → **wznów commit** od nowa dla całej listy zaznaczonych. Jest to bezpieczne, bo backend **pomija duplikaty** (patrz §6.3), więc już utworzone karty nie zduplikują się.

---

## 3. Architektura frontendu (Android)

### 3.1. Nowy komponent: `ImportController` (singleton Hilt)
Plik: `android/app/src/main/java/com/vocabulario/app/data/import/ImportController.kt` (nowy pakiet `data/import`).

- Adnotacja `@Singleton`, wstrzykiwany przez Hilt (rejestracja w `di/AppModule.kt`). Żyje **poza** scope’em nawigacji → przeżywa `key(startRoute)` rebuild w `VocabularioAppRoot`.
- Wystawia `val state: StateFlow<ImportJobState>`.
- Uruchamia pracę we własnym `CoroutineScope(SupervisorJob() + Dispatchers.Default)` (nie `viewModelScope`), żeby nie ginęła z ekranem.
- Zależności: `LearningRepository`, `ImportStatePersistence` (DataStore), `UiStrings`, `NetworkMonitor`.

```kotlin
enum class ImportStatus { Idle, Processing, Review, Committing, Done, Error }

data class ImportResult(val created: Int, val duplicates: Int, val failed: Int)

data class ImportJobState(
    val status: ImportStatus = ImportStatus.Idle,
    val sourceName: String? = null,        // nazwa pliku lub etykieta „Wklejka”
    val mode: String = "vocabulario",      // vocabulario | preserve
    val targetListId: String? = null,      // wybrana z góry
    val targetListName: String? = null,
    val processed: Int = 0,
    val total: Int = 0,
    val valid: List<ImportValidWord> = emptyList(),          // tryb vocabulario
    val displayCards: List<ImportDisplayCard> = emptyList(),  // tryb preserve
    val invalid: List<String> = emptyList(),
    val deselectedKeys: Set<String> = emptySet(),            // odznaczone w review
    val result: ImportResult? = null,
    val error: String? = null,
) {
    val busy: Boolean get() = status == ImportStatus.Processing || status == ImportStatus.Committing
    val selectedCount: Int
        get() = when (mode) {
            "preserve" -> displayCards.count { it.key !in deselectedKeys }
            else -> valid.count { it.input !in deselectedKeys }
        }
}
```

API publiczne kontrolera:
```kotlin
fun startFromFile(bytes: ByteArray, filename: String, mode: String, listId: String, listName: String)
fun startFromPaste(text: String, mode: String, listId: String, listName: String)
fun toggleItem(key: String)
fun requestCancel()          // UI pokazuje modal potwierdzenia
fun confirmCancel()
fun confirmCommit()
fun dismissResult()          // Done/Error → Idle
```

Reguły:
- Limit: jeśli po analizie `valid.size + invalid.size > 50` **lub** wejściowa liczba pozycji > 50 → `Error(import_limit_exceeded)`. Twardy limit egzekwuje też backend (§6.1); front sprawdza wcześnie dla UX.
- `startFromFile/Paste` odrzucane, gdy `status.busy` (idempotencja).
- Anulowanie w `Committing` przerywa pętlę po bieżącym elemencie; już utworzone zostają; wynik = częściowy.

### 3.2. Persystencja: `ImportStatePersistence`
Plik: `data/import/ImportStatePersistence.kt`. DataStore (Preferences lub Proto). Serializacja `ImportJobState` do JSON (`kotlinx.serialization`). Zapis przy każdej istotnej zmianie stanu; odczyt w `init` kontrolera. `ImportResult`/duże listy ≤50 → rozmiar znikomy, można trzymać w całości.

### 3.3. Zmiany w `HomeViewModel` / `HomeScreen`
- `HomeViewModel` **wstrzykuje** `ImportController` i **eksponuje** `val importState = importController.state`. Usuwa własne pola `import*` z `HomeUiState` oraz metody: `startImportFromText`, `startImportFromFileText`, `startImportFromFileBytes`, `validateImport`, `applyImportResult`, `applyImportDisplayResult`, `removeImportWord`, `removeImportDisplayCard`, `cancelImport`, `openImportDestination`, `dismissImportDestination`, `commitImportToLearning`, `commitImportToList`, `commitDisplayImportToList`, `createListAndCommitImport`. Logika przenosi się do `ImportController`.
- `search()` guard: `if (importController.state.value.busy) return` (zamiast `if (importActive)`).
- `HomeScreen` obserwuje `importState` przez `collectAsState()` i renderuje:
  - **panel blokady** w `AddTab` gdy `busy` (spinner + label + `[Przerwij]`),
  - **spinner przy zakładce „Dodaj”** gdy `busy` (rozszerzyć `HomeTabs(importBusy = importState.busy)` — dziś `importJobActive`, patrz `HomeScreen.kt:200`, `:518`, `:557`),
  - **modal Review** gdy `status == Review`,
  - **modal potwierdzenia przerwania** (steruje `ImportController.requestCancel/confirmCancel`),
  - **modal wyników** gdy `status == Done` — renderowany na poziomie roota (`VocabularioAppRoot`), by był widoczny nad każdą trasą (wymaganie 5c).

### 3.4. Ekran startowy importu (jeden dialog)
Zastępuje obecną sekwencję dialogów (`showFileDialog` → `showModeDialog` → osobny `AddToListSheet`). Jeden dialog z: wybór pliku/pokazanie nazwy, wybór trybu (radio), wybór listy (dropdown + „Nowa lista”), przycisk „Importuj”. Po zatwierdzeniu woła `ImportController.startFromFile/Paste(..., listId, listName)`.

### 3.5. Modal Review
Lista pozycji (`valid` lub `displayCards`) z checkboxami (odznaczanie → `toggleItem`). Sekcje: „Do zaimportowania”, „Zwroty/konstrukcje” (oznaczone `entry_kind ∈ {construction, phrase, sentence}`), „Nierozpoznane” (`invalid`, tylko podgląd). Stopka: `[Anuluj]` / `[Zapisz {selectedCount}]` → `confirmCommit`. Dla preserve używać `ImportDisplayFlip` jako podglądu.

### 3.6. TestTags (rozszerzyć `ui/TestTags.kt`)
Zachować istniejące (`BTN_IMPORT_FILE/PASTE`, `IMPORT_MODE_VOCAB/PRESERVE`, `BTN_IMPORT_CONFIRM/CANCEL`, `IMPORT_PASTE_INPUT`). Dodać:
`IMPORT_START_DIALOG`, `IMPORT_LIST_PICKER`, `IMPORT_BTN_START`, `IMPORT_STATUS_PANEL`, `IMPORT_BTN_ABORT`, `IMPORT_ABORT_CONFIRM`, `IMPORT_REVIEW_MODAL`, `IMPORT_REVIEW_ITEM`, `IMPORT_RESULT_MODAL`, `IMPORT_RESULT_OK`.

---

## 4. Frontend — renderer preserve (display v2)

### 4.1. Zamknięty słownik bloków (kontrakt renderera)
`ImportDisplayBlockView` (`ui/components/ImportDisplayBlocks.kt`) obsługuje **tylko** te typy:
`headword | gloss | bilingual | list | table | note | chip | section | divider | text`.
Nieznany `type` → render jako `text` (oczyszczony). **Nigdy** surowy HTML.

Mapowanie starych typów zachować wstecznie: `title`→`headword`/`gloss` (wg `emphasis`/`size`), `paragraph`/`pre`→`text`, `meta`→`chip`.

### 4.2. Rozszerzenie modelu `ImportDisplayBlock` (`data/api/Models.kt`)
Dodać pola (nullable, z domyślnymi null → wsteczna zgodność):
```kotlin
val align: String? = null,       // "start" | "center"
val size: String? = null,        // "display" | "lemma" | "gloss" | "body" | "caption"
val semantic: String? = null,    // "headword" | "translation" | "example" | "note" | "conjugation" | "pronunciation" | "tags"
val tts: ImportTts? = null,      // { enabled: Boolean, lang: String? }
```
`parseBlock` w `ImportDisplayBlocks.kt` musi odczytać nowe pola (dodać do parsera). `size`→typografia MD3, `align`→wyrównanie, `tts.enabled`→ikona odtwarzania (reuse `TtsSpeak.kt`). Stylistyka spójna z `CardDetailContent` (te same nagłówki sekcji, chipy, odstępy).

### 4.3. Bidirectional na froncie
Practice już obsługuje `direction` (`PracticeScreen.kt:101`). Dla kart preserve dwustronność zależy od pola `bidirectional` w treści (§6.4). Front nie wymaga zmian w praktyce poza tym, że karty `bidirectional=false` nie wejdą w kierunek `l1_to_l2` (decyduje backend przy budowie kolejki, §6.4).

---

## 5. Backend — parsowanie i deterministyka

### 5.1. Warstwa deterministyczna przed AI (HTML → bloki)
W `services/import_package.py` / `services/import_display.py` dodać parser zachowujący strukturę zamiast płaskiego `strip_html`:
- `<table>` → blok `table` (`headers` z pierwszego wiersza `<th>`/pierwszego rzędu, `rows` z reszty). Kluczowe dla koniugacji Anki (`class="pron"/"form"`).
- `<ul>/<ol>/<li>` → blok `list` (`items`).
- `<br>`, `<p>`, `<div>` → podział na akapity/linie (już częściowo w `strip_html`).
- `<b>/<strong>` → zachować jako `emphasis` na poziomie tekstu (opcjonalnie; nie krytyczne).
Reszta HTML (script/style) → usuwana (już jest).

### 5.2. Drabinka degradacji (bez AI → AI → heurystyka → fallback)
Kolejność w `resolve_import_display_cards`:
1. Znane pola (Anki notes/`field_names`) → precyzyjne role.
2. `analyze_import_layout` (AI, §7) → role + intencja prezentacji.
3. Heurystyka `_mock_display_analysis` (istnieje) jako fallback przy awarii/niepewności AI.
4. Ostateczność: jedna sekcja `text` (oczyszczona) — nigdy surowy HTML.

---

## 6. Backend — endpointy, limity, commit, dwustronność

### 6.1. Twardy limit 50 kart
W `api/v1/learning.py` dla `/imports/ingest`, `/imports/file`, `/imports/validate` (oraz `/imports/commit-*`): po odczycie/segmentacji, jeśli liczba pozycji (notatek / valid+invalid / kart) `> 50` → `HTTPException(400, detail_code="import_limit_50")`. Zastąpić istniejące limity 2000 (`learning.py:219,237,283`).

### 6.2. Nowy endpoint commit vocabulario (batch, z raportem)
`POST /imports/commit-vocabulario` → body `{ profile_id, list_id, words: List[ImportValidWord] }`, zwrot `ImportCommitResponse { created, duplicates, failed, list_id }`.
- Dla każdego słowa: `find_card_anywhere(...)` → jeśli istnieje: `duplicates++` i pomiń; inaczej utwórz `LearningCard` (status `pending`, enrichment w tle jak dziś przez `add_word_to_list`/`card_jobs`), `created++`. Wyjątek inny niż duplikat: `failed++`.
- Jedna transakcja / batch; enrichment kolejkowany w tle (bez czekania).
- Front (`ImportController`) woła ten endpoint i mapuje wynik na `ImportResult`. Postęp `x/total`: albo endpoint zwraca całość (wtedy `processed` skacze do `total` po odpowiedzi), albo — dla płynnego licznika przy ≤50 — commit wykonujemy **po stronie klienta pętlą** po `addWordToList` z obsługą `409=duplikat` (patrz §6.3). **Rekomendacja:** klient pętli po `addWordToList` (prostsze, daje płynny licznik przy ≤50), a `409` liczy jako duplikat.

> Decyzja implementacyjna: przy limicie 50 kart pętla klienta po `addWordToList` jest wystarczająca i daje licznik `x/total` „za darmo”. Nowy endpoint batch jest opcjonalny (nice‑to‑have). MVP: pętla klienta + mapowanie `409 → duplicates`.

### 6.3. Duplikaty
`add_word_to_list` zwraca `409` dla duplikatu (`learning.py:1147‑1149`). `commit-display` już liczy `skipped` przez `find_card_anywhere` (`learning.py:323‑327`). Ujednolicić raport: vocab (klient) mapuje `409 → duplicates`, inne błędy → `failed`. Commit jest **idempotentny** (ponowny import pomija istniejące) — to jest podstawa reguły wznawiania z §2.4.

### 6.4. Dwustronność kart preserve
- `build_import_display_content` (`services/card_jobs.py:69`) ustawia `lemma_l2` i `gloss_primary` z bloków oznaczonych `semantic=headword` (L2) i `semantic=translation` (L1).
- Dodać do `content` pole `bidirectional: bool` = `true` tylko gdy AI pewnie otagowało oba (`headword` + `translation`); inaczej `false`.
- W budowie kolejki SRS (`api/v1/learning.py` `_resolve_direction` / generowanie itemów, ~`:484‑536`): dla kart z `content.display.bidirectional == false` wymuszać kierunek `l2_to_l1` (nie losować `l1_to_l2`). `collect_acceptable_answers` (`services/answer_check.py:91`) działa na `meanings`/`lemma`, więc dla poprawnie otagowanych kart obie strony mają dane.

---

## 7. Backend — AI: one‑shot layout + wybór modelu

### 7.1. Jeden request na import (tryb preserve)
Nowa metoda `analyze_import_layout` w `services/llm.py` łącząca to, co dziś robią `analyze_import_format` + `analyze_import_display` (+ ewentualnie answer‑structure), w **jedno** wywołanie:
- Wejście: cała próbka (przy ≤50 kart mieści się w kontekście) + `field_names` + para językowa.
- Wyjście: JSON = segmentacja (jeśli potrzebna) **i** szablon display v2 (`prompt_blocks`/`answer_blocks` z `field_index`, `align`, `size`, `semantic`, `tts`).
- Dla źródeł już posegmentowanych (Anki notes/apkg) segmentacja pomijana — nadal jeden call (tylko layout).
- Tryb vocabulario: klasyfikacja pozostaje, ale przy ≤50 to jeden batch — podnieść `_BATCH` w `import_classify.py` do ≥50, żeby był jeden call.

### 7.2. Konfiguracja modelu (per‑zadanie, provider‑agnostyczna)
W `core/config.py` dodać:
```python
llm_import_layout_model: str = ""     # pusty → użyj llm_lookup_model
llm_import_provider: str = "openai"   # "openai" | "anthropic"
anthropic_api_key: str = ""
```
- Domyślnie (puste) → obecny klient OpenAI i `llm_lookup_model`. Zalecane ustawienie: `LLM_IMPORT_LAYOUT_MODEL=<najmocniejszy model OpenAI na koncie>` (jeden call na import → koszt znikomy).
- `LLMService._chat_json` rozbić o wybór providera: dla `openai` bez zmian; dla `anthropic` dodać gałąź z klientem Anthropic i wymuszeniem JSON (tool use / prefill), bo Anthropic nie ma `response_format=json_schema` 1:1.
- **Twarda walidacja wyjścia**: parsuj JSON → waliduj schematem display v2 → przy niezgodności retry (1×) → fallback do heurystyki `_mock_display_analysis` (§5.2 p.3). Dotyczy każdego providera.

> Aby użyć **Opus 4.8**: ustaw `LLM_IMPORT_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`, `LLM_IMPORT_LAYOUT_MODEL=<slug Opus 4.8>`. Bez klucza Anthropic zostaje najlepszy model OpenAI.

### 7.3. Schemat display v2 (`ai/schemas/import_display.py`)
Rozszerzyć `_leaf_block_props()` o: `align` (`start|center|null`), `size` (`display|lemma|gloss|body|caption|null`), `semantic` (enum j.w. `|null`), `tts` (obiekt `{enabled: bool, lang: string|null}` lub null). Dodać do `_LEAF_REQUIRED` (schema strict OpenAI wymaga wszystkich kluczy). Na wierzchu odpowiedzi dodać `bidirectional: bool`.

### 7.4. Prompt (`ai/prompts/v1.py`)
Zaktualizować `IMPORT_DISPLAY_PROMPT_V1`/`SYSTEM` (lub nowy `IMPORT_LAYOUT_*`) zgodnie z §13 planu analitycznego + reguły: zamknięty słownik bloków, `semantic=headword/translation`, `tts` dla pól L2, tabele HTML → `table`, `align/size`, „na froncie max 1 tytuł”, `bidirectional`.

---

## 8. i18n — nowe klucze (dodać we wszystkich `values-*`)

Istnieją (reuse): `import_online_only`, `import_how`, `import_vocab_mode`, `import_preserve_mode`, `err_import*`, `msg_import_result`, `import_progress`.
Dodać:
- `import_start_title` — „Import fiszek”
- `import_pick_list` — „Lista docelowa”
- `import_action_start` — „Importuj”
- `import_limit_exceeded` — „Na razie możesz zaimportować maksymalnie 50 kart.”
- `import_status_analyzing` — „Analizuję %1$s…” (źródło)
- `import_status_importing` — „Import słówek z pliku %1$s”
- `import_progress_count` — „Zaimportowano %1$d/%2$d”
- `action_abort` — „Przerwij”
- `import_abort_title` — „Przerwać import?”
- `import_abort_body` — „Postęp zostanie porzucony.”
- `import_result_title` — „Import zakończony”
- `import_result_body` — „Dodano %1$d, duplikaty %2$d”
- `import_result_body_failed` — „Dodano %1$d, duplikaty %2$d, błędy %3$d”
- `import_review_flagged` — „Zwroty i konstrukcje”
- `action_show_list` — „Pokaż listę”

Baza: `android/app/src/main/res/values/strings.xml` + tłumaczenia w pozostałych `values-*`.

---

## 9. Lista zmienianych/nowych plików

Frontend:
- NOWE: `data/import/ImportController.kt`, `data/import/ImportStatePersistence.kt`, `data/import/ImportModels.kt` (stany).
- ZMIANA: `ui/home/HomeViewModel.kt` (usunięcie logiki importu, delegacja), `ui/home/HomeScreen.kt` (ekran startowy, panel blokady, modale review/abort/result, spinner zakładki), `ui/VocabularioAppRoot.kt` (modal wyników na poziomie roota), `data/api/Models.kt` (display v2: `align/size/semantic/tts`, `ImportTts`, `ImportCommitResponse`), `ui/components/ImportDisplayBlocks.kt` (nowe typy/pola, styl spójny), `data/LearningRepository.kt` (mapowanie `409→duplicate`, ew. nowy endpoint), `data/api/VocabularioApi.kt` (ew. `commit-vocabulario`), `ui/TestTags.kt`, `di/AppModule.kt` (provide `ImportController`), `res/values*/strings.xml`.
- USUNĄĆ: `data/ImportTextParser.kt`, `ui/add/AddWordScreen.kt`, `ui/add/AddWordViewModel.kt` (martwe; potwierdzić brak referencji).

Backend:
- ZMIANA: `api/v1/learning.py` (limit 50; ew. `commit-vocabulario`; kierunek dla `bidirectional=false`), `services/llm.py` (`analyze_import_layout`, provider switch, walidacja), `core/config.py` (nowe pola), `ai/prompts/v1.py` (prompt), `ai/schemas/import_display.py` (v2), `services/import_display.py` (parser HTML tabel, degradacja, `bidirectional`), `services/import_classify.py` (`_BATCH≥50`), `services/card_jobs.py` (`build_import_display_content`: `semantic`→`lemma_l2`/`gloss_primary`, `bidirectional`).

---

## 10. Testy

Backend (pytest, próbki z `Desktop/` → skopiować do `backend/tests/fixtures/import/`):
- `quizlet1.txt` (TSV) → N kart, poprawne pary.
- `quizlet2.txt` (jedna linia `,`/`;`) → poprawna segmentacja (N, nie 1).
- `quizlet3.txt` (zwroty) → `entry_kind ∈ {construction, phrase}`, oznaczone, nie `invalid`.
- `Testowa.txt` (Anki notes) → headword = pole słowa; tabela koniugacji → blok `table` (nie `pre`).
- `Testowa2.txt` (Anki cards HTML) → lemma z `front-word`; brak JS/CSS w wyjściu.
- `.apkg` → happy path + jasny błąd `anki21b`.
- Limit: 51 pozycji → `400 import_limit_50`.
- Duplikaty: powtórzone hasła → `duplicates`, nie `failed`.
- display v2: walidacja schematu; fallback przy „zepsutym” JSON z modelu.
- bidirectional: karta z pewnym L2/L1 → `bidirectional=true`; niejednoznaczna → `false` + kierunek l2→l1.

Frontend (unit + Compose):
- `ImportController`: przejścia stanów (start→Processing→Review→Committing→Done), guardy busy, `toggleItem`, anulowanie (częściowy wynik), limit 50.
- Persystencja: restart w `Review` → modal wraca; w `Committing` → wznowienie idempotentne.
- Blokada „Dodaj” w `busy`; spinner zakładki; modal wyników nad każdą trasą.

E2E (maestro): import pliku → zmiana zakładki/trasy w trakcie → powrót → nadal zablokowane, licznik rośnie → modal wyników → „Pokaż listę”.

---

## 11. Kolejność wdrożenia (milestones)

1. **M1 — cykl życia (naprawa BUG #1):** `ImportController` + `ImportJobState` + DataStore + delegacja z `HomeViewModel` + ekran startowy + panel blokady + spinner zakładki + modal abort + modal wyników. Commit vocab = pętla klienta z `409→duplicate`. (Bez zmian AI.)
2. **M2 — limit i raport:** twardy limit 50 (front+back), raport `created/duplicates/failed`, ujednolicenie duplikatów.
3. **M3 — jakość preserve:** display v2 (schemat + model Models.kt + renderer), parser HTML tabel, degradacja, `analyze_import_layout` one‑shot + wybór modelu (domyślnie najmocniejszy OpenAI), walidacja/fallback.
4. **M4 — dwustronność preserve:** `semantic`→`lemma_l2/gloss_primary`, `bidirectional`, kierunek w kolejce SRS.
5. **M5 — sprzątanie i testy:** usunięcie kodu martwego, komplet testów na próbkach, i18n we wszystkich `values-*`.

Zależności: M1 niezależny (najpierw). M3 zależy od M1 (stan) i jest niezależny od M2. M4 zależy od M3 (semantic). M5 na końcu.

---

## 12. Definicja ukończenia (DoD)
- Zmiana widoku/tras w trakcie importu **nie przerywa** zadania; po powrocie „Dodaj” nadal zablokowane z licznikiem.
- Restart aplikacji w trakcie: `Review` wraca, `Committing` wznawia się bez duplikatów.
- „Przerwij” + potwierdzenie działa w Processing i Committing.
- Po zakończeniu: modal wyników niezależnie od ekranu; „Dodaj” odblokowane.
- Import > 50 kart zablokowany z czytelnym komunikatem.
- Karty vocabulario: pełne karty (enrichment w tle); duplikaty raportowane.
- Karty preserve: render spójny ze stylem Vocabulario (tabele koniugacji jako `table`, nie monospace); dwustronność działa dla pewnie otagowanych kart.
- Wszystkie testy §10 zielone.

---

## 13. Prompt dla agenta implementującego

> Skopiuj poniższe jako zadanie dla osobnego agenta. Agent ma trzymać się `docs/spec-import-implementacja-v1.md` (ten dokument) i `docs/plan-import-refaktor-2026-08-11.md`.

```
Rola: Jesteś agentem implementującym feature „Import słówek” w aplikacji Vocabulario
(Android/Kotlin + Compose, backend FastAPI/Python). Repo: c:/Users/masaw/devetene/tene-app/vocabulario.

Źródło prawdy: docs/spec-import-implementacja-v1.md (kontrakt) oraz
docs/plan-import-refaktor-2026-08-11.md (kontekst). Nie odstępuj od decyzji z §1 specu.
Cokolwiek nie jest w dokumentach — zapytaj, nie zgaduj.

Zasady twarde:
- Limit importu = 50 kart (front + backend), komunikat import_limit_exceeded.
- Model AI layoutu = JEDEN request na import; konfigurowalny (llm_import_layout_model),
  domyślnie najmocniejszy model OpenAI. NIE zakładaj dostępu do Anthropic/Opus —
  kod ma być provider-agnostyczny, ale domyślnie działa na OpenAI. Zawsze waliduj JSON
  wyjścia schematem i miej fallback do heurystyki.
- Zadanie importu żyje w singletonie Hilt (ImportController) poza scope'em nawigacji,
  ze stanem trwałym w DataStore (przeżywa nawigację i restart). Commit jest idempotentny
  (duplikaty pomijane), więc wznowienie po restarcie jest bezpieczne.
- Zostaje ręczny krok Review (odznaczanie); lista docelowa wybierana PRZED przetwarzaniem.
- Dwustronność preserve tylko gdy AI pewnie otaguje L2/L1 (semantic headword/translation),
  inaczej bidirectional=false i kierunek l2_to_l1.
- Zwroty/konstrukcje importujemy, ale oznaczamy w Review.

Kolejność pracy = milestones z §11 (M1→M5). Po KAŻDYM milestone:
1) uruchom właściwe testy (backend: pytest w backend/; frontend: gradle testDebugUnitTest),
2) napraw lint/build, 3) zaraportuj krótko co zrobione + co dalej. Nie łącz milestones.

M1 najpierw (naprawa buga cyklu życia) — jest niezależny od zmian AI.

Pliki do zmiany/utworzenia: patrz §9 specu. Stringi: dodaj klucze z §8 w
android/app/src/main/res/values/strings.xml oraz wszystkich values-*/ (spójne tłumaczenia;
jeśli nie znasz języka, użyj angielskiego fallbacku i oznacz TODO).

Testy i próbki: skopiuj pliki z Desktop (quizlet1/2/3.txt, Testowa.txt, Testowa2.txt,
Testowa.apkg) do backend/tests/fixtures/import/ i oprzyj na nich testy z §10.

Definicja ukończenia: §12 specu. Nie commituj bez wyraźnej prośby użytkownika.
Zachowaj istniejące TestTags i dodaj nowe z §3.6.
```
