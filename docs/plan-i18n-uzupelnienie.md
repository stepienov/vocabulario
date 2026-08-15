# Plan implementacji — uzupełnienie kluczy i tłumaczeń UI

Cel: w każdym języku obsługiwanym przez UI **żaden** tekst z `strings.xml` nie spada na angielski fallback i nie zostaje jako skopiowany EN (poza krótką allowlistą znaków / marek).

Źródło diagnostyki: [i18n-audyt-tekstow.md](i18n-audyt-tekstow.md). Ten dokument opisuje **jak to wdrożyć**, nie powtarza całego katalogu 433 kluczy.

---

## 1. Zakres

### W środku

- 16 języków UI z `locales_config.xml` + `SUPPORTED_UI_LANGS` = **17 plików**:
  `values` (EN default), `values-en`, `values-pl`, `values-es`, `values-zh`, `values-hi`, `values-ar`, `values-fr`, `values-pt-rBR`, `values-pt-rPT`, `values-ru`, `values-de`, `values-it`, `values-ja`, `values-ko`, `values-tr`, `values-vi`.
- Uzupełnienie **66 brakujących kluczy** w 15 plikach (wszystkie poza `values/` i `values-pl`).
- Tłumaczenie kluczy, które **są**, ale mają identyczny tekst co EN (`values/strings.xml`).
- Usunięcie 4 martwych extra kluczy `review_status_*`.
- Synchronizacja `values-en` z `values/` (dziś 371 vs 433).
- CI: ten sam zestaw kluczy wszędzie; raport „skopiowany EN”.

### Świadomie poza tą rundą

| Temat | Dlaczego |
|---|---|
| Nowe copy ze [standaryzacji UI](plan-standaryzacja-ui.md) (`correction_history_button`, zmiana title warning, OK wszędzie) | Inne zadanie. Jeśli UI wejdzie wcześniej — **włożyć nowe klucze do tego samego PR stringów**, nie zostawiać ich tylko w EN/PL. |
| POS w `Constants.kt` | Nie XML; osobny ticket (albo przeniesienie do `pos_*`). |
| `userMessage()` / `detail.message` z backendu | Leak EN z API, nie brak klucza XML. |
| `issue.label` / `issue.message` / `reason` korekty | Tekst z serwera. |
| Etykiety czasów `LanguagePacks` | Pedagogiczne L2, nie UI lang. |
| Endonimy języków (`Polski`, `Español`) | Zostają. |
| Treść kart (lemma, gloss, nazwy list usera) | Dane, nie UI. |

---

## 2. Stan wyjściowy (sierpień 2026)

`scripts/check_ui_strings.py` **już dziś padnie**: baza 433 klucze, 15 locale po 371 + 4 extra.

| Plik | Klucze | Brak | Extra | Identyczne z EN* |
|---|---|---|---|---|
| `values/` | 433 | 0 | 0 | (źródło EN) |
| `values-pl` | 433 | 0 | 0 | 8 (prawie same allowlista) |
| `values-en` | 371 | 66 | 4 | n/d |
| `values-it` | 371 | 66 | 4 | 27 |
| `values-ja`, `ko`, `tr` | 371 | 66 | 4 | 21 |
| `values-vi` | 371 | 66 | 4 | 23 |
| `values-es` | 371 | 66 | 4 | 88 |
| `values-de` | 371 | 66 | 4 | 101 |
| `values-ar`, `fr`, `hi`, `pt-rBR`, `pt-rPT`, `ru`, `zh` | 371 | 66 | 4 | 102 |

\* pomijając `app_name` i `action_ok`.

Dwie warstwy dziury:

1. **Brak klucza** → Android bierze EN z `values/`. 66 kluczy: historia karty, self-edit warning, kody korekty, pending review, część voice, `list_delete`, `err_word_on_list`, `status_needs_review`. Lista: audyt §1.1.
2. **Klucz jest, tekst = EN** → user „ma tłumaczenie”, ale widzi angielski. ~110 unikalnych kluczy; najgorzej ar/de/fr/hi/pt/ru/zh (blok wklejony skryptem `add_f4_f6_strings.py`). it/ja/ko/tr/vi były generowane `translate_ui_strings.py` i są bliżej kompletne jakościowo, ale **też bez 66**.

Wolumen do zebrania (szacunek):

- 14 locale × 66 missing ≈ **924** nowych wpisów (`values-en` dostaje EN z bazy, bez tłumaczenia).
- Skopiowany EN: ~9×100 + ~5×22 ≈ **1000**, minus allowlista (~15 kluczy × locale).
- Razem rząd **~1800–1900** stringów do uzupełnienia / przetłumaczenia.

---

## 3. Źródło prawdy i allowlista

### Źródło prawdy

| Rola | Plik |
|---|---|
| Zestaw kluczy + kanoniczny EN | `android/app/src/main/res/values/strings.xml` |
| Referencja znaczenia (review) | `values-pl/strings.xml` (komplet, native) |
| Locale EN explicit | `values-en` = **kopia** `values/` po syncu, zero rozjazdu |

Nie używać `values-en` jako źródła do generatora — dziś jest niekompletny. Stary `scripts/translate_ui_strings.py` czyta właśnie `values-en` i **nadpisuje cały plik** — przy tym planie go **nie odpalać as-is**.

### Allowlista identycznego EN (nie tłumaczyć na siłę)

Te wartości mogą być takie same we wszystkich locale:

| Klucz | Przykład | Powód |
|---|---|---|
| `app_name` | Vocabulario | marka |
| `action_ok` | OK | uniwersalne |
| `sort_lemma_asc` | A → Z | alfabet łaciński w UI sort |
| `sort_lemma_desc` | Z → A | j.w. |
| `card_history_diff_ipa` | `ipa: %1$s → %2$s` | skrót IPA; można zostawić `ipa` |
| `voice_start` / `voice_stop` | Start / Stop | często zapożyczenie (PL też tak ma) |

Świadomie **nie** na allowliście (trzeba przetłumaczyć, mimo że czasem wyglądają „międzynarodowo”):

- `settings_mode_choice` = `Quiz` — w PL też „Quiz”; OK zostawić, dodać do allowlisty po decyzji.
- `tab_dashboard` = `home` — to copy UI, nie marka; **przetłumaczyć** (w PL jest przetłumaczone).
- `correction_field_lemma` / `correction_section_lemma` = `Lemma` — przetłumaczyć albo „hasło” / lokalny termin.
- `auth_email` / `auth_password` — w it/vi skopiowane; przetłumaczyć tam, gdzie język tak robi (Email często zostaje — wtedy dopisać do allowlisty per-locale, nie globalnie).
- Cały blok importu (`import_start_title`, `import_result_*`, …) — to największy blob EN w it/ja/ko/tr/vi.

Allowlistę trzymać w `scripts/check_ui_strings.py` (zbiór kluczy), nie w głowie.

---

## 4. Narzędzia (krok 0, zanim XML)

Istniejące:

- `scripts/check_ui_strings.py` — tylko **zestaw kluczy** (brak / extra). Wołane z `scripts/ci_check.py`.
- `scripts/translate_ui_strings.py` — one-shot GPT dla it/ja/ko/tr/vi, źródło `values-en`, overwrite.
- `scripts/add_f4_f6_strings.py` — historyczny wklejacz EN; nie używać do uzupełniania.

Dodać / przebudować:

### 4.1 `scripts/i18n_export_gaps.py`

Wyjście: TSV/CSV (i opcjonalnie JSON) z kolumnami:

```
locale | key | status | en | pl | current
```

`status`:

- `missing` — nie ma klucza
- `en_copy` — wartość == EN i klucz ∉ allowlista
- `ok` — pomijane w eksporcie (albo osobny plik pełny)

To jest **lista do zebrania tłumaczeń**. Jeden plik na locale albo jeden duży z filtrem. Commitować artefakt `docs/i18n-gaps.tsv` w PR narzędziowym, żeby review widział zakres.

### 4.2 `scripts/i18n_apply.py`

Wejście: ten sam TSV po wypełnieniu kolumny `translation`.

- Wstawia brakujące `<string>` w stabilnej kolejności (kolejność z `values/strings.xml`).
- Nadpisuje tylko wiersze `en_copy` / `missing`.
- **Nie rusza** już przetłumaczonych wartości.
- Escaping Android: `%1$s`, `&amp;`, `\'`, `\"`.
- Usuwa extra `review_status_*`.

### 4.3 `scripts/translate_ui_strings.py` → tryb merge

Zmiany:

- Źródło: `values/strings.xml`, nie `values-en`.
- Locale: wszystkie poza `values` / `values-en` / `values-pl`.
- Tłumacz **tylko** `missing` + `en_copy`.
- Model: ten sam stack co backend (`OPENAI_API_KEY`), prompt: zachowaj placeholdery, Vocabulario, ton UI, dla `pt-rBR` vs `pt-rPT` osobne instrukcje wariantu.
- Output: TSV do review, **albo** od razu XML przez `i18n_apply.py`.
- Po GPT: obowiązkowy pass na PL-EN parze jako QA (nie merge’ować ślepo).

### 4.4 Rozszerzyć `check_ui_strings.py`

Fail gdy:

1. inny zestaw kluczy niż baza (już jest),
2. extra klucze (już jest),
3. **nowe:** `en_copy` poza allowlistą — flaga `--strict-copy` w CI po zakończeniu tłumaczeń; do czasu wypełnienia TSV tylko raport (exit 0) żeby nie blokować innych PR.

Opcjonalnie: identyczna kolejność kluczy jak w `values/` (łatwiejszy diff) — nie wymagać w CI na start.

---

## 5. Kolejność wdrożenia

Każdy krok = osobny, merdżowalny PR.

### PR A — narzędzia + raport luk

- Skrypty z §4.1–4.4 (strict-copy na razie off).
- Wygenerować `docs/i18n-gaps.tsv` (lub `docs/i18n/gaps-*.tsv`).
- Nie zmieniać jeszcze `strings.xml` poza ewentualnym formatowaniem.

**Gotowe gdy:** `python scripts/i18n_export_gaps.py` odtwarza te same liczby co §2.

### PR B — kompletność kluczy (bez jakości tłumaczeń)

Dla każdego z 15 niekompletnych plików:

1. Dodać 66 brakujących wpisów.
2. Tymczasowa wartość = EN z `values/` (żeby `check_ui_strings.py` zaczął przechodzić i UI nie crashowało na brak zasobu — crash i tak nie ma, jest fallback; tu chodzi o **równy zestaw**).
3. Skopiować `values/` → `values-en` (pełne 433).
4. Usunąć `review_status_*` wszędzie.

To jest **uzupełnienie kluczy**. Jeszcze nie zamyka EN na ekranie (te 66 nadal angielskie, ale już w pliku locale — ten sam efekt co fallback, plus `check_ui_strings` zielony).

Alternatywa lepsza jeśli PR C idzie od razu: pominąć tymczasowy EN i wstawiać od razu tłumaczenia. Wtedy B+C = jeden PR. Rozdział B jest tylko gdy tłumaczenia nie zdążą.

### PR C — zebranie i wklejenie tłumaczeń

1. Z TSV: wiersze `missing` + `en_copy`.
2. Wypełnienie:
   - **Maszyna:** `translate_ui_strings.py` w trybie merge, batche po ~80 kluczy / locale.
   - **Review:** PL jako znaczenie, EN jako źródło. Priorytet native-pass: `es`, `de`, `fr`, `pt-BR`, `pt-PT`, `it` (częściej używane pary); potem `ja`, `ko`, `zh`, `ru`, `tr`, `vi`, `ar`, `hi`.
3. `i18n_apply.py` → XML.
4. Ręczny diff: placeholdery `%1$s` / `%1$d` / `%2$s` / `%3$d` niezgubione; `\'` w it/fr; RTL w `values-ar` (znaki Unicode OK, nie odwracać `%s`).
5. `pt-rBR` vs `pt-rPT`: nie klonować 1:1 po machine translate — przynajmniej pass po czasownikach (ficheiro/arquivo, ecrã/tela) na stringach importu i settings.

**Priorytet treści w C** (gdyby ciąć na dwa commity):

1. 66 missing (historia, korekta, voice, review) — to widać w live flow.
2. Blob importu (`import_*` identyczne z EN nawet w ja/ko).
3. Korekta (`correction_*` skopiowane w ar/de/es/…).
4. Filtr/sort, notyfikacje, offline, settings leftovers.

### PR D — twardy CI

- `check_ui_strings.py --strict-copy` w `scripts/ci_check.py`.
- Zakaz merge, jeśli locale ≠ 433 kluczy albo EN-copy poza allowlistą.

---

## 6. Jak zbierać tłumaczenia (operacyjnie)

Nie rozsyłać 17 pełnych XML. Rozsyłać **tylko luki**.

1. Export TSV z PR A.
2. Kolumna `translation` pusta; `en` + `pl` zawsze wypełnione (tłumacz widzi oba).
3. Wypełnienie: GPT merge **albo** arkusz (Google Sheet z tymi samymi kolumnami) → reimport.
4. Po wklejeniu: skrypt walidujący
   - każdy klucz z luki ma niepusty `translation`,
   - `translation != en` (chyba allowlista),
   - liczba placeholderów w `translation` == EN,
   - brak gołego `%s` (u nas `%1$s`).

Review checklist per locale (15 min):

- Auth (login / hasło / Google)
- Onboarding (3 labele + Start)
- Listy: nowa lista, usuń, przenieś
- Import: start, abort, result
- Practice: oceny + pusty stan
- Korekta + self-edit warning + historia
- Głos: listening / no match / network
- Settings: języki, poziom, czasy
- Notification shade (2 kanały)

Uruchomić app z `appLang` = ten locale (Settings), nie z system locale.

---

## 7. Kryteria gotowości

- `python scripts/check_ui_strings.py` → `OK — 17 locale, po 433 kluczy`.
- `--strict-copy` → 0 `en_copy` poza allowlistą.
- `values-en` ≡ `values/` (te same klucze i wartości).
- Brak `review_status_*`.
- Wybór UI: es, zh, hi, ar, fr, pt-BR, pt-PT, ru, de, it, ja, ko, tr, vi, pl, en — **żaden** z 66 nie pokazuje się po angielsku w innym języku.
- Placeholdery: grep `%[0-9]` spójny z EN.
- Ten plan **nie** obiecuje naprawy POS / błędów API (osobno).

---

## 8. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Stary `translate_ui_strings.py` nadpisze dobre it/ja/ko/tr/vi | Tylko merge luk; backup gita |
| GPT zepsuje `%1$s` | walidator placeholderów, reject wiersza |
| `values-en` rozjedzie się znowu | CI: `values-en` musi równać się `values/` |
| UI-standaryzacja doda klucze w międzyczasie | najpierw ten PR kompletności, potem UI copy we wszystkich 17 od razu |
| pt-BR = pt-PT | osobny prompt + krótki pass ludzki |
| `tab_dashboard` = `home` w EN jako produkt | jeśli to ma zostać „home” wszędzie — wrzucić na allowlistę i nie tłumaczyć; dziś PL jest przetłumaczone, więc raczej tłumaczyć |

---

## 9. Pliki

```
android/app/src/main/res/values*/strings.xml     # 17 plików
scripts/check_ui_strings.py                      # + extra + strict-copy
scripts/ci_check.py                              # włączyć strict po PR D
scripts/i18n_export_gaps.py                      # NOWY
scripts/i18n_apply.py                            # NOWY
scripts/translate_ui_strings.py                  # przebudowa merge
docs/i18n-gaps.tsv                               # artefakt luk (PR A)
docs/i18n-audyt-tekstow.md                       # diagnostyka (bez zmian merytorycznych)
```

`scripts/add_f4_f6_strings.py` — nie używać; można usunąć w PR D jako śmieć.

---

## 10. Szacunek

| PR | Charakter | Orientacja |
|---|---|---|
| A narzędzia + TSV | kod Python | mały |
| B sync kluczy | mechaniczny XML | mały, jeśli EN placeholder |
| C tłumaczenia | 1.8k stringów + review | główna praca |
| D CI strict | 10 linii | po akceptacji jakości C |

Zależność: C może wchłonąć B. A musi być pierwsze.

Po C UI w dowolnym języku z listy LSP nie powinno robić fallbacku do angielskiego **na kluczach XML**. Reszta EN (API, POS, czasy L2) zostaje w audycie jako następne bilety.
