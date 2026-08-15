# Import słówek (plik / wklejka) — analiza i plan udoskonalenia

Data: 2026‑08‑11
Autor analizy: przegląd kodu end‑to‑end (Android + backend) na podstawie próbek Anki/Quizlet.
Status: **analiza + plan** (bez zmian w kodzie).

Cel dokumentu: rzetelnie opisać jak dziś działa import, gdzie leżą błędy (w szczególności blokada/przerywanie importu przy zmianie widoku), oraz zaproponować kompletny plan naprawy dwóch rzeczy:

1. **UX i cykl życia importu** — import ma być odpornym zadaniem w tle, blokującym zakładkę „Dodaj”, ze spinnerem, licznikiem `x/total`, przyciskiem „Przerwij” i modalem wyników.
2. **Jakość kart** — poprawny import do formatu **kart Vocabulario** (pełny enrichment) oraz ładny import „w oryginale” (**preserve**) z lepszym promptem i strukturą karty.

---

## 1. Słownik pojęć

- **Tryb `vocabulario`** — z par (słowo L2 / tłumaczenie) aplikacja tworzy **własne, wzbogacone karty** (enrichment AI: znaczenia, przykłady, koniugacja itd.). Renderowane przez `CardDetailContent`.
- **Tryb `preserve`** — zachowanie fiszki „w oryginale”; AI analizuje layout i buduje `display.blocks` (front/back). Renderowane przez `ImportDisplayBlocks`.
- **Ingest / validate** — faza parsowania + analizy AI, która zwraca listę pozycji do przeglądu.
- **Commit** — faza zapisu zaakceptowanych pozycji na wybraną listę.
- **`RawImportDeck`** — surowa struktura po odczycie pliku/wklejki (przed mapowaniem pól).

---

## 2. Jak import działa dziś (architektura end‑to‑end)

### 2.1. Mapa plików

Frontend (Android / Compose):
- `ui/home/HomeScreen.kt` — cały UI importu żyje w zakładce **`HomeTab.ADD`** (a nie w `AddWordScreen.kt`!). Zawiera: przyciski „Z pliku” / „Wklej”, file picker (`OpenDocument`), dialog wyboru trybu, panel przeglądu, dolny pasek akcji, pasek postępu `ImportProgressBar`, spinner przy zakładce.
- `ui/home/HomeViewModel.kt` — **jedyne źródło logiki importu**. Stan trzymany w `HomeUiState` (pola `import*`). Metody: `startImportFromText`, `startImportFromFileBytes`, `validateImport`, `applyImportResult`, `applyImportDisplayResult`, `commitImportToList`, `commitDisplayImportToList`, `cancelImport`, `openImportDestination`.
- `ui/components/ImportDisplayBlocks.kt` — renderer trybu preserve (`ImportDisplayFlip`, `ImportDisplayBlockView`) + parser `parseImportDisplayFromContent`.
- `data/LearningRepository.kt` — wywołania API: `ingestImport`, `ingestImportPreserve`, `ingestImportFile`, `ingestImportFilePreserve`, `commitImportDisplay`, `validateImport`, `addWordToList`.
- `data/ImportTextParser.kt` — **kod martwy/legacy** (patrz §5.7).
- `ui/add/AddWordScreen.kt` + `AddWordViewModel.kt` — **nie są w grafie nawigacji** (`Routes` nie ma `ADD`); to legacy, nie obsługuje importu.

Backend (FastAPI):
- `api/v1/learning.py` — endpointy: `POST /imports/validate`, `POST /imports/ingest`, `POST /imports/file`, `POST /imports/commit-display`.
- `services/import_package.py` — odczyt plików: `.apkg/.colpkg` (SQLite w ZIP), TSV/CSV/TXT, Anki Notes, Anki Cards HTML; deterministyczna segmentacja `apply_import_format`.
- `services/import_format.py` — AI: surowy tekst → instrukcja segmentacji (`ensure_deck_segmented`).
- `services/import_classify.py` — AI: notatki → `entry_kind` + `headword_l2` (tryb vocabulario).
- `services/import_display.py` — AI + heurystyki: role pól + bloki UI (tryb preserve).
- `services/import_urls.py` — import z URL (Quizlet / AnkiWeb).
- `services/llm.py` — `analyze_import_format`, `analyze_import_classify`, `analyze_import_display`, `analyze_import_answer_structure`.
- `ai/prompts/v1.py` — prompty `IMPORT_FORMAT_*`, `IMPORT_CLASSIFY_*`, `IMPORT_DISPLAY_*`, `IMPORT_ANSWER_STRUCTURE_*`.
- `ai/schemas/import_display.py`, `import_format.py`, `import_classify.py` — JSON schemas.

### 2.2. Przepływ (obecny)

```
[Dodaj] → „Z pliku” / „Wklej”
      → (plik) OpenDocument → bytes+nazwa   |  (tekst) dialog wklejki
      → dialog trybu: „Karty Vocabulario” | „Zachowaj fiszki”
      → FAZA INGEST (loading=true, spinner w AddTab)
             vocabulario: /imports/ingest|file  → valid[] + invalid[]
             preserve:    /imports/ingest|file  → displayCards[]
      → FAZA PRZEGLĄD (importActive=true): lista kafelków w AddTab
             + dolny pasek: [Anuluj] [Zatwierdź]
      → „Zatwierdź” → AddToListSheet (wybór/utworzenie listy)
      → FAZA COMMIT:
             vocabulario: pętla addWordToList (importProgress=index/total),
                          tab→DASHBOARD, ImportProgressBar u góry, spinner przy zakładce
             preserve:    /imports/commit-display (jeden strzał; progress 0.15→1)
      → koniec: importJobActive=false; wynik jako tekst (notice/error), BEZ modala
```

### 2.3. Model stanu (fragmentaryczny — to jest źródło problemów)

W `HomeUiState` współistnieje **pięć** niezależnych flag opisujących „czy trwa import”:

```37:65:android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt
    val loading: Boolean = false,
    ...
    val importActive: Boolean = false,
    val importMode: String = "vocabulario", // vocabulario | preserve
    val importValid: List<ImportValidWord> = emptyList(),
    val importDisplayCards: List<ImportDisplayCard> = emptyList(),
    val importInvalid: List<String> = emptyList(),
    val importCommitting: Boolean = false,
    val importDestinationOpen: Boolean = false,
    /** Import w tle (po wyjściu na dashboard). */
    val importJobActive: Boolean = false,
    val importProgress: Float = 0f,
    val importTargetListId: String? = null,
```

Nie ma jednego, spójnego obiektu „ImportJob”. `loading` służy jednocześnie do wyszukiwania i ingestu; `importActive` do przeglądu; `importJobActive` do commitu. Każda faza używa innej flagi i inaczej blokuje (albo nie blokuje) UI.

---

## 3. Analiza formatów wejściowych (na podstawie próbek)

| Plik | Format | `kind` po odczycie | Ryzyko / uwagi |
|---|---|---|---|
| `quizlet1.txt` | TSV `term⇥def` (30 słów) | `plain`/`notes` | OK. Czyste pary. |
| `quizlet2.txt` | Jedna linia `term,def;term,def;…` (Quizlet „Exportar”) | `raw_text`/`notes` | **Wymaga AI‑formatu**: `card_separator=semicolon`, `field_delimiter=comma`, `field_split=first_only`. Bez tego cała talia = 1 karta. Fallback mock to ogarnia; realny LLM też. |
| `quizlet3.txt` | TSV `term⇥def` (15 **zwrotów**, np. `volver a hacer algo`) | `notes` | Klasyfikacja → `construction`/`phrase`. App „na razie tylko słowa” → zwroty pójdą jako konstrukcje (adaptive enrichment). Do świadomej decyzji. |
| `Testowa.txt` | **Anki Notes** (`#separator:tab`, `#guid/#notetype/#deck/#tags column`), `#html:true` | `notes` | Dobrze parsowane; kolumny guid/notetype/deck/tags pomijane. Pole 3 = słowo, pole 4 = gloss+przykład ES+PL, pole 5 = wzorzec (`e→ie`), pole 6 = **ogromna tabela HTML koniugacji**. |
| `Testowa2.txt` | **Anki Cards** (eksport szablonów HTML z `<script>` TTS, `class="front-word"`) | `cards_html` | Najtrudniejszy. Zawiera JS/CSS. Ekstrakcja lemma po `class=front-word/answer-word`. Preserve 1:1 = brzydko. |
| `Testowa.apkg` | Pakiet Anki (ZIP + SQLite) | `anki_package` | Ryzyko `collection.anki21b` (skompresowany) → jawny błąd z prośbą o eksport Notes/`.apkg` desktop. |

Wnioski kluczowe:
- **Eksport „Notes” (`.txt`) i `.apkg` desktop** są najbezpieczniejsze; **eksport „Cards” (HTML) i `anki21b`** są problematyczne — trzeba to komunikować użytkownikowi.
- Talie Anki dla czasowników **już zawierają gotową tabelę koniugacji w HTML** (`class="pron"/"form"`, nagłówki „Presente”, „Pretérito indefinido”…). Dziś w trybie preserve ta tabela jest spłaszczana do `pre` (monospace) → wygląda źle, mimo że to strukturalne dane, które Vocabulario samo potrafi ładnie renderować (patrz §6.3).

---

## 4. BUG #1 — „podczas importu nie można zmienić widoku; import się przerywa”

### 4.1. Co realnie się dzieje w kodzie

Import **nie jest** modelowany jako trwałe zadanie. Konsekwencje:

1. **Faza ingest (`loading=true`)** to jedno długie wywołanie backendu (parsowanie + kilka wywołań LLM: format → classify/display → answer‑structure). Dla dużych talii to 10–60 s. W tym czasie:
   - UI **nie blokuje** przełączania zakładek ani ponownego wyszukiwania/wklejania. `selectTab()` nie czyści stanu importu, ale też go nie chroni.
   - Gdy ingest kończy się, `applyImportResult()` / `applyImportDisplayResult()` ustawia `importActive=true`, ale **nie ustawia `tab`**. Jeśli user jest na innej zakładce, panel przeglądu (renderowany tylko w `AddTab`) jest niewidoczny, a na dole ekranu pojawia się „wiszący” pasek [Anuluj]/[Zatwierdź] nad Dashboardem. Z perspektywy użytkownika: „nic się nie stało / import się zepsuł”.

```217:235:android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt
    fun selectTab(tab: HomeTab) {
        val leavingAdd = _state.value.tab == HomeTab.ADD && tab != HomeTab.ADD
        _state.value = _state.value.copy(
            tab = tab,
            ... // czyści query/candidates/addTarget/pickList — ale NIE stan importu
        )
```

2. **Faza commit (vocabulario)** jawnie przełącza na `DASHBOARD` i **kasuje `importActive`**:

```683:717:android/app/src/main/java/com/vocabulario/app/ui/home/HomeViewModel.kt
            _state.value = _state.value.copy(
                importActive = false,
                ...
                tab = HomeTab.DASHBOARD,
                importJobActive = true,
                importProgress = 0f,
                ...
            )
            var failed = 0
            words.forEachIndexed { index, w ->
                runCatching { repository.addWordToList(...) }.onFailure { failed++ }
                _state.value = _state.value.copy(importProgress = (index + 1).toFloat() / total)
            }
```

   W tej fazie `AddTab` **nie jest zablokowana** (`importActive=false`), więc użytkownik może wejść w „Dodaj” i **rozpocząć nowe wyszukiwanie/import** równolegle z trwającym commitem → wyścig i nadpisanie stanu.

3. **Brak trwałości / odporności**: cały stan importu żyje wyłącznie w pamięci `HomeViewModel`. `HomeViewModel` jest scope’owany do wpisu grafu `HOME`. Przejście do `Settings`/`Practice` (osobne trasy) samo w sobie go nie niszczy, ale:
   - `PairSwitchHost { key(startRoute) { NavHost … } }` — **zmiana `startRoute` przebudowuje cały graf** (i niszczy `HomeViewModel`). Zmiana profilu językowego / re‑bootstrap w trakcie importu = utrata zadania.
   - Śmierć procesu / restart Activity (np. gdy systemowy file‑picker jest na wierzchu na słabszym sprzęcie) = utrata zadania. Nic nie zapisuje postępu.
   - Wywołania są pojedynczymi, długimi żądaniami HTTP bez wznawiania — timeout ubija fazę bez śladu.

### 4.2. Wniosek (root cause)

Przyczyną „przerywania importu i braku reakcji” jest **brak modelu trwałego zadania importu** oraz **niespójne blokowanie UI**: różne fazy używają różnych flag, faza przeglądu nie wymusza powrotu na zakładkę „Dodaj”, a faza commitu nie blokuje ponownego użycia „Dodaj”. Do tego długie, jednorazowe wywołania AI bez postępu i bez odporności na rekompozycję/rebuild grafu/śmierć procesu.

---

## 5. Pozostałe zidentyfikowane braki i długi techniczne

- **5.1. Brak licznika `x/total` w fazie processingu.** Backend zwraca całą listę „na raz” (ingest = jeden strzał). Licznik postępu istnieje **tylko** w commit‑vocabulario (`index/total`). Wymaganie użytkownika („Zaimportowano x/liczba”) dotyczy fazy przetwarzania — więc dziś nie da się go pokazać bez zmiany modelu (streaming/batch albo job w tle z postępem).
- **5.2. Brak modala wyników.** Po commit jest tylko tekst (`msg_import_result` dla preserve, `err_add_partial` dla vocab). Brak modala „dodano X, duplikatów Y”.
- **5.3. Raport duplikatów niespójny.** `preserve` zwraca `created/skipped` (deduplikacja przez `find_card_anywhere`). `vocabulario` liczy tylko `failed`, **nie** rozróżnia duplikatów od błędów.
- **5.4. Spinner przy zakładce „Dodaj”** istnieje, ale zależny tylko od `importJobActive` (commit), nie obejmuje fazy ingest.

```557:563:android/app/src/main/java/com/vocabulario/app/ui/home/HomeScreen.kt
                        if (tab == HomeTab.ADD && importBusy) {
                            CircularProgressIndicator(modifier = Modifier.size(12.dp), ...)
                        }
```

- **5.5. Brak przycisku „Przerwij”** dla fazy ingest/commit (jest tylko „Anuluj” w fazie przeglądu, i to wyłączany podczas `importCommitting`). Brak modala potwierdzenia przerwania.
- **5.6. Panel przeglądu ≠ modal.** Wymaganie mówi o **modalu** z listą zaimportowanych słówek; dziś to inline panel w `AddTab` (renderowany tylko na tej zakładce).
- **5.7. Kod martwy / duplikacja logiki.** `data/ImportTextParser.kt` oraz `startImportFromFileText()` (wywołuje `validateImport`) **nie są używane** w aktywnej ścieżce (plik idzie przez `startImportFromFileBytes → /imports/file`). `ui/add/AddWordScreen.kt` + `AddWordViewModel.kt` są poza grafem nawigacji. Utrzymywanie dwóch parserów (Kotlin + Python) grozi rozjazdem.
- **5.8. Limit 2000 pozycji** egzekwowany po stronie backendu — brak wczesnego, przyjaznego komunikatu w UI przed wysłaniem dużego pliku.
- **5.9. Import wyłącznie online** (`import_online_only`) — brak kolejkowania offline (świadoma decyzja, ale warto potwierdzić).

---

## 6. Analiza jakości kart

### 6.1. Tryb `vocabulario` (docelowo „poprawny import”)
- Commit robi `addWordToList` per słowo → backend uruchamia **ten sam pipeline enrichmentu** co przy ręcznym dodaniu. Karty renderują się przez `CardDetailContent` → wyglądają jak natywne. To dobra baza.
- Ryzyka jakości: (a) błędna segmentacja/klasyfikacja (zły `headword_l2`, brak `gloss`), (b) zwroty/konstrukcje idą ścieżką `enrich_adaptive_entry` (bez koniugacji) — mogą wyglądać uboższo, (c) brak raportu duplikatów (§5.3).
- Wniosek: „ładność” w vocabulario ≈ „poprawność wejścia do enrichmentu” + kompletny raport. Enrichment i render już są dobre.

### 6.2. Tryb `preserve` (docelowo „ładny oryginał”) — tu jest główny problem wizualny
- Osobny renderer `ImportDisplayBlocks` (inne style niż `CardDetailContent`) → **niespójny wygląd** z resztą aplikacji.
- Layout budowany przez `analyze_import_display` (prompt `IMPORT_DISPLAY_PROMPT_V1`) + heurystyki (`_split_headings`, `_split_paragraphs`, `_mock_display_analysis`). Efekty:
  - Długie pola / HTML → `section(collapsed) > pre` (monospace) — brzydkie dla treści, które mają naturalną strukturę.
  - Brak jawnych reguł typografii (co wyśrodkować, jaki rozmiar, co to „chip”/etykieta, co czytać TTS).
  - `prompt_style` (`word|phrase|sentence|html_block`) praktycznie nie wpływa na render.
- Wniosek: potrzebny **lepszy prompt + bogatszy, ustandaryzowany schemat display v2**, spójny stylistycznie z kartą Vocabulario, plus mądrzejsze mapowanie treści (a nie „chamskie 1:1”).

### 6.3. Szczególny przypadek: talie Anki z gotową koniugacją
- `Testowa.txt` ma pole 6 = kompletna tabela koniugacji w HTML (`Presente`, `Pretérito indefinido`, …, `class="pron"/"form"`), czyli **dokładnie te dane, które Vocabulario generuje samo**.
- Dziś preserve wrzuca to do `pre`. Można zamiast tego **sparsować tabele HTML** i albo (a) zmapować do `table`/`section` display v2, albo (b) w trybie vocabulario **wykorzystać istniejącą koniugację zamiast generować od nowa** (oszczędność tokenów + wierność źródłu).

---

## 7. Docelowy UX (zgodny z wymaganiami 1–5)

### 7.1. Maszyna stanów zadania importu

```
IDLE
  → (wybór pliku/wklejki + trybu) → PROCESSING
PROCESSING  (blokuje Dodaj: brak search/paste/import; spinner + „Import słówek z pliku {nazwa}. Zaimportowano x/total”;
             spinner przy zakładce „Dodaj”; przycisk „Przerwij” [czerwony])
  → sukces → READY_FOR_REVIEW  (modal z listą zaimportowanych do obsłużenia — niezależnie od aktywnego ekranu)
  → „Przerwij” (po potwierdzeniu) → IDLE (porzucony, Dodaj odblokowane)
  → błąd → ERROR (komunikat + odblokowanie)
READY_FOR_REVIEW → (wybór listy + zatwierdzenie) → COMMITTING → DONE (modal wyników: dodano/duplikaty)
```

Uwaga do wymagań: użytkownik opisuje dwa nieco różne scenariusze — (A) „processing z licznikiem, potem modal do obsłużenia” oraz (B) „user wybiera import i listę, dalej korzysta z aplikacji, a karty generują się w tle i na końcu modal ze statusem”. Oba sprowadzają się do **jednego trwałego zadania w tle z postępem i modalem końcowym**; różnią się tylko momentem wyboru listy (przed czy po processingu). Rekomendacja w §11.

### 7.2. Mapowanie wymagań → zachowanie

1. **Blokada podczas importu** — w stanie PROCESSING/COMMITTING zakładka „Dodaj” pokazuje spinner + komunikat `Import słówek z pliku {nazwa}` i `Zaimportowano x/total`; ukryte/wyłączone: pole wyszukiwania, „Z pliku”, „Wklej”.
2. **Trwałość przy nawigacji** — zadanie żyje ponad zakładkami i trasami; po powrocie do „Dodaj” nadal zablokowane, licznik `x` aktualizowany na bieżąco.
3. **Mały spinner przy zakładce „Dodaj”** — aktywny dla **całego** czasu trwania zadania (ingest + commit), nie tylko commit.
4. **Przycisk „Przerwij” (czerwony)** + modal „Czy na pewno przerwać import?” z [Wróć] / [Przerwij]. Przerwanie porzuca zadanie i odblokowuje „Dodaj”.
5. **Po pełnym imporcie (niezależnie od ekranu)**: (a) spinner/komunikaty z „Dodaj” znikają, (b) odblokowanie funkcji, (c) modal z listą zaimportowanych do obsłużenia / lub modal statusu (dodano/duplikaty).

---

## 8. Plan zmian — Część A: cykl życia i UI importu (naprawa BUG #1)

### A1. Wprowadzić jeden model zadania (`ImportJob`)
- Nowy typ w warstwie stanu (rekomendacja: **osobny, długożyjący komponent**, nie `HomeViewModel`), np. `ImportController`/`ImportJobManager` jako `@Singleton` (Hilt) trzymany poza scope’em nawigacji, wystawiający `StateFlow<ImportJobState>`.
- `ImportJobState`:
  ```
  status: Idle | Processing | ReadyForReview | Committing | Done | Error | Cancelled
  source: FileSource(name) | PasteSource
  mode: vocabulario | preserve
  processed: Int, total: Int            // licznik x/total
  items: List<ImportValidWord> | List<ImportDisplayCard>
  invalid: List<String>
  result: { created: Int, duplicates: Int, failed: Int }?
  error: String?
  targetListId: String?
  ```
- Dzięki singletonowi zadanie przeżywa `key(startRoute)` rebuild grafu i przełączanie tras. `HomeViewModel` tylko **obserwuje** ten stan i renderuje.

### A2. Uodpornić na śmierć procesu (persistencja)
- Zapisywać metadane zadania (nazwa pliku, tryb, lista pozycji już zwalidowanych/wygenerowanych, `targetListId`, postęp) do trwałego magazynu (Room / DataStore) albo delegować commit do `WorkManager` (spójne z istniejącym `SyncWorker`/`EnrichmentCheckWorker`).
- Minimalny wariant: przy wznowieniu aplikacji odtworzyć stan `ReadyForReview`/`Committing`; pełny wariant: `WorkManager` z powiadomieniem.

### A3. Spójne blokowanie „Dodaj”
- Gdy `status ∈ {Processing, Committing}`: w `AddTab` renderować **panel statusu** (spinner + `Import słówek z pliku {name}` + `Zaimportowano {processed}/{total}` + przycisk „Przerwij”), a ukrywać search/„Z pliku”/„Wklej”.
- `search()` już ma guard `if (importActive) return` — rozszerzyć na cały `status` zadania i dodać analogiczne guardy do startu kolejnego importu/wklejki.

### A4. Licznik `x/total` w czasie rzeczywistym (wymaga zmian po stronie backendu — patrz A6)
- Ingest przebudować z „jeden strzał” na **przetwarzanie wsadowe z postępem**:
  - Wariant 1 (rekomendowany, prostszy): rozbić na 2 kroki — `analyze` (format/role, szybkie) → `process batch` (klasyfikacja/enrichment w paczkach po ~40, `import_classify` już batuje po `_BATCH=40`). Frontend woła kolejne paczki i inkrementuje `processed`.
  - Wariant 2: streaming (SSE/chunked) postępu z jednego endpointu.
- Dla `preserve` licznik = liczba przetworzonych notatek (materializacja bloków jest szybka; postęp głównie z `ensure_deck_segmented` + `analyze_import_display`, które są 1× na talię — wtedy licznik odnosi się do materializacji kart `i/total`).

### A5. „Przerwij” + modal potwierdzenia
- Czerwony przycisk „Przerwij” w panelu statusu → modal [Wróć]/[Przerwij]. „Przerwij” = `job.cancel()` (anulowanie coroutines/WorkManagera) + `status=Idle` + odblokowanie.
- Ważne: anulowanie w trakcie commit‑vocabulario musi być bezpieczne (karty już utworzone zostają; nie tworzymy kolejnych) i raportować „dodano X z N (przerwano)”.

### A6. Modal wyników (DONE)
- Po commit pokazać modal: „Dodano {created}, duplikaty {duplicates}, błędy {failed}” + akcja „Pokaż listę”.
- Modal renderowany na poziomie roota (nad każdą trasą), sterowany `ImportJobState.status==Done`, aby był widoczny niezależnie od aktywnego ekranu (wymaganie 5c).

### A7. Uporządkować stan
- Usunąć/zredukować `loading|importActive|importCommitting|importJobActive|importProgress` na rzecz jednego `ImportJobState`.
- Wymusić `tab=ADD` przy wejściu w `ReadyForReview`, żeby panel/modal był w spodziewanym miejscu.

### A8. Sprzątanie kodu martwego
- Usunąć `ImportTextParser.kt`, `startImportFromFileText()`, oraz `AddWordScreen.kt`/`AddWordViewModel.kt` (albo świadomie przywrócić do grafu). Jedno źródło parsowania = backend.

---

## 9. Plan zmian — Część B: import do kart Vocabulario (poprawność)

Cel: „wszystkie karty (poza duplikatami) powstają jako pełne karty Vocabulario na wybranej liście”.

- **B1. Deduplikacja i raport.** Ujednolicić z preserve: commit‑vocabulario ma zwracać `created/duplicates/failed`. Duplikat = istniejąca karta (`find_card_anywhere`) — pomijana, liczona osobno; błąd sieci ≠ duplikat.
- **B2. Odporny commit wsadowy.** Zamiast pętli pojedynczych `addWordToList` (N żądań), rozważyć endpoint **batch‑commit** (jedna transakcja, kolejkowanie enrichmentu w tle), z postępem `x/total`. Zmniejsza ryzyko częściowego importu i obciążenie.
- **B3. Enrichment w tle po commicie.** Karty tworzą się od razu (status `pending`), enrichment leci asynchronicznie (istnieje już polling `startPollingIfNeeded` + `EnrichmentCheckWorker`). To realizuje scenariusz „user korzysta dalej, karty się generują, na końcu modal”.
- **B4. Jakość klasyfikacji.** Doprecyzować `IMPORT_CLASSIFY_PROMPT_V1`: pewny wybór `headword_l2` (L2, nie tłumaczenie), sensowny `gloss_l1` z back‑pola, poprawne `entry_kind`. Dodać testy na próbkach (§12).
- **B5. Decyzja o zwrotach.** Skoro „na razie tylko słowa”: albo (a) mapować `phrase/construction/sentence` mimo to (obecne zachowanie), albo (b) przenosić je do `invalid` z etykietą „zwroty — na razie nieobsługiwane”. Rekomendacja: (a) + wyraźne oznaczenie w przeglądzie, żeby user mógł je odznaczyć.

---

## 10. Plan zmian — Część C: import „w oryginale” (preserve) — ładny render

Cel: nie robić „chamskiego 1:1”, tylko żeby AI zaproponowało jak aplikacja ma wyświetlić kartę (sekcje, wyśrodkowanie, typografia, co czytać TTS, punktory), spójnie ze stylem Vocabulario.

### C1. Ujednolicić renderer ze stylem karty Vocabulario
- Zbliżyć `ImportDisplayBlocks` do stylistyki `CardDetailContent` (te same nagłówki sekcji, chipy, odstępy, typografia) — karta „oryginalna” ma wyglądać „jak nasza”, tylko z treścią użytkownika.

### C2. Rozszerzyć schemat display → **display v2**
Dodać atrybuty prezentacji, których dziś brak:
- `align`: `start | center` (np. lemma/tytuł wyśrodkowany).
- `size`/`emphasis`: `display | lemma | gloss | body | caption` (mapowane na typografię MD3).
- `tts`: `{ enabled: bool, lang: "es"|"pl"|... }` — które pole/blok czytać (Anki Cards ma TTS w źródle).
- `role`/semantyka bloku: `headword | translation | example | note | conjugation | pronunciation | tags`.
- `table` z sensownym renderem (koniugacja) zamiast `pre`.
- `collapsed` domyślnie dla długich/rzadko potrzebnych sekcji.
- zachować kompatybilność: renderer ignoruje nieznane pola (jak dziś `parseBlock`).

### C3. Mądrzejsze mapowanie treści (nie 1:1)
- Krótka treść → tytuł + gloss (wyśrodkowane, duże).
- Wiele znaczeń / punktory → `list`.
- Tabela HTML (koniugacja) → sparsować do `table`/`section` (patrz §6.3), nie `pre`.
- Bardzo długie/nietypowe → `section(collapsed)` z czytelnym nagłówkiem (nie monospace).

### C4. Nowy prompt display (draft w §13)
- Prompt ma zwracać nie tylko role pól, ale **intencję prezentacji** (align/size/tts/semantyka), z twardymi zasadami typografii i „na froncie max 1 tytuł”.
- `answer_needs_structure` + `analyze_import_answer_structure` zostają jako drugi przebieg dla „grubych” prawych stron.

### C5. Zamknięty słownik bloków = kontrakt renderera
- Renderer zna **skończony** zestaw typów; AI mapuje dowolną treść do tego zestawu. Złożoność renderera = O(liczba typów), niezależnie od różnorodności talii.
- Proponowany zestaw: `headword | gloss | bilingual | list | table | note/chip | section | divider | text(fallback)`.
- Nowa/nieznana treść nie wymaga nowego kodu — mapuje się do najbliższego bloku, w ostateczności do `text` (oczyszczony) — **nigdy surowy HTML/CSS/JS**.

### C6. Warstwa deterministyczna PRZED AI (parser HTML/struktury)
- Warstwa A (bez AI): wyciągnij strukturę już maszynową — pola Anki, `<table>`→wiersze, `<ul>/<li>`→`list`, `<br>/<p>`→akapity, `<b>`→emfaza. Rozszerzyć `strip_html`/`import_package.py` o zachowanie tabel/list zamiast płaskiego czyszczenia.
- Warstwa B (AI, ~1–2 wywołania na CAŁĄ talię, nie na kartę): role pól + intencja prezentacji.
- Warstwa C (bez AI): materializacja szablonu na wszystkie notatki.
- To ogranicza koszt/latencję AI i daje powtarzalność.

### C7. Drabinka degradacji pewności (graceful degradation)
1. Znane nazwy pól / czytelna struktura → precyzyjne mapowanie.
2. Wnioskowanie ról przez AI z próbki → dobre mapowanie.
3. Heurystyka (pierwsze pole = front, reszta = back) → akceptowalne.
4. Nieznane/ogromne/dziwne → jeden zwinięty `section > text`, czytelny, spójny stylistycznie.

### C8. Zakres wsparcia note‑type’ów (świadome granice)
- Wprost zdefiniować obsługiwane typy (basic front/back, notatki wielopolowe, tabele).
- Nietypowe (cloze deletion, image occlusion, audio‑only, math) → degradacja do prostej karty front/back **albo** pominięcie z jasnym komunikatem. Nie udajemy pełnej wierności.

### C9. Lepszy model AI dla analizy layoutu (kluczowe dla jakości renderu)
Dotychczasowe testy dają słaby, brzydko sformatowany render — to w dużej mierze **ograniczenie jakości modelu** dobierającego layout, nie tylko promptu.

- Dziś backend jest **OpenAI‑only** (`AsyncOpenAI`), a wszystkie analizy importu chodzą na jednym modelu `llm_lookup_model = "gpt-5.6-terra"` (`core/config.py`), przez `_chat_json` z `response_format: json_schema (strict)`.
- Rekomendacja: wprowadzić **override modelu per‑zadanie** — osobny, mocniejszy model TYLKO dla `analyze_import_display` (+ `analyze_import_answer_structure`), np. `llm_import_display_model`. Analiza layoutu jest 1× na talię, więc koszt mocniejszego modelu jest znikomy, a zysk wizualny duży.
- Aby użyć **Opus 4.8 (Anthropic)** trzeba dodać **abstrakcję providera** w `LLMService` (dziś jest `llm_provider="openai"`, ale klient tylko OpenAI):
  - wariant 1: klient Anthropic + mapowanie „structured output” (tool use / JSON schema) — Anthropic nie ma 1:1 `response_format=json_schema`, trzeba wymusić JSON przez tool/`prefill` + walidację schematem po stronie backendu;
  - wariant 2 (mniejsza zmiana): bramka zgodna z OpenAI API (OpenRouter / LiteLLM / Azure) i podanie slug‑a modelu (np. `claude-opus-4-8`) w `llm_import_display_model`.
- **Twarda walidacja wyjścia** niezależnie od modelu: JSON → schemat display v2 → w razie niezgodności retry/fallback do heurystyki (§C7 p.3–4). Modele bez natywnego strict‑JSON wymagają tego bufora.
- Dobór modelu i zasady typografii z promptu (§13) działają **razem** — sam mocniejszy model bez zamkniętego słownika bloków (§C5) i reguł stylu nadal potrafi „rozjechać” kartę.

### C10. Nauka w dwie strony (L1↔L2) dla kart preserve
Stan obecny: kierunek to ustawienie użytkownika `practice_direction` (`l2_to_l1 | l1_to_l2 | random`, `models/__init__.py`, `learning.py:_resolve_direction`). Praktyka flipuje na podstawie **ustrukturyzowanej treści** karty (`lemma_l2` ↔ `gloss_primary`, `collect_acceptable_answers(content, direction)`).

Konsekwencje dla preserve:
- Karta preserve ma front/back **zapieczony rolami pól** (prompt=front, answer=back) — zwykle L2→L1. Bez dodatkowej informacji „która strona to L2, a która L1” nie da się poprawnie odwrócić karty przy `l1_to_l2`.
- Dlatego **`semantic` z display v2 (§C2) jest warunkiem dwustronności**: oznaczenie `headword`=L2 i `translation`=L1 pozwala rendererowi/praktyce zbudować obie strony niezależnie od zapieczonego front/back.
- Dla kart, w których AI nie ustali jednoznacznie L2/L1 (np. jednopolowe, mieszane), dwustronność wyłączamy dla tej karty (fallback: tylko oryginalny kierunek) — świadomie, zamiast pokazywać bezsensowny flip.
- `commit-display` / `build_import_display_content` powinno zapisywać `lemma_l2` (z `headword`) i `gloss_primary` (z `translation`) tak, by SRS i `collect_acceptable_answers` działały jak dla zwykłych kart (już częściowo są ustawiane).

> Podsumowanie: dwustronność **zadziała dla preserve tylko jeśli** import otaguje semantykę stron (L2/L1). To jest ujęte w display v2 i w prompcie (§13). Dla vocabulario dwustronność działa już dziś (treść jest ustrukturyzowana).

---

## 11. Rekomendacja dot. kolejności wyboru listy

Aby pogodzić oba scenariusze użytkownika i uzyskać najlepszy UX:

1. **Wybór trybu + listy docelowej PRZED processingiem** (jeden ekran startowy importu).
2. Start zadania → PROCESSING w tle z licznikiem `x/total`, „Dodaj” zablokowane, spinner przy zakładce, „Przerwij” dostępny.
3. User może swobodnie korzystać z reszty aplikacji.
4. Po zakończeniu → **modal wyników** (dodano/duplikaty) niezależnie od ekranu; z modala „Pokaż listę”.

To upraszcza maszynę stanów (jedno przejście PROCESSING→DONE), eliminuje „wiszący pasek na Dashboardzie” i realizuje wszystkie 5 wymagań. Faza „przeglądu/odznaczania” pozycji staje się opcjonalna (można ją zostawić jako krok przed startem lub całkiem pominąć w MVP).

> Do decyzji użytkownika: czy zostawiamy krok ręcznego przeglądu/odznaczania pozycji (jak dziś), czy import jest w pełni automatyczny z modalem końcowym.

---

## 12. Testy i walidacja

- **Backend (pytest)** na próbkach z `Desktop/`:
  - `quizlet2.txt` → poprawna segmentacja (N kart, nie 1).
  - `Testowa.txt` → notes: właściwe pole = headword; koniugacja rozpoznana.
  - `Testowa2.txt` → cards_html: ekstrakcja lemma z `front-word`; brak JS/CSS w output.
  - `.apkg` → happy path + jasny błąd dla `anki21b`.
  - Deduplikacja: powtórzone hasła → `duplicates`, nie `failed`.
- **Frontend**: testy stanu `ImportJobState` (PROCESSING blokuje search/paste/import; „Przerwij” → Idle; DONE → modal). Utrzymać istniejące `TestTags` (`BTN_IMPORT_*`, `IMPORT_MODE_*`).
- **E2E (maestro)**: import pliku → nawigacja w trakcie → powrót → nadal zablokowane, licznik rośnie → modal wyników.

---

## 13. Draft nowego promptu display (preserve v2)

Szkic (do iteracji), rozszerza `IMPORT_DISPLAY_PROMPT_V1` o intencję prezentacji:

```
System: Jesteś warstwą layoutu importu fiszek w Vocabulario. Notatki są już
posegmentowane. Zwracasz JSON: role pól + SZABLON bloków UI (front/back) z
field_index ORAZ intencją prezentacji. Karta ma wyglądać spójnie ze stylem
Vocabulario (czysto, mobilnie), nie kopiuj CSS/JS Anki, nie zmyślaj treści.

Zasady:
- Front: max 1 główny tytuł (headword) — align=center, size=lemma; opcjonalnie
  chip/meta (np. tempo, tagi) NAD tytułem.
- Back: najpierw główne tłumaczenie (size=gloss), potem przykłady (bilingual:
  L2 wyżej, L1 niżej), potem detale w sekcjach (collapsed dla długich).
- Wiele znaczeń / punktory → type=list.
- Tabela odmiany/koniugacji w HTML → type=table (nagłówki + wiersze), NIE pre.
- Ustaw tts={enabled:true, lang:L2} dla pól w języku uczonym, które warto czytać
  (headword, przykłady L2). Reszta tts.enabled=false.
- Dla każdego bloku ustaw: type, field_index/l2_field_index/l1_field_index,
  align(start|center), size(display|lemma|gloss|body|caption),
  semantic(headword|translation|example|note|conjugation|pronunciation|tags),
  collapsed, tts. Nieużywane pola = null.
- prompt_style: word|phrase|sentence|html_block.
- answer_needs_structure=true gdy prawa strona jest długa/HTML/wielosegmentowa.
- Oznacz semantic=headword dla pola L2 i semantic=translation dla pola L1
  (potrzebne do nauki w dwie strony). Jeśli nie da się ustalić — semantic=null.
- rationale po polsku.
```

Schemat `import_display.py` rozszerzyć o pola: `align`, `size`, `semantic`, `tts` (obiekt `{enabled, lang}`) — z zachowaniem wstecznej zgodności.

Model dla tej analizy: uruchamiać na mocniejszym modelu (override per‑zadanie, §C9), z twardą walidacją JSON→schemat i fallbackiem do heurystyki.

---

## 14. Podsumowanie zależności i etapy wdrożenia

Kolejność (od najniższego ryzyka):

1. **Etap 1 — UX/stan (naprawa BUG #1):** `ImportJob` jako singleton + spójne blokowanie „Dodaj” + „Przerwij” + modal wyników + spinner przy zakładce na cały czas zadania. (Część A, bez zmian backendu poza raportem.)
2. **Etap 2 — poprawność vocabulario:** batch‑commit + raport `created/duplicates/failed` + enrichment w tle. (Część B.)
3. **Etap 3 — licznik x/total realny:** rozbicie ingestu na paczki z postępem. (A4/A6.)
4. **Etap 4 — ładny preserve:** display v2 (schemat + prompt + renderer spójny z Vocabulario, parsowanie tabel koniugacji, warstwa deterministyczna §C6, drabinka degradacji §C7). (Część C.)
5. **Etap 4b — jakość modelu:** override modelu per‑zadanie dla analizy layoutu + (opcjonalnie) abstrakcja providera pod Opus 4.8; twarda walidacja JSON. (§C9.)
6. **Etap 4c — dwustronność preserve:** tagowanie semantic L2/L1 + zapis `lemma_l2`/`gloss_primary` w commit‑display. (§C10.)
7. **Etap 5 — sprzątanie:** usunięcie kodu martwego, testy na próbkach.

Otwarte decyzje do potwierdzenia:
- Czy zostaje ręczny krok przeglądu/odznaczania pozycji (§11)?
- Zwroty/konstrukcje: importować czy oznaczać jako nieobsługiwane (§9 B5)?
- Trwałość zadania: `WorkManager` (pełna odporność na śmierć procesu) czy tylko singleton + DataStore (MVP)?
- Czy wykorzystywać gotową koniugację z Anki w trybie vocabulario (§6.3), czy zawsze generować od nowa?
- **Model dla analizy layoutu:** Opus 4.8 (wymaga abstrakcji providera/bramki) czy mocniejszy model OpenAI‑compatible (mniejsza zmiana)? (§C9.)
- **Dwustronność preserve:** włączać tylko gdy AI pewnie otaguje L2/L1, czy pozostawić jednokierunkową dla niejednoznacznych kart? (§C10.)
```
