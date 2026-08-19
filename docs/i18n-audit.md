# Audyt i18n UI (Android)

Data: 2026-08-18  
Zakres: teksty widoczne w aplikacji (Compose / ViewModele / powiadomienia) oraz słowniki `strings.xml` dla 16 języków UI + fallback EN.

## Werdykt

Teksty UI są w modelu **klucz → tłumaczenie** (`R.string.*` / `stringResource` / `UiStrings.get`). Nie ma hardkodowanych napisów produkcyjnych w Compose.

Słowniki locale są **kompletne kluczami**: 17 katalogów `values*` × **511** identycznych kluczy. Po audycie uzupełniono puste EN, stale kopie angielskiego w zgłoszeniach kart oraz brakujące placeholdery `%1$s` / `%2$s`.

`scripts/check_ui_strings.py` po poprawkach: **OK** (te same klucze, brak pustych stringów, placeholdery zgodne z EN, brak niedozwolonych kopii EN).

## Architektura

| Warstwa | Rola |
|---|---|
| `android/app/src/main/res/values/strings.xml` | Źródło EN (fallback Androida) |
| `values-en/` | Kopia EN (sync 1:1 z `values/`) |
| `values-{ar,de,es,fr,hi,it,ja,ko,pl,pt-rBR,pt-rPT,ru,tr,vi,zh}/` | 16 języków UI z `locales_config.xml` / `SUPPORTED_UI_LANGS` |
| `UiStrings` | Ten sam katalog, ale z ViewModeli (honoruje locale aplikacji) |
| `string-array month_names` | 12 miesięcy w każdym locale |
| `scripts/i18n_pack.json` | Paczka pomocnicza do `i18n_apply.py` (zsynchronizowana z XML) |

Nazwy języków w ustawieniach (`العربية`, `Deutsch`, …) są **endonimami** w `Constants.kt` — to etykiety kodów ISO, nie chrome UI.

## Czy UI idzie przez klucze?

**Tak.** Ekrany Compose biorą copy z `stringResource(R.string.*)`, błędy API z mapy kod → `R.string.*` (`ApiErrors.kt`), powiadomienia z `NotificationHelper`.

Wyjątki (nie są lukami tłumaczeń):

- `BuildConfig.DEBUG`: napis `DEBUG API: …` na ekranie logowania — tylko build debug.
- Interpolacje techniczne: `[ipa]`, `• item`, liczby, ISO języka na chipie (`EN`, `ES→EN`).
- Treść kart (lematy, glosy, przykłady) — dane użytkownika / LSP, nie UI.

## Stan słowników (po uzupełnieniu)

| Locale | Klucze | Braki | Puste | Kopie EN (poza allowlistą) | Placeholdery ≠ EN |
|---|---:|---:|---:|---:|---:|
| values (EN fallback) | 511 | 0 | 0 | — | — |
| values-en | 511 | 0 | 0 | sync z EN | 0 |
| pl, de, es, fr, it, pt-BR, pt-PT, zh, ja, ko, ar, ru, hi, tr, vi | 511 | 0 | 0 | 0 | 0 |

Allowlista celowych zbitek z EN (marka / cognate / skrót): `app_name`, `action_ok`, `Quiz`, `Start`/`Stop`, `A → Z`, `ipa: …`, `System`, oraz wyrazy typu *Email* / *Lemma* / *Filter* tam, gdzie to standard UI danego języka.

`string-array month_names` jest we wszystkich 17 plikach (12 pozycji, przetłumaczone).

## Braki znalezione i uzupełnione

### 1. Pusty klucz EN

`home_relative_day_after` w `values/` i `values-en/` był pusty (PL miało „pojutrze”, reszta locale też). Kod omija pusty string i pokazuje dzień tygodnia — w EN nie było więc „the day after tomorrow”.

Uzupełniono: **the day after tomorrow**.

### 2. Stare angielskie copy zgłoszeń kart

EN zmienił znaczenie kilku kluczy (`Check and fix card`, `Send for verification`, `Card "%1$s". %2$s`), a część locale została przy starym tekście:

- **Pozostawiony angielski** (ar, de, es, fr, hi, pt-BR, pt-PT, ru, zh): `correction_report_title`, `correction_submit`, `correction_result_accepted_title`, `correction_result_rejected_title`, `correction_result_rejected_body`.
- **Stare tłumaczenie bez placeholderów** (it, ja, ko, tr, vi): `correction_result_rejected_body` nadal opisywało „edytuj kartę na własne ryzyko” zamiast `Card "%1$s". %2$s`. To psuło `stringResource(..., lemma, message)` — Android wymaga tych samych `%1$s` / `%2$s`.

Wszystkie 14 locale dostały aktualne tłumaczenia zgodne z EN/PL i z placeholderami.

### 3. Drobne kopie EN

- DE: `action_filter_active` / `filter_title` → **Filtern** (spójnie z `action_filter`).
- PL: `card_history_diff_lemma` → **lemat:** (jak `correction_field_lemma`).

## Klucze zdefiniowane, ale nieużywane w kodzie

~89 kluczy jest w XML, lecz nie ma `R.string.*` w `android/app/src/main`. To nie dziury w słownikach — to martwe / odłożone copy. Wartości są przetłumaczone we wszystkich locale.

Przykłady:

- Treści dialogów, których UI pokazuje tylko tytuł (`list_delete_confirm_body`, `list_clear_all_body`, `import_abort_body`, `import_discard_body`).
- Stare ustawienia: `settings_tolerate_typos*`, `settings_tense_labels*`, `settings_notif_study` / `settings_notif_cards` (ekran używa `settings_notif_enabled`).
- Statystyki home nieużywane na dashboardzie: `home_due_now`, `home_forecast_title`, `home_learning_now`, …
- Przyciski ogólne bez wywołań: `action_apply`, `action_save`, `action_undo`, `add_word_title`, …

Nie usuwano ich w tym audycie (mogą wrócić albo być użyte z XML/testów).

## Poza `strings.xml`

### `TenseUiLabels.kt`

Fallback nazw czasów, gdy LSP nie przyśle `tense_labels_app`. To **nie** jest katalog `strings.xml`.

- Nauka **angielskiego**: etykiety dla wszystkich 16 języków UI.
- Pozostałe L2: zwykle tylko **EN + język uczony + PL**.

Jeśli UI jest np. hiszpański, a nauka to niemiecki, nagłówek odmiany może nie dostać tłumaczenia z tego fallbacku (zostaje nazwa L2 z `LanguagePacks` / LSP). `LanguagePacks.kt` trzyma nazwy w języku uczonym — tak ma być.

To jedyna większa luka „słownikowa” poza XML. Źródłem prawdy dla produkcji ma być LSP `ui_meta`.

### `scripts/i18n_pack.json`

Przed audytem paczka miała ~200 kluczy / język (ok. 310 braków względem XML). Zsynchronizowano z aktualnymi `strings.xml` (511 kluczy × 14 locale).

## Co zmieniono w kodzie / zasobach

- Uzupełnione `strings.xml` we wszystkich locale (74 podmiany) + sync `values-en`.
- `scripts/check_ui_strings.py`: wykrywa puste wartości i rozjazd placeholderów.
- `scripts/i18n_pack.json`: pełny dump z XML.

## Jak sprawdzić ponownie

```bash
python scripts/check_ui_strings.py
```
