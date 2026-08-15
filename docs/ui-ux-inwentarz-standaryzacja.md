# Inwentarz UI/UX — powtarzające się flow i miejsca do ujednolicenia

Przegląd wszystkich ekranów, modalów, sheetów i formularzy w aplikacji Android (Compose). Cel: wiedzieć **gdzie to samo pytanie / ta sama funkcja pojawia się więcej niż raz** i **gdzie wygląd lub zachowanie się rozjeżdża**, zanim zacznie się standaryzację.

Wizualne porównanie wariantów (makiety z tokenów Compose + copy PL, z możliwością zaznaczenia wyboru): [ui-ux-porownanie.html](ui-ux-porownanie.html).

Źródło: kod w `android/app/src/main/java/com/vocabulario/app/ui/`. Nie wymaga klikania każdej funkcji w emulatorze.

Stan tokenów, które już istnieją i warto **dopinać wszędzie**:

| Token | Wartość | Gdzie zdefiniowany |
|---|---|---|
| `AppCardShape` | 18.dp | `AppComponents.kt` |
| `AppButtonShape` | 28.dp (pill) | `AppComponents.kt` |
| `AppChipShape` | 999.dp | `AppComponents.kt` |
| `AppDialogShape` | 24.dp | `AppComponents.kt` |
| `CardBlockingAlertDialog` + `CardDialogButtonRow` | wspólny dialog karty | `CardSheetDialogs.kt` |
| `ActionCancel` / `ActionConfirm` | różowy / zielony | `Theme.kt` |

Część UI już z nich korzysta. Reszta nadal ma własne kształty, kolory przycisków i copy.

---

## 1. Mapa nawigacji (od pierwszego ekranu)

```
Splash (LOADING) ─────────────────────────────────────────┐
                                                          │
AUTH ──login / register / Google──► ONBOARDING ──► HOME   │
  ▲                                    ▲            │     │
  │                                    │            │     │
  └── Settings → Wyloguj ──────────────┘            │     │
                                                    │     │
HOME (3 taby + stały przycisk Ucz się)              │     │
  ├── Dashboard                                     │     │
  ├── Dodaj (szukaj / głos / import)                │     │
  ├── Listy (chipy + kafelki słów)                  │     │
  ├── ⚙ → SETTINGS                                  │     │
  └── Ucz się → PRACTICE                            │     │
                                                    │     │
Zarejestrowane, ale NIEOSIĄGALNE z UI:              │     │
  PROFILE, LEARNING, PACKS  ◄── NavHost ma trasy,   │     │
                                nikt do nich        │     │
                                nie nawiguje        │     │
```

Start (`AppViewModel.bootstrap`):

1. Brak tokenu → **Auth**
2. Token + brak profilu językowego → **Onboarding**
3. Token + profil → **Home**
4. Timeout / błąd sieci (nie 401) → **Home** (offline)

---

## 2. Katalog ekranów i wszystkich akcji

### 2.1 Auth (`AuthScreen`)

- Formularz: email + hasło (login **albo** rejestracja, przełącznik `TextButton`).
- Akcje: zaloguj / zarejestruj, Google, przełącz tryb.
- Błąd: czerwony tekst pod formularzem (nie modal).
- Wygląd: hero z gradientem + `BrandLogo`. Jedyny ekran z tym layoutem (OK).
- Pola: `OutlinedTextField` + `AppButtonShape` (pill). Przyciski 52.dp.
- **Brak** `AppScreenScaffold`. Świadomie inny — zostawić.

### 2.2 Onboarding (`OnboardingScreen`)

Pytania do usera:

1. Język natywny (dropdown)
2. Język nauki (dropdown)
3. Poziom CEFR (radio lista A1–C2)
4. Czasy czasownika — tylko gdy pack językowy to pokazuje (checkboxy)
5. Start

To **ten sam zestaw pytań** co Settings (języki + CEFR + czasy) i niedostępny Profile.

Różnice vs Settings:

| | Onboarding | Settings |
|---|---|---|
| Języki | `LangDropdown` bez `AppButtonShape` | `SettingsDropdown` z `AppButtonShape` |
| CEFR | pionowa lista `RadioButton` | `ExposedDropdownMenu` |
| Czasy | checkboxy inline na ekranie | radio „wszystkie / wybrane” + **osobny modal** `TensePickerDialog` |
| Scaffold | goły `Column` + padding 24 | `AppScreenScaffold` |
| Przycisk Start | `Button` bez `AppButtonShape` | — |

### 2.3 Home — Dashboard

Tylko odczyt: due / nowe / powtórzone, status puli, wykres 7 dni. Brak modalów. Błąd: mały czerwony tekst na dole.

### 2.4 Home — Dodaj

Akcje:

| Akcja | Co się otwiera |
|---|---|
| Import z pliku | `ImportStartDialog` (plik + tryb + lista) |
| Wklej | ten sam `ImportStartDialog` w trybie paste |
| Szukaj (tekst) | lista `CandidateRow` |
| Mikrofon | `VoiceSearchSheet` (Dialog, nie sheet) |
| + na kandydacie | `AddToListSheet` |
| Chip listy na kandydacie już na liście | skok do Listy + focus słowa |
| Offline | banner, bez importu i głosu |

Import (globalny, overlay nad **każdą** trasą w `VocabularioAppRoot`):

1. `ImportStartDialog` → processing (`ImportStatusPanel` na tabie Dodaj) →
2. `ImportReviewDialog` (checkboxy słów) → committing →
3. `ImportResultDialog` **albo** `ImportErrorDialog`
4. W trakcie: Abort → `ImportAbortConfirmDialog`

### 2.5 Home — Listy

Akcje na chipie listy (menu `ListEditDialog.Menu`):

- systemowa (Uczę się): przenieś wszystkie / wyczyść wszystkie
- pending inbox: przenieś wszystkie / usuń listę
- zwykła: zmień nazwę / przenieś wszystkie / usuń listę

Akcje na kafelku słowa:

- tap → rozwinięcie (reveal odpowiedzi) + ikony: zobacz kartę / ⋮ (usuń, przenieś, popraw, historia)
- long-press → multi-select
- `needs_review` → `PendingReviewSheet` zamiast rozwinięcia

Sort / filtr: dwa `ModalBottomSheet`.

Pełna karta: `ListCardDetailOverlay` (pełnoekranowy `Dialog`).

### 2.6 Practice (`PracticeScreen`)

Wejście: przycisk **Ucz się** na Home.

Fazy:

1. Ładowanie / błąd (retry) / pusta kolejka (`EmptyState` + Wstecz)
2. Odpowiedź: flashcard / choice / type (z Settings)
3. Zły choice → `AlertDialog` „błąd” + toast „Błąd”
4. Dobry choice/type → toast „Brawo”
5. Rewers karty (`FlashcardBackContent` albo `ImportDisplayFlip`) + oceny Again/Hard/Good/Easy
6. Na rewersie: Popraw kartę, Historia, + przy słowach pokrewnych → `AddToListSheet`

Undo w top barze.

### 2.7 Settings (`SettingsScreen`)

Accordion: tryb nauki, kierunek, układ karty (+ czasy), limit nowych, motyw, powiadomienia, języki, CEFR. Wyloguj **bez potwierdzenia**.

Modal: `TensePickerDialog` (`Dialog` + `Surface`, nie `AlertDialog`).

### 2.8 Ekrany zarejestrowane, ale martwe

| Trasa | Plik | Status |
|---|---|---|
| `PROFILE` | `ProfileScreen` | NavHost jest, **nikt nie nawiguje**. Duplikuje CEFR + czasy z Onboardingu/Settings. Własny `Scaffold` (nie `AppScreenScaffold`). Karty Material bez `AppCard`. |
| `LEARNING` | `LearningScreen` | `onOpenCard` w Root idzie tu, ale Home **nigdy nie woła** `onOpenCard`. Pokazuje listę kart + `CardDetailContent` + `AddToListSheet`. |
| `PACKS` | `PacksScreen` | Placeholder tekstowy. Własny `Scaffold`. |

**Wniosek:** Profile i Packs nie powinny wchodzić w standaryzację „żywego” UI, dopóki nie zdecydujesz, czy je usunąć, czy podpiąć. Learning wygląda na starszy wariant „zobacz kartę”, zastąpiony przez `ListCardDetailOverlay`.

---

## 3. Powtarzające się flow (to, co warto ujednolicić jako pierwsze)

Każdy wiersz = **jedna funkcja / jedno pytanie do usera**, które pojawia się w ≥2 miejscach.

### A. Dodaj słowo do listy

**Pytanie:** „Uczę się” czy inna lista? Ewentualnie utwórz nową.

| Miejsce | Trigger | UI |
|---|---|---|
| Home → Dodaj | + na `CandidateRow` | `AddToListSheet` (bottom sheet, 3 stany) |
| Home → głos | + na `VoiceCandidateRow` | ten sam sheet (po dismiss dialogu głosu) |
| Practice → zły choice | + na wygaszonej kafelce | ten sam sheet |
| Practice → rewers | + przy related word | ten sam sheet |
| Learning (martwy) | related word | ten sam sheet |

**Stan:** już wspólny komponent. Dobrze.

**Rozjazd:** tworzenie nowej listy w tym flow (sheet, pole pill `AppButtonShape`, przyciski 52.dp, Wstecz/Dodaj) **nie wygląda jak** tworzenie listy z zakładki Listy (AlertDialog, pole 14.dp, Utwórz w kolorze tertiary).

### B. Utwórz nową listę

| Miejsce | Kontekst | Kontener | Pole | Primary | Anuluj |
|---|---|---|---|---|---|
| Listy → chip + | pusta / przenieś 1 / wybrane / wszystkie | `AlertDialog` | `RoundedCornerShape(14)`, `surfaceVariant`, bez ramki | **Utwórz**, `tertiary` | Anuluj, `error` |
| `AddToListSheet` | po „Inna lista” → „Nowa lista” | bottom sheet | pill 52.dp | **Dodaj** | **Wstecz** |
| `ImportStartDialog` | opcja w dropdownie listy | ten sam AlertDialog importu | zwykły `OutlinedTextField` | Start importu | Anuluj, `error` + osobny TextButton Anuluj przy polu |

Trzy różne pytania o tę samą rzecz: nazwę listy. Trzy różne CTA (Utwórz / Dodaj / Start).

### C. Wybierz listę docelową

| Miejsce | UI |
|---|---|
| `AddToListSheet` | pionowa lista `Surface` pill 52.dp |
| Import start | `ExposedDropdownMenu` |
| Przenieś słowo / wybrane / wszystkie | `ExposedDropdownMenu` w AlertDialog + link „Nowa lista” |

To samo pytanie, dwa wzorce: sheet z kafelkami vs dropdown.

### D. Potwierdź usunięcie (destrukcyjne)

| Miejsce | Tytuł | Primary | Secondary | Kolor primary |
|---|---|---|---|---|
| Usuń listę | `list_delete_confirm_title` | **Usuń** | **Wstecz** (`onSurface`) | `error` |
| Wyczyść listę | `list_clear_all_title` | **Wyczyść wszystkie** | **Anuluj** (`onSurface`) | `error` |
| Usuń słowo | `list_delete_word_confirm` (bez body) | **Usuń** | **Wstecz** | `error` |
| Usuń zaznaczone | tytuł + body z liczbą | **Usuń** | **Wstecz** | `error` |
| Przerwij import | `import_abort_title` | **Przerwij** | **Anuluj** (bez `error` na tekście) | `error` |
| Wyloguj | — | klik od razu wylogowuje | brak | outlined, primary |

Wzorzec destrukcji jest, ale:

- secondary raz **Wstecz**, raz **Anuluj**
- kolor Anuluj raz `error`, raz `onSurface`, raz default
- usunięcie słowa **nie ma treści** (tylko tytuł)
- wylogowanie **nie pyta** — jedyna destrukcja bez dialogu

### E. Przenieś (słowo / zaznaczone / całą listę)

Trzy niemal identyczne `AlertDialog` w `HomeScreen.kt` (~80 linii × 3):

- `WordEditDialog.Move`
- `MultiEditDialog.Move`
- `ListEditDialog.MoveAll`

Różnica: tytuł, czy jest link „Nowa lista”, i który callback. Dropdown i przyciski skopiowane 1:1.

**Rekomendacja:** jeden `MoveToListDialog(title, lists, onMove, onCreateNew?)`.

### F. Język natywny / język nauki

| Miejsce | Komponent |
|---|---|
| Onboarding | `LangDropdown` (bez pill shape, bez surface fill) |
| Settings → Języki | `SettingsDropdown` (pill + surface) |
| Profile (martwy) | brak — tylko pokazuje kody |

To samo pytanie, dwa wyglądy dropdownu.

### G. Poziom CEFR

| Miejsce | Wzorzec |
|---|---|
| Onboarding | radio lista |
| Settings | dropdown |
| Profile (martwy) | radio lista (jak onboarding) |

User odpowiada na to samo w dwóch żywych miejscach **innym kontrolerem**.

### H. Wybór czasów czasownika

| Miejsce | Wzorzec |
|---|---|
| Onboarding | checkboxy na stronie |
| Settings → układ karty | radio Wszystkie / Wybrane + modal z checkboxami (`TensePickerDialog`) |
| Profile (martwy) | checkboxy na stronie |

Settings ma dojrzalszy UX (modal, potwierdzenie, tertiary Confirm). Onboarding wygląda jak prototyp.

### I. Popraw kartę / edytuj sam / historia

**Ten sam zestaw** podpięty w dwóch żywych miejscach:

| Krok | Home (Listy) | Practice (rewers) |
|---|---|---|
| Wejście | ikona ołówka na kafelku | `TextButton` „Popraw kartę” |
| Raport sekcji | `CardCorrectionReportSheet` | to samo |
| Wynik AI | `CardCorrectionResultDialog` | to samo |
| Self-edit | `CardSelfEditSheet` | to samo |
| Ostrzeżenie walidacji | `CardSelfEditWarningDialog` | to samo |
| Historia | `CardHistorySheet` | to samo |

**Komponenty już wspólne.** Rozjazd jest w **wejściu**:

- Listy: okrągła ikona w rzędzie akcji kafelka
- Practice: dwa `TextButton` pod treścią karty (Popraw / Historia), Historia w kolorze pomarańczowym `CorrectionActivityColor`

### J. Zobacz pełną kartę

| Miejsce | Renderer | Kontener |
|---|---|---|
| Listy → ikona artykułu | `CardDetailContent` **albo** `ImportDisplayFlip` | pełnoekranowy `Dialog` (`ListCardDetailOverlay`) |
| Practice → rewers | `FlashcardBackContent` **albo** `ImportDisplayFlip` | w scaffoldzie, nie overlay |
| Learning (martwy) | `CardDetailContent` | w `AppScreenScaffold` |

Dwa osobne renderery karty native (`CardDetailContent` vs `FlashcardBackContent`) — podobna treść (znaczenia, conjugacja, related, TTS), inny układ i inne flagi z Settings (Practice honoruje showUsages / examples / conjugation; overlay listy **wymusza** `fullDetail = true` i `userTenses = emptyList()`).

To jest największy rozjazd **treści**, nie tylko chrome’u.

### K. Wynik wyszukiwania słowa (kandydat)

| Miejsce | Komponent | + dodaj | Kształt |
|---|---|---|---|
| Dodaj (lista) | `CandidateRow` | koło 40.dp primary | `AppCard` 18.dp |
| Głos | `VoiceCandidateRow` | `IconButton` Add (nie koło) | `AppDialogShape` 24.dp, `surfaceVariant` |
| Review pending | `SuggestionTile` | brak + (wybór kafelkiem) | 16.dp, border 2.dp gdy selected |
| Practice zły choice | `ChoiceTile` (tryb `showActions`) | koło 40.dp jak CandidateRow | 20.dp, `surfaceVariant` |
| Related na rewersie | `RelatedWordsList` | koło 40.dp | wiersz w sekcji |
| Learning lista | `WordListItem` | brak | `AppCard` |

Pięć wariantów „lemma + gloss + POS + akcja”. CandidateRow i ChoiceTile(showActions) i RelatedWordsList są najbliżej — warto jeden `LemmaRow`.

### L. Empty / error / loading

| Sytuacja | Wzorzec |
|---|---|
| Pusta kolejka Practice | `EmptyState` (tytuł + hint, padding 48) |
| Pusta lista Learning | `EmptyState` |
| Pusta lista słów (Listy) | zwykły `Text` wyśrodkowany, padding 40 |
| Filtr nic nie zwraca | `Text` + `TextButton` Wyczyść filtry |
| Pusty Dodaj | `Text` `import_empty_hint`, padding 56 |
| Błąd Practice | tekst + Button Retry |
| Błąd Auth / Onboarding / Settings / Dodaj | czerwony `Text` inline |
| Błąd importu | `ImportErrorDialog` (modal) |
| Loading Home listy | spinner na środku |
| Loading Practice | spinner |
| Loading Settings | spinner zamiast treści |
| Pair switch | `PairSwitchHost` — blur + scrim + spinner nad **całą** apką |

Brak wspólnego `ErrorBanner` / `EmptyState` wszędzie. Import jako jedyny error idzie w modal.

---

## 4. Katalog modalów i sheetów (wszystkie)

### 4.1 AlertDialog (Material, `AppDialogShape`)

Używane bezpośrednio, **nie** przez `CardBlockingAlertDialog`:

| Dialog | Plik | Przyciski | Uwagi |
|---|---|---|---|
| Import abort | `ImportUi` | Przerwij (error Button) + Anuluj (Outlined) | OK wzorzec destrukcji |
| Import result | `ImportUi` | OK (Button) + **Pokaż listę (`TextButton`)** | jedyny TextButton jako secondary w dialogu importu |
| Import error | `ImportUi` | OK | ten sam tytuł co result (`import_result_title`) |
| Import review | `ImportUi` | Confirm+liczba (`tertiary`) + Anuluj (`error`) | duża lista w `text` |
| Import start | `ImportUi` | Start + Anuluj (`error`) | formularz w `text` |
| Practice wrong | `PracticeScreen` | **Wróć** (jeden Button) | `onDismissRequest` zamyka; `dismissButton = {}` |
| Nowa lista | `HomeScreen` | Utwórz (`tertiary`) + Anuluj (`error`) | |
| Menu listy | `HomeScreen` | puste confirm + **Wstecz TextButton** | to nie jest dialog potwierdzenia — to menu akcji w AlertDialog |
| Rename listy | `HomeScreen` | **OK** + Anuluj (`onSurface`) | jedyny dialog z CTA „OK” przy zapisie nazwy |
| Delete list / word / selected / clear all | `HomeScreen` | Usuń (`error`) + Wstecz lub Anuluj | patrz tabela D |
| Move word / selected / all | `HomeScreen` | Przenieś + Anuluj (`error`) | 3 kopie |

### 4.2 CardBlockingAlertDialog (wspólny)

| Dialog | Blocking? | Przyciski |
|---|---|---|
| `CardCorrectionResultDialog` | tak (`onDismissRequest = {}`) | OK **albo** Anuluj + Edytuj sam |
| `CardSelfEditWarningDialog` | tak | Cofnij + Potwierdź |
| `PendingReviewSheet` (mimo nazwy Sheet) | nie (X zamyka) | warianty: Odrzuć/Szukaj ponownie **albo** Szukaj/Zatwierdź + TextButton Odrzuć |

Te trzy są najbardziej spójne wizualnie (shape, `CardDialogButtonRow` 48.dp, SemiBold).

### 4.3 Dialog (custom Surface, nie AlertDialog)

| | Kontener | Szerokość |
|---|---|---|
| `TensePickerDialog` | `Dialog` + Surface 92% | Anuluj (`error`) + Potwierdź (`tertiary`) |
| `VoiceSearchSheet` | pełny overlay 52% czarny + Surface | X w rogu, bez pary przycisków |
| `ListCardDetailOverlay` | pełny ekran, background | X, jak osobny ekran |
| Usages na flashcard | pełny overlay, klik tła zamyka | Surface 16.dp (nie `AppDialogShape` 24) |

Cztery różne „okna” poza AlertDialog.

### 4.4 ModalBottomSheet

| Sheet | Shape sheetu | tonalElevation | Przyciski |
|---|---|---|---|
| `AddToListSheet` | `AppButtonShape` | 0 | własne SheetPrimary/Outlined 52.dp |
| `CardSelfEditSheet` | `AppButtonShape` | 0 | Anuluj (Outlined **bez** shape) + Zapisz (z `AppButtonShape`) |
| `CardCorrectionReportSheet` | **default Material** | default | jeden Button Submit; self-edit to klikalny tekst |
| `CardHistorySheet` | **default Material** | default | Restore jako `TextButton` |
| Sort (Listy) | default | default | tap wiersza zamyka |
| Filter (Listy) | default | default | Wyczyść wszystkie + Zastosuj, 50/50 |

Rozjazd: dwa sheety „markowe” (pill + elevation 0) vs cztery domyślne Material.

Self-edit **blokuje** swipe-to-dismiss (`confirmValueChange` + `onDismissRequest = {}`). Correction/History/AddToList zamykają się gestem. User nie wie, który sheet da się zrzucić.

---

## 5. Rozjazdy wizualne (chrome)

### 5.1 Kształty

| Element | Występuje jako |
|---|---|
| Pole tekstowe w dialogu listy | 14.dp |
| Pole w AddToList / Auth / Practice type / Settings | `AppButtonShape` 28.dp |
| Pole w Import paste / Self-edit / Correction note | default OutlinedTextField (4.dp Material) |
| Dropdown import / move | 14.dp albo default |
| Kafelek słowa na liście | 20.dp |
| ChoiceTile (aktywny) | `AppButtonShape` 28 |
| ChoiceTile (po błędzie, showActions) | 20.dp |
| SuggestionTile (review) | 16.dp |
| Toast Practice | 28.dp |
| Usages modal | 16.dp |
| GradeSquare | 12.dp |
| Dashboard tile | 28.dp (`TileRadius`) |
| AppCard | 18.dp |

Za dużo radiusów dla „zaokrąglonego kafelka / pola”. Kandydat na 3 tokeny: **pole** (pill 28), **karta** (18), **dialog** (24). Reszta (12, 14, 16, 20) do wyrzucenia albo uzasadnienia.

### 5.2 Wysokość przycisków

| Wysokość | Gdzie |
|---|---|
| 48.dp | `CardDialogButtonRow`, Import abort/start, multi-select bar, import file/paste |
| 52.dp | Auth, AddToList sheet, Practice Show answer / Check |
| 54.dp | Home **Ucz się** |
| 56.dp | `GradeSquare` |
| `heightIn(min = 48)` | Correction submit |
| bez stałej wysokości | większość dialogów list, Settings Confirm, Self-edit, Onboarding Start |

### 5.3 Kolor primary w dialogach

| Kolor | Użycie |
|---|---|
| `primary` (niebieski) | większość Button |
| `tertiary` (zielonkawy) | Utwórz listę, Import review Confirm, Settings Confirm limit, TensePicker Confirm |
| `error` | Usuń / Wyczyść / Przerwij |

Tertiary = „pozytywne potwierdzenie”. Nie jest stosowane konsekwentnie (rename listy daje zwykły primary **OK**, AddToList **Dodaj** jest primary, nie tertiary).

### 5.4 Kolor Anuluj

W `Theme.kt` jest `ActionCancel` (różowy) — **prawie nigdzie nie używany w dialogach**. Anuluj to zwykle `OutlinedButton` z `color = scheme.error` albo `onSurface`.

Grade Again używa `ActionCancel`. Dialogi nie.

### 5.5 Scaffold / top bar

| Ekran | Wzorzec |
|---|---|
| Practice, Settings, Learning | `AppScreenScaffold` |
| Home | własny header (logo + kółko settings) |
| Auth, Onboarding | bez top bara |
| Profile, Packs | surowy `Scaffold` + `TopAppBar` (inne paddingi: 16 vs 20) |

### 5.6 Copy przycisków wtórnych (to samo znaczenie, inne słowo)

| Intencja | Słowa, które się pojawiają |
|---|---|
| Zamknij bez skutku | Anuluj, Wstecz, Zamknij (X), Wróć (`action_return` w practice wrong), OK |
| Potwierdź pozytywnie | OK, Potwierdź, Utwórz, Dodaj, Start, Zastosuj, Zapisz, Zatwierdź |
| Destrukcja | Usuń, Wyczyść wszystkie, Przerwij, Odrzuć, Wyloguj |

Największy bałagan: **Anuluj vs Wstecz** w dialogach destrukcji (D) i **OK vs Zapisz vs Potwierdź** przy zatwierdzaniu formularza.

---

## 6. Zachowania, które user poczuje jako „inne”

1. **Zamknięcie poza przyciskiem**
   - Większość AlertDialog: tap poza / back zamyka.
   - Correction result i Self-edit warning: **nie da się** zamknąć tłem (`onDismissRequest = {}`).
   - Self-edit sheet: nie da się zrzucić.
   - Correction report / History / AddToList: da się zrzucić.
   - Practice wrong: tap poza = Wróć (OK).
   - Usages: tap tła zamyka; Voice: też.

2. **Logout bez potwierdzenia**, usunięcie słowa z potwierdzeniem. Niespójna hierarchia ryzyka.

3. **Menu listy w AlertDialog** (lista przycisków + Wstecz) vs **menu słowa** (rozwijane ikony na kafelku). Dwie metafory „więcej akcji”.

4. **Import wynik** secondary = TextButton „Pokaż listę”; wszędzie indziej secondary = OutlinedButton.

5. **Cancel w Import review / start** ma `color = scheme.error` mimo że to nie jest destrukcja (destrukcja jest osobnym abortem).

6. **Onboarding Start** bez `AppButtonShape`; po onboardingu pierwszy ekran Home już jest „markowy”. Skok stylu na starcie.

7. **Powiadomienia — godzina** to gołe `OutlinedTextField` na liczbę, bez pill, bez paddingu sekcji (wypada z accordionu wizualnie). Limit nowych kart ma pill + Confirm tertiary — ta sama klasa „wpisz liczbę”, inny UI.

8. **Flashcard usages** otwiera modal 16.dp / elevation 6. Inne dialogi 24.dp / elevation 0. Wygląda jak z innej apki.

9. **Głos vs szukaj tekstowy:** po głosie kandydaci są w dialogu, bez chipa „już na liście”, bez skoku do listy, + to `IconButton` nie koło 40.dp. Po dodaniu dialog się zamyka — w szukaniu tekstowym zostajesz na liście wyników.

---

## 7. Co już jest ujednolicone (nie ruszać bez potrzeby)

- `AddToListSheet` — jeden flow dodawania, 3 wejścia.
- Correction / self-edit / history — te same composable na Listach i w Practice.
- `CardBlockingAlertDialog` + `CardDialogButtonRow` — wzorzec do **rozszerzenia** na resztę dialogów.
- Tokeny `App*Shape` i kolory brand w `Theme.kt`.
- Import overlay globalny (wynik/błąd nad każdą trasą).
- `SettingsRadioRow` / `SettingsCheckRow` wewnątrz Settings.
- Przycisk **Ucz się** i główne CTA Auth (pill, pełna szerokość).

---

## 8. Proponowana kolejność standaryzacji

Priorytet = (ile razy user to widzi) × (jak bardzo się rozjeżdża).

### P0 — wspólny dialog systemowy

Zbudować **jeden** `AppAlertDialog` (albo rozszerzyć `CardBlockingAlertDialog`) z wariantami:

- `neutral` — Anuluj (Outlined, `onSurface`) + Potwierdź (Button primary)
- `positive` — Anuluj + Potwierdź/Utwórz (`tertiary`)
- `destructive` — Anuluj + Usuń/Przerwij (`error`)
- `single` — jeden pełnej szerokości (OK / Wróć)

Zasady copy:

- wtórny zawsze **Anuluj** (nie Wstecz), chyba że to nawigacja wstecz w wielokrokowym sheetcie
- zapis nazwy / formularza: **Zapisz**, nie OK
- zamknięcie informacyjne: **OK**
- X tylko w overlayach pełnoekranowych / voice / review

Podmienić ~15 AlertDialogów w `HomeScreen` + `ImportUi` + Practice wrong.

### P1 — jeden dialog listy i jeden „przenieś”

- `CreateListDialog` — zastępuje tworzenie z Listy, z move-then-create, i opcję w Imporcie (albo import zostaje w swoim wizardzie, ale pole nazwy wygląda tak samo).
- `MoveToListDialog` — jedna implementacja zamiast 3.
- Menu listy: albo zostawić AlertDialog, ale przyciski jak w `CardDialogButtonRow`, albo przerobić na bottom sheet analogiczny do `AddToListSheet` (wtedy „więcej akcji” ma jedną metaforę: sheet).

### P2 — sheety

- Wszystkie `ModalBottomSheet`: `shape = AppButtonShape`, `tonalElevation = 0`, padding 20–24.
- Jedna polityka dismiss: formularze z danymi (self-edit, import?) blokują gest; listy opcji (sort, filter, add-to-list, correction report, history) pozwalają zrzucić.
- Correction report: self-edit jako OutlinedButton, nie klikalny paragraf.

### P3 — pola i dropdowny

- Wspólny `AppOutlinedField` (pill, `surfaceVariant`, bez ramki unfocused) — Auth, AddToList, Listy create/rename, Settings liczby, Practice type.
- Wspólny `AppDropdown` — Onboarding języki, Settings języki/CEFR, Import lista, Move lista, Self-edit POS.

### P4 — onboarding = settings (te same kontrolki)

- CEFR: zdecydować radio **albo** dropdown i użyć w obu.
- Czasy: checkboxy onboardingu zastąpić tym samym `TensePickerDialog` (albo odwrotnie, ale jeden wzorzec).
- Języki: ten sam dropdown.

### P5 — wiersz lematu

Jeden `LemmaRow(lemma, gloss, pos, trailing)` dla: CandidateRow, VoiceCandidateRow, ChoiceTile(showActions), RelatedWordsList, SuggestionTile (selected state jako parametr).

### P6 — karta native

Ścieżka długa: `CardDetailContent` vs `FlashcardBackContent`. Na standaryzację UX warto najpierw spisać, **które sekcje** widać w Practice vs overlay listy vs (ew.) Learning, i czy Settings (usages/examples/conjugation) mają działać też w overlayu listy. Dziś overlay pokazuje „wszystko”, Practice honoruje ustawienia.

### P7 — porządki nawigacji

- Usunąć albo podpiąć `PROFILE` / `PACKS` / `LEARNING`.
- Jeśli Profile ma wrócić: nie duplikować CEFR/czasów — to już jest w Settings.
- Jeśli Learning ma wrócić: nie duplikować overlayu karty.
- Wyloguj: dodać `destructive` dialog (spójnie z usuwaniem).

### P8 — empty / error

- Puste Listy i Dodaj → `EmptyState`.
- Błędy inline → wspólny kolor/typografia; import error może zostać modalem (blocking).
- Retry tylko tam, gdzie akcja jest jasna (Practice już ma).

---

## 9. Szybka checklista „czy to ten sam flow?”

Przy projektowaniu komponentu sprawdź, czy nie istnieje już:

| Szukasz | Istnieje w |
|---|---|
| Pytać o listę docelową | `AddToListSheet`, Import start, 3× Move dialog |
| Pytać o nazwę listy | Listy create, AddToList create, Import create |
| Potwierdzić usunięcie | 4 dialogi w Listach + import abort |
| Dodać słowo | Dodaj, głos, practice choice, related |
| Poprawić kartę | Listy kafelek, Practice rewers |
| Pokazać kartę | overlay listy, Practice rewers, Learning |
| Język / CEFR / czasy | Onboarding, Settings, (Profile) |
| Wybór z listy opcji | Settings radio, Onboarding radio, Sort sheet, Filter chips, Tense modal |
| Kandydat lookup | CandidateRow, VoiceCandidateRow, SuggestionTile |

---

## 10. Pliki-kotwice (gdzie klikać w kodzie)

| Obszar | Plik |
|---|---|
| Nawigacja | `ui/VocabularioAppRoot.kt` |
| Tokeny + wspólne cegiełki | `ui/components/AppComponents.kt` |
| Dialog karty | `ui/card/CardSheetDialogs.kt` |
| Home + ~12 dialogów list | `ui/home/HomeScreen.kt` |
| Import dialogi | `ui/home/ImportUi.kt` |
| Dodaj do listy | `ui/components/AddToListSheet.kt` |
| Głos | `ui/home/voice/VoiceSearchSheet.kt` |
| Practice | `ui/practice/PracticeScreen.kt` |
| Settings + tense modal | `ui/settings/SettingsScreen.kt` |
| Correction / history / self-edit | `ui/card/CardCorrectionFlow.kt`, `CardSelfEditSheet.kt`, `CardSelfEditWarningDialog.kt` |
| Review pending | `ui/card/PendingReviewSheet.kt` |
| Overlay karty | `ui/card/ListCardDetailOverlay.kt` |
| Rewers flashcard | `ui/card/FlashcardBackContent.kt` |
| Szczegóły karty (listy) | `ui/card/CardDetailContent.kt` |
| Onboarding | `ui/onboarding/OnboardingScreen.kt` |
| Martwe | `ui/profile/ProfileScreen.kt`, `ui/learning/LearningScreen.kt`, `ui/packs/PacksScreen.kt` |
