# Plan implementacji — standaryzacja UI (dialogi, kolory, inputy)

Decyzje z uwag (sierpień 2026). Ten dokument **nie implementuje** zmian — opisuje co, gdzie i w jakiej kolejności. Inwentarz wyjściowy: [ui-ux-inwentarz-standaryzacja.md](ui-ux-inwentarz-standaryzacja.md), makiety: [ui-ux-porownanie.html](ui-ux-porownanie.html).

---

## 1. Co jest jasne (zamknięte decyzje)

### 1.1 Kolory

| Token | Nowa wartość | Zastosowanie |
|---|---|---|
| `ActionConfirm` | `#569252` | globalna zieleń zatwierdzenia (dziś `#6DCF65`) |
| `ActionTeal` (nowy) | `#74AEAB` | Historia zmian, Edytuj (odrzucona korekta) |
| Destrukcja | `colorScheme.error` | tylko Usuń / Przerwij |
| Anuluj (dialog decyzji) | `ActionCancel` / error (czerwony tekst) | 4a, 13 |
| Anuluj (destrukcja) | **bez koloru** — `onSurface` / outlined | §3 |

`BrandTeal` zostaje `#72AEAA` (auth gradient itd.). Przyciski teal z tej rundy używają **`#74AEAB`**, nie `BrandTeal`.

**Easy (ocena fiszki):** dziś `GradeKnown = ActionConfirm`. Zmiana zieleni **przefarbuje też Easy**, jeśli alias zostanie. W tej rundzie **rozdzielić**: `GradeKnown` zostaje przy starym `#6DCF65` (albo osobnym tokenie ocen), `ActionConfirm` idzie na `#569252`. Inaczej ocena i OK zlewają się w jeden odcień bez świadomej decyzji.

### 1.2 Copy przycisków w dialogach

| Rola | Etykieta | Klucz |
|---|---|---|
| Zatwierdzenie akcji | **OK** | `action_ok` |
| Odrzucenie / zamknięcie bez skutku | **Anuluj** | `action_cancel` |
| Destrukcja | **Usuń** / **Przerwij** | `action_delete` / `action_abort` |
| Środkowy w pickerze listy | **Nowa lista** | `list_new` |
| Odrzucona korekta | **Edytuj** (nie „Edytuj samodzielnie”) | `correction_edit_self` |
| Drzwi na fiszce | **Zgłoś poprawkę** (czerwony) + **Historia zmian** (teal) | `correction_fix_card` + nowy `correction_history_button` |

Nigdzie w dialogu: Wróć / Utwórz / Dodaj / Importuj / Zapisz / Zastosuj / Zatwierdź / Przenieś / Stwórz i dodaj / Zatwierdź N.

### 1.3 Chrome dialogu decyzji

- Wyśrodkowany.
- Tło: **przyciemnione + blur** (wzorzec `PairSwitchHost`: `blur(10.dp)` + `Color.Black.copy(alpha = 0.28f)`). Voice overlay ma już ciemniejszy scrim `0.52` — zostaje overlay, ale blur+dim jak reszta.
- Shape: `AppDialogShape` = **24.dp** wszędzie, w tym podgląd zwrotów (§4c).
- Typografia, paddingi, małe przyciski: referencja **Import → + Nowa lista** (`ImportUi.kt`) oraz **TensePicker** (Dialog 92%, `SettingsScreen.kt`) — **nie** `CardDialogButtonRow` 48.dp.
- Input tekstowy: szary prostokąt `surfaceVariant`, **bez** unfocused border, radius **24.dp** (dziś 14.dp w dialogach list / pill `AppButtonShape` w search).

### 1.4 Co nie jest dialogiem decyzji (nie dostaje pary Anuluj/OK)

- Overlay głosu (§4b): scrim + X, bez przycisków dialogowych.
- Zwroty na fiszce (§4c): tap w tło zamyka, brak przycisków.
- Bottom sheety (AddToList, korekta, historia, filtr/sort) — **poza tą rundą**, poza copy Anuluj tam, gdzie dziś jest Wróć w sheetcie tworzenia listy.
- Auth / onboarding Start / Ucz się / Sprawdź / oceny / Wyślij zgłoszenie.

---

## 2. Niejasności — jak je interpretuję (do potwierdzenia przy implementacji)

Jeśli któraś interpretacja jest zła, lepiej poprawić tu niż w kodzie.

| # | Niejasność | Przyjęta interpretacja |
|---|---|---|
| A | §13: „Anuluj czerwone i **OK niebieskie**” vs zieleń `#569252` wszędzie | Literówka. **OK zawsze zielony `#569252`**. W §13 nie ma OK — para to Anuluj (czerwony) + Edytuj (`#74AEAB`). |
| B | Anuluj czerwony (4a, 13) vs Anuluj bez koloru (§3) | Dwa warianty: **decyzja** = Anuluj czerwony + OK zielony; **destrukcja** = Anuluj bez koloru + Usuń/Przerwij czerwone. |
| C | Import review: `"Zatwierdź ${count}"` | Zostaje samo **OK** (count widać w treści). |
| D | Filtr listy: **Zastosuj**; Settings limit: **Zatwierdź**; self-edit sheet: **Zapisz**; TensePicker: **Zatwierdź** | TensePicker i wszystkie **AlertDialog** → OK. **Zapisz** na sheetcie self-edit i **Zastosuj** na filtrze — sheety, poza rundą; jeśli mają wyglądać jak dialog, wtedy też OK. Limit dzienny to przycisk **w akordeonie**, nie modal — zostawiam `action_confirm` do osobnej decyzji (propozycja: też OK, ten sam zielony). |
| E | Dwa zielone obok siebie w pickerze listy (Nowa lista + OK) | Świadome: oba `#569252`. Nowa lista outlined/filled mniejszy na środku, OK filled z prawej — ten sam kolor, inna waga (Nowa lista `OutlinedButton` z zielonym tekstem/obwódką, OK `Button` filled). Jeśli oba filled będą nieczytelne, Nowa lista = outlined zielony. |
| F | „Wszystkie inputy” vs dropdowny §6/§8 | **Pola wpisywane** = szary rect 24.dp. **Dropdowny** (język, CEFR) = `SettingsDropdown` pill + surface. Search na Dodaj jest polem wpisywanym → szary 24, nie pill. |
| G | Auth email/hasło, practice „wpisz słowo”, notatka korekty | Też pola wpisywane → ten sam `AppGrayField`. |
| H | Import start: przycisk **Importuj** | Modal → **OK**. |
| I | Import wynik: OK + „Pokaż listę” | OK zielony; „Pokaż listę” zostaje jako tertiary/text (nie Anuluj). |
| J | Wyloguj | Brak modala potwierdzenia dziś. Zostaje przycisk Settings, bez zmiany. |
| K | §9 skórka sheetów | Nie w tej rundzie. |
| L | Onboarding CEFR (radio) vs Settings dropdown | Ta runda dotyczy **Settings**. Onboarding CEFR nie był w uwagach — zostawiam radio, chyba że przy okazji §8 (dropdown języka) ujednolicimy też CEFR na onboarding. |

---

## 3. Tokeny i wspólne composable (fundament)

Bez tego każdy dialog będzie znowu inny.

### 3.1 `Theme.kt`

```
ActionConfirm = Color(0xFF569252)
ActionTeal    = Color(0xFF74AEAB)   // nowy
GradeKnown    = Color(0xFF6DCF65)   // odpiąć od ActionConfirm
tertiary      = ActionConfirm       // Material tertiary = zieleń OK
```

### 3.2 Nowe / zmienione composable (`AppComponents.kt` + `CardSheetDialogs.kt`)

1. **`AppGrayField`** — `OutlinedTextField` z:
   - `containerColor = surfaceVariant`
   - `unfocusedBorderColor = Transparent`
   - `focusedBorderColor = outline` (cienki, jak search dziś)
   - `shape = RoundedCornerShape(24.dp)`
   - placeholder `onSurfaceVariant`
   - używany wszędzie zamiast 14.dp / pill / gołego OutlinedTextField

2. **`AppModalScrim`** — pełnoekranowy host:
   - treść pod spodem: `Modifier.blur(10.dp)`
   - overlay: czarny 0.28f, zjada kliknięcia
   - karta na środku: `Surface(shape = AppDialogShape)`, max szer. ~92% (jak TensePicker)
   - **nie** `AlertDialog` Material — osobne okno nie rozmywa activity. Wzorzec: `PairSwitchHost` + custom `Dialog(usePlatformDefaultWidth = false)`.

3. **`AppDialogButtonRow`** — małe przyciski (wysokość domyślna Material / max ~36–40.dp, **nie 48**), `AppButtonShape`, układ:
   - 2 przyciski: Anuluj | OK (lub Usuń)
   - 3 przyciski pickera: Anuluj | Nowa lista | OK
   - warianty koloru: `Confirm` / `Destroy` / `Teal` / `Neutral` / `CancelRed`

4. **`AppAlertDialog`** — title + opcjonalny body + `AppDialogButtonRow`. Jeden padding (np. 20–24.dp), title `titleMedium`/`titleLarge` z mniejszym odstępem do body gdy title wrapuje (uwaga §13).

5. **`CardDialogButtonRow`** — albo usunąć 48.dp i delegować do `AppDialogButtonRow`, albo przestać używać.

Token `AppDialogShape` już jest 24.dp — tylko **dopiąć** (usages peek ma 16.dp).

---

## 4. Spec per ekran / numer uwagi

### § global — kolory i copy

Przejść wszystkie `AlertDialog` / `CardBlockingAlertDialog` / custom `Dialog` i podmienić etykiety wg tabeli 1.2. Potem kolory przycisków.

Pliki: `HomeScreen.kt`, `ImportUi.kt`, `SettingsScreen.kt`, `CardSheetDialogs.kt`, `CardSelfEditWarningDialog.kt`, `CardCorrectionFlow.kt`, `PracticeScreen.kt`, `AddToListSheet.kt` (Wróć → Anuluj).

### §1 Jak nazwać nową listę?

Dziś kilka wariantów treści (czysta nowa lista / import / utwórz-i-przenieś). **Zostają różne body**, jedna ramka:

- `AppAlertDialog` na środku, scrim+blur
- `AppGrayField` (placeholder `list_name_hint`)
- Anuluj (czerwony, mały) + OK zielony
- Dziś confirm = `action_create` / `list_create_and_add` → **OK**
- Miejsca: `HomeScreen` `showCreate`, `ImportUi` gałąź `creatingNew`, `AddToListSheet` prompt nazwy (sheet — Anuluj zamiast Wróć; confirm sheetu zostaje Dodaj **albo** OK jeśli uznamy to za ten sam modal; rekomendacja: ten prompt wydzielić do `AppAlertDialog` jak Listy, wtedy OK)

### §2 Do której listy?

**Jeden** nowy composable `MoveToListDialog` zamiast 3× skopiowanego `AlertDialog` w `HomeScreen` (słowo / zaznaczone / wszystkie) + analog w imporcie jeśli picker listy ma ten sam job.

Układ:

- Title: `list_move_to` / `list_pick_target` (zależnie od kontekstu)
- Większy odstęp między sekcjami (lista radio vs stopka) — dziś za ciasno
- Stopka **3 przyciski**: Anuluj (lewo, czerwony jak decyzja) | **Nowa lista** (środek, `#569252`) | **OK** (prawo, filled `#569252`)
- „Nowa lista” **nie** jest `TextButton` pod listą — jest trzecim przyciskiem. Klik otwiera modal §1; po OK wraca do pickera z nową listą zaznaczoną, albo od razu wykonuje move — zachować dzisiejszy flow `createThenMove*`

### §3 Potwierdź usunięcie / destrukcję

Miejsca:

| Dialog | Title (zostaje) | Body (usuń) | Confirm |
|---|---|---|---|
| Usuń listę | `list_delete_confirm_title` | `list_delete_confirm_body` | Usuń |
| Wyczyść Uczę się | `list_clear_all_title` | `list_clear_all_body` | zostaje etykieta czyszczenia / Usuń — **ustalić**: dziś `list_clear_all`; propozycja: **Usuń** albo zostawić „Wyczyść”, ale czerwony jak destrukcja |
| Usuń słowo | `list_delete_word_confirm` | brak / krótki | Usuń |
| Usuń zaznaczone | `list_delete_selected_title` | `list_delete_selected_body` | Usuń |
| Przerwij import | `import_abort_title` | `import_abort_body` | **Przerwij** |
| Wyloguj | — | — | bez zmian (brak modala) |

Wszędzie: **tylko pytanie + 2 przyciski**. Anuluj (nie Wróć) **bez koloru**. Usuń/Przerwij czerwone, małe.

`list_delete_word_confirm` i `list_delete_confirm_title` już są pytaniami — OK. Body do wycięcia tam, gdzie jest.

### §4a Dialog decyzji — chrome + self-edit warning

Chrome: TensePicker (92%, małe Anuluj/OK).

`CardSelfEditWarningDialog`:

- Title: **„Potwierdzasz zmiany?”** → nowy copy `self_edit_warning_title`
- Body: bez zmiany merytoryki (`self_edit_warning_body` + lista issue z API)
- Ikona ostrzeżenia + body **czerwone** (warning, nie zwykły opis)
- Przyciski małe: **Anuluj** (czerwony, dziś „Wycofaj zmiany”) + **OK** (zielony, dziś „Zatwierdź zmiany”)
- Zachować zachowanie: Anuluj = revert, OK = apply

To samo chrome dla: review pending, correction accepted (tylko OK), import start/review/error/result (result ma extra „Pokaż listę”).

### §4b Overlay narzędzia (głos)

Zostaje `VoiceSearchSheet` jako Dialog (nie sheet): ciemny scrim + X. Dodać **blur** tła jak globalnie. Nie konkurować z 4a.

### §4c Lekki podgląd zwrotów

`FlashcardBackContent.kt` — `RoundedCornerShape(16.dp)` → `AppDialogShape` (24.dp). Treść bez zmian. Tap poza zamyka. Scrim+blur jak globalnie (dziś Dialog bez blura).

### §5 Wiersz słowa

Standard: `CandidateRow` (`HomeScreen.kt`) — `AppCard` 18.dp, koło + 40.dp.

Dopiąć do tego:

- `VoiceCandidateRow` (`VoiceSearchSheet.kt`) — dziś `AppDialogShape` + `surfaceVariant`, inny padding
- `ChoiceTile(showActions)` (`AppComponents.kt`)
- `RelatedWordsList` (`FlashcardBackContent.kt`) — koło 40.dp już jest, karta może się różnić

Wydzielić `LemmaActionRow(lemma, gloss, trailing)` jeśli da się bez rzeźni.

### §6 CEFR w Settings

Akordeon **Poziom**:

- Usunąć **subtitle** pod tytułem (`state.cefrLevel`)
- Usunąć **divider** w expanded (tylko w tej sekcji, albo parametr `showDivider = false`)
- Usunąć label dropdownu `settings_cefr_known` („Znajomość języka uczonego”)
- Zostaje: tytuł **Poziom** + `SettingsDropdown` **bez labelki**, wartość = aktualny CEFR (A1–C2)

Dropdown nadal pill + surface.

### §7 Czasy

Bez zmiany flow: radio Wszystkie / Wybrane + Edytuj → modal `TensePicker`. Tylko chrome modala (małe Anuluj/OK, 24.dp, blur). Zatwierdź → OK.

### §8 Dropdown języka

`SettingsDropdown` pill + surface — już w Settings. Onboarding `LangDropdown` **podmienić na ten sam** `SettingsDropdown` (uwaga z inwentarza).

### §10 Input radius

Wszystkie pola wpisywane: **24.dp** przez `AppGrayField`. Nie 14 / pill / default Outlined.

Miejsca do podmiany: Listy (create/rename/move), Import paste + nowa lista, AddToListSheet, search Dodaj, Auth, Onboarding (jeśli jakieś text), Settings limit dzienny, self-edit fields, correction note, practice type-answer.

### §11 Drzwi „Popraw kartę”

Zostaje **inny** wejście niż overlay szczegółu karty. Na Practice (`PracticeScreen.kt` ~391–413) `TextButton` z copy:

- `correction_fix_card`: **Zgłoś poprawkę**, kolor error/czerwony, wygląd **Button** (nie nagi tekst)
- nowy `correction_history_button`: **Historia zmian**, `#74AEAB`

Na liście (`HomeScreen` ikony) zostają ikony — to inne drzwi, zgodnie z „zostaw inaczej”.

### §12 Pusty stan

Wzorzec: Listy (`list_empty`) — `Text` `bodyLarge`, `onSurfaceVariant`, padding ~40.dp, bez drugiej linii.

Zmienić:

- Practice: `EmptyState(practice_empty, practice_empty_hint)` → sam `practice_empty`, padding 40–56, **bez hintu**
- Dodaj: już goły Text (`import_empty_hint`) — OK, dopiąć padding 40–56 jeśli inny
- `EmptyState` zostawić albo uprościć; `LearningScreen` (martwa trasa) analogicznie

### §13 Przycisk wtórny + odrzucona korekta

- Wtórny w dialogu = `OutlinedButton` (jak start importu).
- `CardCorrectionResultDialog` rejected: **dwa** przyciski, bez OK:
  - Anuluj — czerwony, outlined
  - **Edytuj** — `#74AEAB` (skrócić `correction_edit_self`)
- Title vs body: zmniejszyć `spacedBy` / padding pod `titleLarge` gdy title wrapuje („Zgłoszenie nie zostało przyjęte” itd.), żeby nagłówek siadał bliżej opisu, a nie jak osobna sekcja.

Accepted: nadal pojedyncze OK zielone, małe.

---

## 5. Mapowanie dialogów → nowy wariant

| Dziś | Plik | Nowy wariant |
|---|---|---|
| Nowa lista / rename | `HomeScreen.kt` | §1 gray field, Anuluj+OK |
| Import + Nowa lista | `ImportUi.kt` | ten sam §1 |
| 3× Przenieś | `HomeScreen.kt` | `MoveToListDialog` §2 |
| Usuń listę/słowo/zaznaczone, wyczyść | `HomeScreen.kt` | §3 bez body |
| Import abort | `ImportUi.kt` | §3 Przerwij |
| Import start / review / result / error | `ImportUi.kt` | 4a chrome, confirm=OK |
| TensePicker | `SettingsScreen.kt` | 4a (już najbliżej) |
| Self-edit warning | `CardSelfEditWarningDialog.kt` | 4a + czerwony warning |
| Pending review | `PendingReviewSheet.kt` | 4a małe przyciski |
| Correction result | `CardCorrectionFlow.kt` | accepted=OK; rejected=§13 |
| Voice | `VoiceSearchSheet.kt` | 4b + blur |
| Usages peek | `FlashcardBackContent.kt` | 4c 24.dp + blur |
| Filter/sort sheets | `HomeScreen.kt` | poza rundą |
| AddToList / Correction / History sheets | *Sheet.kt | poza rundą (copy Anuluj w create) |
| Practice empty back | `PracticeScreen.kt` | to nawigacja, nie dialog — `action_return` zostaje |

---

## 6. Kolejność wdrożenia

Każdy krok ma być merdżowalny osobno.

1. **Tokeny** — `Theme.kt` (`ActionConfirm`, `ActionTeal`, split `GradeKnown`). Zero layoutu. Sprawdzić Easy na fiszce.
2. **`AppGrayField` + `AppDialogButtonRow` + `AppModalScrim` / `AppAlertDialog`**. Jeszcze nie podłączać wszystkich call site’ów.
3. **Stringi** — nowe/zmienione klucze w `values` + `values-pl` od razu; pozostałe 15 locale w tym samym PR albo tuż po (inaczej EN fallback — patrz audyt i18n).
4. **Wydzielić dialogi z `HomeScreen.kt`** (~12 `AlertDialog`) do `ui/home/ListDialogs.kt`: create, rename, destroy, `MoveToListDialog`.
5. **ImportUi + TensePicker + CardBlocking\*** — ten sam chrome, małe przyciski, OK.
6. **Self-edit warning + correction rejected** (4a + 13).
7. **Blur host** — podpiąć pod wszystkie decyzje + voice + usages. Najtrudniejszy krok technicznie (AlertDialog → custom Dialog).
8. **Settings CEFR + onboarding language dropdown**.
9. **CandidateRow** unifikacja, Practice drzwi-przyciski, empty states, inputy 24.dp w pozostałych formularzach.

Nie zaczynać od HomeScreen „w miejscu” bez kroku 2 — skończy się 12. kopią paddingów.

---

## 7. Nowe / zmienione stringi

Wszystkie 17 plików `values*/strings.xml` (albo najpierw `values` + `values-pl`, reszta w PR i18n).

| Klucz | PL (docelowo) | Uwaga |
|---|---|---|
| `self_edit_warning_title` | Potwierdzasz zmiany? | nadpisanie |
| `self_edit_warning_confirm` | nieużywany → `action_ok` | można zostawić alias |
| `self_edit_warning_revert` | nieużywany → `action_cancel` | j.w. |
| `correction_fix_card` | Zgłoś poprawkę | dziś „Popraw kartę”; w wielu locale nadal ang. „Fix card” |
| `correction_history_button` | Historia zmian | **nowy** — nie reuse `card_history_title` (sheet nadal „Historia karty”) |
| `correction_edit_self` | Edytuj | skrót |

Klucze `action_create`, `action_apply`, `import_action_start`, `list_create_and_add` zostają w XML na razie (mogą być martwe po podmianie na `action_ok`) — posprzątać w PR stringów.

---

## 8. Pliki (orientacyjnie)

```
android/.../ui/theme/Theme.kt
android/.../ui/components/AppComponents.kt      // field, empty, dialog host
android/.../ui/card/CardSheetDialogs.kt         // małe przyciski
android/.../ui/home/HomeScreen.kt               // dialogi → extract
android/.../ui/home/ListDialogs.kt              // NOWY
android/.../ui/home/ImportUi.kt
android/.../ui/home/ImportUi.kt (inputy)
android/.../ui/home/voice/VoiceSearchSheet.kt
android/.../ui/settings/SettingsScreen.kt
android/.../ui/onboarding/OnboardingScreen.kt
android/.../ui/practice/PracticeScreen.kt
android/.../ui/card/CardSelfEditWarningDialog.kt
android/.../ui/card/CardCorrectionFlow.kt
android/.../ui/card/FlashcardBackContent.kt
android/.../ui/card/PendingReviewSheet.kt
android/.../ui/components/AddToListSheet.kt
android/.../ui/auth/AuthScreen.kt               // AppGrayField
android/.../res/values*/strings.xml
```

Testy: `ImportJobStateTest` bez UI; dodać mały test shape/token jeśli jest Paparazzi — **nie ma**. Checklist ręczny: każdy modal z inwentarza § dialogi.

---

## 9. Poza zakresem tej rundy

- Skórka bottom sheetów (§9 galerii)
- Martwe trasy PROFILE / LEARNING / PACKS (chyba że empty state przy okazji)
- Treść fiszki, oceny (poza splitem `GradeKnown`)
- Backend / import pipeline

---

## 10. Kryteria gotowości

- Żaden `AlertDialog` decyzji nie ma 48.dp buttonów ani radius ≠ 24.
- Żaden dialog nie pokazuje Wróć / Utwórz / Importuj / Zatwierdź N jako confirm.
- Otwarty modal → tło rozmyte i przyciemnione (API 31+ blur; poniżej: przynajmniej dim 0.28).
- CEFR: tylko „Poziom” + dropdown z bieżącą wartością.
- Practice: dwa prawdziwe buttony, nie TextButton-linki.
- Easy nadal stary odcień; OK nowy `#569252`.
- `values-pl` i `values` zsynchronizowane z nowym copy; pozostałe locale nie spadają na angielski dla nowych kluczy (patrz [i18n-audyt-tekstow.md](i18n-audyt-tekstow.md)).
