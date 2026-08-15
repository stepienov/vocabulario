# Audyt i18n — wszystkie teksty UI, klucze, braki, hardcoded

Stan kodu: sierpień 2026. 433 klucze w `values/strings.xml` (domyślny **EN**). Aplikacja ustawia locale UI z profilu (`appLang`), nie z systemu — Compose czyta wtedy `stringResource` / `UiStrings.get` z matching `values-*`.

Prawidłowy flow:

```
placeholder / R.string.<klucz>
        ↓
Compose: stringResource(R.string.x)
ViewModel / notyfikacje: UiStrings.get(R.string.x)  albo context.getString()
        ↓
Android resources: values-<locale>/strings.xml
        ↓
brak klucza → fallback do values/ (angielski)
```

To **nie** jest własny słownik po kluczu w Kotlinie (poza POS i czasami — §5).

---

## 1. Locale

`android/app/src/main/res/xml/locales_config.xml` + foldery:

| Folder | Język | Kluczy | vs baza 433 |
|---|---|---|---|
| `values/` | EN (default) | 433 | komplet |
| `values-pl` | polski | 433 | **komplet** |
| `values-en` | angielski (explicit) | 371 | **brak 66**, extra 4 |
| `values-ar`, `de`, `es`, `fr`, `hi`, `it`, `ja`, `ko`, `pt-rBR`, `pt-rPT`, `ru`, `tr`, `vi`, `zh` | | 371 | **brak 66**, extra 4 |

`values-en` jest **przestarzały**. Przy wybranym English Android bierze `values-en` najpierw; 66 brakujących kluczy i tak spadają na `values/` (też EN), więc EN UI działa. Szkoda: dwa źródła prawdy dla angielskiego.

**Każdy inny język oprócz PL** przy korekcie karty, historii, self-edit, review pending, voice search, `list_delete`, `err_word_on_list`, `status_needs_review` pokaże **angielski**.

### 1.1 66 kluczy tylko w `values/` + `values-pl`

```
card_history_actor_system, card_history_actor_you,
card_history_diff_conjugation, card_history_diff_content, card_history_diff_gloss,
card_history_diff_ipa, card_history_diff_lemma, card_history_diff_meanings,
card_history_diff_pos, card_history_diff_similar,
card_history_empty, card_history_event_accepted, card_history_event_report,
card_history_event_reviewed, card_history_event_self_edit,
card_history_restore, card_history_restored,
card_history_summary_report, card_history_summary_restored, card_history_title,
cd_card_history, cd_list_word_actions, cd_view_card,
correction_add_meaning, correction_add_row,
correction_code_accepted, correction_code_failed, correction_code_insufficient,
correction_code_not_applicable, correction_code_unfounded,
correction_daily_limit, correction_empty_rows_hint,
correction_field_conjugation_json, correction_field_examples, correction_field_ipa,
correction_field_l1, correction_field_l2, correction_field_notes,
correction_field_similar, correction_field_synonyms_l1, correction_field_usages,
correction_processing, correction_report_subtitle, correction_result_accepted_body,
correction_section_meaning, correction_self_edit_link,
err_word_on_list, list_delete,
review_close, review_confirm, review_did_you_mean, review_no_match,
review_reject, review_search_again, review_title,
self_edit_processing, self_edit_validating,
self_edit_warning_body, self_edit_warning_confirm, self_edit_warning_revert,
self_edit_warning_title,
status_needs_review,
voice_either_lang_hint, voice_network_required, voice_no_match, voice_searching
```

Flow, które **psują się** poza PL/EN:

- Practice / lista → Popraw kartę → self-edit warning, processing
- Historia karty (tytuł, eventy, diffy, przywróć)
- Wynik korekty (body accepted, kody result)
- Pending review (tytuł, Czy chodziło Ci o, Zatwierdź/Odrzuć)
- Voice search (Searching, no match, network)
- Usuń listę (`list_delete` w menu)
- Błąd „słowo już na liście”

Część kluczy korekty **jest** w 371 (np. `correction_fix_card`, `correction_edit_self`) — ale w ar/de/es/fr/hi/pt/ru/zh nadal po angielsku („Fix card”, „Edit myself”). To nie brak klucza, tylko **nietłumaczony copy**.

### 1.2 Extra (martwe) w locale 371

`review_status_accepted`, `review_status_rejected`, `review_status_reported`, `review_status_user_edited` — nie ma ich w `values/`. Nieużywane w Kotlinie. Posprzątać.

---

## 2. Mechanizm w kodzie

| Warstwa | API | OK? |
|---|---|---|
| Compose | `stringResource(R.string.*)` | tak |
| VM / repo / import | `UiStrings.get(R.string.*)` | tak — honoruje locale aplikacji |
| Notyfikacje | `context.getString(R.string.notif_*)` | tak, jeśli Context ma locale |
| Accessibility | `cd_*` przez `stringResource` | tak, z wyjątkiem ikon z `contentDescription = null` |
| POS | `localizedPosLabel` → `POS_LABELS` w `Constants.kt` | **omija strings.xml** |
| Czasy | `LanguagePacks` / `tense_labels_*` z karty | etykiety **L2 pedagogiczne**, nie UI lang (świadome) |
| Nazwy języków | `SUPPORTED_UI_LANGS` endonimy | świadome (Español, Polski…) |
| Błędy HTTP | `Throwable.userMessage()` | **leak angielskiego z backendu** |

`UiStrings` (`i18n/UiStrings.kt`) to cienki wrapper na `Context.getString`. Nie ma drugiego słownika.

---

## 3. Katalog tekstów wg flow

Poniżej: każdy user-visible string, klucz, gdzie. **Dane z API** (lemma, gloss, nazwa listy usera, przykłady) nie są tłumaczone — to treść karty.

### 3.1 System / chrome

| Klucz | Gdzie |
|---|---|
| `app_name` | Manifest label |
| `tab_dashboard`, `tab_add`, `tab_lists` | dolna nawigacja Home |
| `action_learn` | stały przycisk Ucz się |
| `cd_settings` | ikona Settings |
| `cd_undo` | undo oceny |
| `cd_back`, `action_return`, `action_back` | wstecz (Practice empty / dialogi — do ujednolicenia na Anuluj w dialogach, patrz plan UI) |
| `offline_banner_title`, `offline_banner_body` | banner offline |
| `creating_card`, `creating_card_failed` | spinner tworzenia karty |

### 3.2 Auth (`AuthScreen` / `AuthViewModel`)

| Klucz | Kiedy |
|---|---|
| `auth_login_title`, `auth_register_title`, `auth_tagline` | hero |
| `auth_email`, `auth_password`, `auth_password_hint` | pola |
| `auth_login`, `auth_register`, `auth_google`, `auth_have_account` | akcje |
| `err_email_required`, `err_email_invalid`, `err_password_required`, `err_password_short` | walidacja lokalna |
| `err_login`, `err_register`, `err_google_login`, `err_google_token` | błąd sieci — **plus** `userMessage` z API |

### 3.3 Onboarding (`OnboardingScreen`)

`onboarding_title`, `onboarding_subtitle`, `onboarding_native`, `onboarding_learning`, `onboarding_cefr`, `onboarding_tenses`, `onboarding_start`

CEFR: kody `A1`…`C2` z `CEFR_LEVELS` — **nie** klucze (uniwersalne).

Czasy: labele z `LanguagePacks` (język nauki).

`err_langs_must_differ`, `err_create_profile` (+ API message).

Dropdowny: endonimy z `SUPPORTED_UI_LANGS`.

### 3.4 Home — Dashboard

`home_due_now`, `home_new_today`, `home_reviewed_today`, `home_learning_now`, `home_new_left`, `home_mastered`, `home_forecast_title`, `home_words_count`, `home_new_words_count`

Dni: `weekday_mon` … `weekday_sun` (`localizedWeekday`).

Pusty wykres: **hardcoded `"—"`** (`HomeScreen.kt`).

Błąd: `err_load_stats` / API.

### 3.5 Home — Dodaj (szukaj / głos / import)

| Klucz | Kiedy |
|---|---|
| `home_search_hint`, `offline_search_hint` | placeholder search |
| `cd_search`, `cd_voice_search`, `action_add` | a11y / + |
| `import_empty_hint` | pusty stan Dodaj |
| `import_from_file`, `import_paste`, `import_online_only` | CTA |
| `list_unnamed`, POS via `localizedPosLabel` | wiersz kandydata |
| `offline_lookup_queued`, `offline_lookup_duplicate` | kolejka pending |
| `err_search`, `err_add`, `err_word_on_list`, `err_create_card` | błędy |
| Voice: `voice_*` | cały overlay |
| Import start: `import_start_title`, `import_paste_hint`, `import_add_file`, `import_other_file`, `import_file_label`, `import_how`, `import_vocab_mode`, `import_preserve_mode`, `import_vocab_hint`, `import_pick_list`, `import_new_list_option`, `import_action_start`, `import_limit_exceeded` | wizard |
| `import_status_analyzing`, `import_status_importing`, `import_progress`, `import_progress_count` | progress |
| Review: `import_review_ready`, `import_review_flagged`, `import_invalid_title`, `kind_*`, `action_confirm`+count | review |
| Abort: `import_abort_title`, `import_abort_body`, `action_abort` | §3 |
| Result: `import_result_*`, `action_ok`, `action_show_list` | done |
| `import_file_errors`, `import_no_cards`, `import_no_valid`, `import_interrupted`, `err_import*` | błędy |
| `list_name_hint`, `list_learning`, `list_pending` | nazwy list |

Bullet `"• $w"` w `ImportUi.kt` / `ImportDisplayBlocks.kt` — znak, nie copy.

Picker pliku: `it.message` z wyjątku Androida → **angielski systemowy**.

### 3.6 Home — Listy

Chip + menu: `list_learning`, `list_pending`, `list_rename`, `list_move_all`, `list_delete`, `list_clear_all`, `action_delete`, `cd_list_options`, `new_list_cd`

Pusty: `list_empty`, `list_filter_empty`, `action_clear_filters`

Meta: `list_words_meta`

Dialogi: `list_new`, `list_name_hint`, `list_name_reserved`, `list_name_taken`, `list_rename`, `list_delete_confirm_title/body`, `list_delete_word_confirm`, `list_delete_selected_title/body`, `list_clear_all_title/body`, `list_move_to`, `list_move_word`, `list_pick*`, `list_create_move_*`, `list_create_and_add`, `list_fallback`

Sort/filtr: `sort_*`, `filter_*`, `action_sort`, `action_filter`, `action_filter_active`, `action_apply`, `action_clear_all`, `filter_pos_unknown`, `status_*`

Zaznaczenie: `cd_selected`, `list_delete_selected`, `action_move`, `action_cancel`

Karta na liście: `cd_view_card`, `cd_list_word_actions`, `cd_delete`, `cd_move`, `cd_play`, `cd_on_list`, `cd_add_to_list`, `cd_card_history`, `correction_fix_card`

AddToList sheet: `action_learn` (Uczę się), `list_new`, `action_add`, `action_back` (→ Anuluj w planie UI)

### 3.7 Practice

`practice_title`, `practice_show_answer`, `action_reveal`, `action_check`, `practice_your_answer`, `practice_error_title`, `practice_bridge_l2`, `practice_bridge_means`, `practice_spelling_warn`, `practice_spelling_detail`, `practice_correct_answer`, `practice_well_done`, `grade_*`, `action_undo`

Pusty: `practice_empty` (+ dziś `practice_empty_hint` — do usunięcia z UI wg planu)

Drzwi: `correction_fix_card`, `card_history_title` (→ osobny klucz w planie)

`err_load_queue`, `err_load_options`, `err_options_count`, `err_check`, `err_save_grade`

### 3.8 Fiszka / detal karty

Sekcje: `section_*`, `no_meanings`, `periphrase_n`, `kind_*`, `card_badge_import`, `card_preparing`, `card_headword`

POS: `localizedPosLabel` (nie XML).

Czasy / osoby: pack + `ui_meta.person_labels` z karty (język etykiet wg ustawienia tense_label_lang). Fallback: `tenseKey.replace("_", " ")` — **surowy klucz angielski** (`present_simple`).

Zwroty peek: treść L1/L2 z karty, bez chrome copy.

### 3.9 Korekta / self-edit / historia / review

Sheet zgłoszenia: `correction_report_title/subtitle`, `correction_section_*`, `correction_note_*`, `correction_validation`, `correction_submit`, `correction_daily_limit`, `correction_requires_online`, `correction_self_edit_link`, `correction_processing`

Self-edit: `correction_self_edit_title`, `correction_field_*`, `correction_add_*`, `correction_empty_rows_hint`, `action_save`, `self_edit_validating`, `self_edit_processing`, `self_edit_warning_*`

Wynik: `correction_result_*`, `correction_code_*`, `correction_edit_self`, `action_ok`, `action_cancel`

Historia: `card_history_*` (cały blok w lukach 66)

Pending review: `review_*`

**Issue z walidacji self-edit:** `"• ${issue.label}: ${issue.message}"` — **angielski z API**, nie klucze.

**`item.reason`** na wyniku korekty — tekst z backendu.

### 3.10 Settings

Grupy: `settings_group_study`, `settings_group_general`

Akordeony: `settings_mode*`, `settings_tolerate_typos*`, `settings_direction*`, `settings_card_layout*`, `settings_examples`, `settings_usages`, `settings_periphrases`, `settings_syn_ant`, `settings_word_family`, `settings_conjugation`, `settings_all_tenses`, `settings_selected_tenses`, `settings_limits`, `settings_new_limit`, `settings_new_per_day`, `new_cards_per_day`, `new_cards_unlimited`, `settings_theme*`, `settings_notifications*`, `settings_notif_study/cards`, `settings_reminder_hour`, `settings_languages`, `settings_languages_summary`, `settings_langs_hint`, `settings_native_lang`, `settings_learning_lang`, `settings_tense_labels*`, `settings_level`, `settings_cefr_known` (do usunięcia z UI), `settings_label`, `action_logout`, `action_confirm`, `action_edit`, `action_cancel`

Limit dzienny: opcje `5/10/20/50` + **hardcoded `"∞"`** w `NEW_CARDS_OPTIONS` (`Constants.kt`) — znak, OK; etykieta unlimited ma klucz `new_cards_unlimited`.

Fallback kierunku: **`"L1"` / `"L2"`** gdy brak profilu (`SettingsScreen.kt`).

TensePicker: labele z packa L2 + `action_cancel` / `action_confirm`.

Błędy: `err_load_settings`, `err_save`, `err_save_tenses`, `err_learning_lang`, `err_cefr` + API.

### 3.11 Notyfikacje (`NotificationHelper`)

`notif_channel_study`, `notif_channel_cards`, `notif_study_title/body`, `notif_cards_ready_title/body` — są we wszystkich 371+ locale (nie w zestawie 66).

### 3.12 Martwe trasy (NavHost jest, UI nie nawiguje)

- **Profile:** `profile_*`, hardcoded `"${appLang} -> ${learning_lang}"`, `"CEFR ${cefr_level}"`
- **Learning:** `learning_title`, `learning_empty`, `learning_empty_hint`, `learning_back_list`
- **Packs:** `packs_title`, `packs_subtitle`, `packs_body`

Klucze żyją w XML; hardcoded w Profile jest bug na martwej trasie.

### 3.13 Inne klucze w XML

`add_word_*` — stary flow dodawania (ekran usunięty?). Sprawdzić grepem czy `R.string.add_word_` jest jeszcze wołany.

`msg_*` — notice po akcjach (`HomeViewModel` / settings).

`action_retry`, `action_close`, `action_import`, `status_awaiting_network`, `status_error`, `status_new`, `status_learning`, `status_mastered`, `card_badge_import`, `import_cards_count`, `import_flashcards_count`, `import_done_count`.

---

## 4. Hardcoded / poza `strings.xml`

To miejsca, które **łamią** placeholder → słownik.

### 4.1 Literały w Compose / Kotlinie (user-visible)

| Plik | Literał | Problem |
|---|---|---|
| `HomeScreen.kt` | `Text("—")` | pusty forecast; powinien być `R.string` albo zostawiony jako znak |
| `ImportUi.kt`, `ImportDisplayBlocks.kt` | `"• $w"` | bullet OK |
| `CardSelfEditWarningDialog.kt` | `"• ${issue.label}: ${issue.message}"` | **EN z API** |
| `CardCorrectionFlow.kt` | `item.reason` | **EN/dowolny z API** |
| `CardHistoryFormatting.kt` | `"—"` w diff lemma/pos/gloss | znak |
| `ProfileScreen.kt` | `"$appLang -> $learning_lang"`, `"CEFR $cefr"` | hardcoded, martwa trasa |
| `SettingsScreen.kt` | `"L1"`, `"L2"` | fallback gdy brak nazw języków |
| `Constants.kt` | `NEW_CARDS_OPTIONS` `"∞"` | znak |
| `HomeScreen.kt` | `onImportError(it.message ?: …)` | wyjątek systemowy EN |
| `ApiErrors.kt` | `parsed.message` z JSON `detail.message` | **backend EN** zawsze wygrywa z `err_*` |
| `LearningRepository.kt` | `error("empty_list_name")`, `"list_name_exists"`, `"Brak karty offline"`, `"No active language profile"`, `"Card not in cache"`, `"offline"` | jeśli wyciekną przez `userMessage` → surowy angielski/polski mix |
| `CardHistorySheet.kt` | `DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.getDefault())` | format OK (locale), nie copy |

`TestTags` — nie user-visible.

### 4.2 Słowniki poza XML

**POS** — `Constants.kt` `POS_LABELS` dla: pl, en, es, de, fr, pt, ru, zh, hi, ar, it, ja, ko, tr, vi, pt-br, pt-pt.

`localizedPosLabel` używa `LocalConfiguration.locales[0].language` → dla pt-BR dostaje `"pt"`, nie `"pt-br"`. Trafia w mapę `"pt"` (jest) — **nie** spada na EN. OK.

Gdy `appLang` ustawiony, Configuration powinna być spójna. Jeśli POS nieznany: pokazuje surowy kod z API (`noun`) albo pusty.

**Rekomendacja:** przenieść POS do `strings.xml` (`pos_noun`, …) × 17 locale, albo mapować `pt-BR` → `pt-br` przez `toLanguageTag()`.

**Czasy** — `LanguagePacks.kt`: Presente, Present simple, Czas teraźniejszy… To etykiety **języka nauki / metajęzyka gramatyki**, nie UI. Fallback `tenseKey` z podkreśleniami. Brak kluczy XML — świadome, ale przy `tense_label_lang = app_lang` pack UI może nie mieć kluczy L2 i dopina L2 (`TenseLabels.kt`). User zobaczy hiszpańskie „Presente” w polskim UI jeśli brak `tense_labels_app` na karcie.

**Endonimy języków** — zostawić hardcoded.

**`SYSTEM_LIST_NAME = "Uczę się"`** — tożsamość w DB, UI używa `list_learning`. Nie pokazywać raw (komentarz w kodzie). Ryzyko: nazwa listy z API jeśli ktoś zapisze kanoniczną i `listDisplayName` nie złapie `is_system`.

### 4.3 Backend → UI bez mapy kodów

`userMessage()`:

1. Jeśli HTTP i `detail.message` jest → **pokaż message z serwera** (prawie zawsze EN).
2. Inaczej `default` z `R.string.err_*`.
3. Non-HTTP: `Throwable.message` (często EN).

Skutek: przy wybranym JP/PL user i tak dostanie *„List name already exists”* gdy API tak odpowie.

**Rekomendacja:** mapować `detail.code` → `R.string.err_*`; message z API tylko w logach / debug. Kody do zmapowania (przykłady z repo): `empty_list_name`, `list_name_exists`, `correction_daily_limit`, `pending_inbox_not_deletable`, walidacja FastAPI `msg` array.

Self-edit `SelfEditValidateIssue.label/message` — albo kody z backendu + XML, albo tłumaczyć na serwerze wg `Accept-Language` / `app_lang`.

---

## 5. Pokrycie tłumaczeń — werdykt

| Warstwa | PL | EN (`values`) | Pozostałe 15 |
|---|---|---|---|
| 367 „starych” kluczy (auth, listy, settings, practice, import bazowy…) | tak | tak | tak (jakość: część korekty nadal EN w ar/de/es/…) |
| 66 nowych (historia, self-edit, review, voice, …) | tak | tak | **BRAK → fallback EN** |
| POS | mapa Kotlin | mapa | mapa (pt przez `"pt"`) |
| Błędy API | fallback `err_*` **nadpisywany** EN z body | j.w. | j.w. |
| Lemma/gloss/nazwy list usera | n/d (treść) | | |
| Issue self-edit / reason korekty | EN API | EN API | EN API |

**Wybór dowolnego języka ≠ brak fallbacków.** Dziś tylko **PL** (i EN) pokrywa 100% kluczy XML. Reszta spada na angielski w całym flow korekty/historii/głosu/review.

Dodatkowo nawet tam, gdzie klucz jest, copy bywa nieprzetłumaczone (`correction_fix_card` = „Fix card” w es/fr/de/…).

Brak `plurals.xml` — ilości przez `%1$d` w zwykłym stringu (OK dla większości locale; AR/RU mogłyby chcieć plural rules).

---

## 6. Lista wszystkich kluczy w `values/strings.xml` (433)

Pogrupowane prefiksem. Pełna treść EN jest w pliku; tu inwentarz do checklisty tłumaczeń.

### action (28)

`action_sort`, `action_filter`, `action_filter_active`, `action_clear_filters`, `action_clear_all`, `action_apply`, `action_undo`, `action_cancel`, `action_ok`, `action_back`, `action_delete`, `action_move`, `action_learn`, `action_confirm`, `action_create`, `action_import`, `action_close`, `action_save`, `action_reveal`, `action_add`, `action_search`, `action_logout`, `action_retry`, `action_check`, `action_return`, `action_abort`, `action_show_list`, `action_edit`

### auth (10)

`auth_login_title`, `auth_register_title`, `auth_login`, `auth_register`, `auth_google`, `auth_email`, `auth_password`, `auth_tagline`, `auth_password_hint`, `auth_have_account`

### onboarding (7)

`onboarding_title`, `onboarding_subtitle`, `onboarding_native`, `onboarding_learning`, `onboarding_start`, `onboarding_cefr`, `onboarding_tenses`

### settings (46)

`settings_title`, `settings_native_lang`, `settings_tense_labels`, `settings_tense_labels_app`, `settings_tense_labels_learning`, `settings_learning_lang`, `settings_langs_hint`, `settings_theme`, `settings_mode`, `settings_group_study`, `settings_group_general`, `settings_mode_choice`, `settings_mode_type`, `settings_mode_flash`, `settings_mode_vocabulario_only`, `settings_tolerate_typos`, `settings_tolerate_typos_sub`, `settings_direction`, `settings_direction_first`, `settings_direction_random`, `settings_card_layout`, `settings_card_layout_sub`, `settings_examples`, `settings_usages`, `settings_periphrases`, `settings_syn_ant`, `settings_word_family`, `settings_conjugation`, `settings_all_tenses`, `settings_limits`, `settings_new_limit`, `settings_new_per_day`, `settings_theme_system`, `settings_languages`, `settings_cefr_known`, `settings_label`, `settings_theme_light`, `settings_theme_dark`, `settings_languages_summary`, `settings_level`, `settings_selected_tenses`, `settings_notifications`, `settings_notifications_summary`, `settings_notif_study`, `settings_notif_cards`, `settings_reminder_hour`

### home / tab / weekday

`tab_dashboard`, `tab_add`, `tab_lists`  
`home_search_hint`, `home_due_now`, `home_new_today`, `home_reviewed_today`, `home_learning_now`, `home_new_left`, `home_mastered`, `home_forecast_title`, `home_words_count`, `home_new_words_count`  
`weekday_mon` … `weekday_sun`

### list (33)

`list_words_meta`, `list_filter_empty`, `list_learning`, `list_pending`, `list_other`, `list_new`, `list_rename`, `list_move_all`, `list_empty`, `list_delete_selected`, `list_move_to`, `list_name_hint`, `list_name_full_hint`, `list_pick`, `list_pick_target`, `list_create_and_add`, `list_delete_confirm_title`, `list_delete`, `list_delete_confirm_body`, `list_move_word`, `list_delete_word_confirm`, `list_delete_selected_title`, `list_delete_selected_body`, `list_create_move_all`, `list_create_move_sel`, `list_create_move_one`, `list_name_reserved`, `list_name_taken`, `list_fallback`, `list_clear_all`, `list_clear_all_title`, `list_clear_all_body`, `list_unnamed`

### import (37)

`import_online_only`, `import_from_file`, `import_paste`, `import_paste_hint`, `import_progress`, `import_add_file`, `import_other_file`, `import_how`, `import_vocab_mode`, `import_preserve_mode`, `import_vocab_hint`, `import_invalid_title`, `import_file_errors`, `import_no_cards`, `import_no_valid`, `import_empty_hint`, `import_file_label`, `import_start_title`, `import_pick_list`, `import_action_start`, `import_limit_exceeded`, `import_status_analyzing`, `import_status_importing`, `import_progress_count`, `import_abort_title`, `import_abort_body`, `import_result_title`, `import_result_body`, `import_result_body_failed`, `import_review_flagged`, `import_paste_source`, `import_interrupted`, `import_review_ready`, `import_new_list_option`, `import_cards_count`, `import_flashcards_count`, `import_done_count`

### practice / grade

`practice_title`, `practice_show_answer`, `practice_error_title`, `practice_bridge_l2`, `practice_bridge_means`, `practice_empty`, `practice_empty_hint`, `practice_your_answer`, `practice_spelling_warn`, `practice_spelling_detail`, `practice_correct_answer`, `practice_well_done`  
`grade_again`, `grade_hard`, `grade_good`, `grade_easy`

### correction (48) + self (6) + card history (23) + review (7)

patrz `values/strings.xml` od `correction_fix_card` oraz lista 66 w §1.1 — to najsłabsze pokrycie locale.

### voice (11)

`voice_listening`, `voice_listening_hint`, `voice_tap_to_start`, `voice_start`, `voice_stop`, `voice_permission_denied`, `voice_unavailable`, `voice_searching`, `voice_either_lang_hint`, `voice_no_match`, `voice_network_required`

### err (45) + msg (5)

wszystkie `err_*` z §6 dump + `msg_import_result`, `msg_added_learning`, `msg_added`, `msg_saved_cefr`, `msg_saved_tenses`

### cd (15)

`cd_undo`, `cd_settings`, `cd_play`, `cd_on_list`, `cd_delete`, `cd_move`, `cd_selected`, `cd_list_options`, `cd_back`, `cd_add_to_list`, `cd_search`, `cd_card_history`, `cd_view_card`, `cd_list_word_actions`, `cd_voice_search`

### section / kind / status / filter / sort / offline / notif / profile / learning / packs / add_word / creating / new / no_meanings / periphrase / app_name

jak w `docs` dump prefiksów: `section_*` (14), `kind_*` (5), `status_*` (7), `filter_*` (4), `sort_*` (7), `offline_*` (5), `notif_*` (6), `profile_*` (9), `learning_*` (4), `packs_*` (3), `add_word_*` (4), `creating_*` (2), `new_list_cd`, `new_cards_per_day`, `new_cards_unlimited`, `no_meanings`, `periphrase_n`, `app_name`.

---

## 7. Scenariusze end-to-end vs luki

| Scenariusz | Czy UI lang pokryty? |
|---|---|
| Auth → onboarding → home | tak (stare klucze) we wszystkich locale |
| Dashboard + listy CRUD + import bazowy | tak, poza `list_delete` (w 66) |
| Szukaj + dodaj na listę | tak; POS z mapy Kotlin |
| Głos | **nie** — 4 klucze voice w 66 |
| Import abort / result | tak |
| Practice + oceny | tak; empty hint do wycięcia |
| Zgłoś poprawkę (sheet) | częściowo: tytuły stare; subtitle/fields/kody w 66 |
| Self-edit + warning | **nie** (66) |
| Historia karty | **nie** (66) |
| Pending review | **nie** (66) |
| Settings języki/CEFR/czasy/theme | tak; CEFR kody A1–C2; czasy z packa |
| Błąd sieci / 400 z API | **nie** — `detail.message` EN |
| Notyfikacje | tak |
| Profile/Learning/Packs | klucze są; Profile ma hardcoded |

---

## 8. Plan naprawy i18n (osobny PR od UI, albo tuż przed)

1. **Zsynchronizować 66 kluczy** do wszystkich `values-*`. Źródło: `values/strings.xml` (EN) + `values-pl`. Nie kopiować EN 1:1 do es/de/… — to ten sam bug co „Fix card”.
2. **Zsynchronizować `values-en` z `values/`** albo usunąć `values-en` i zostawić default.
3. Usunąć extra `review_status_*`.
4. Przeskanować locale pod **identyczny tekst EN** co `values/` (skrypt diff wartości) — wyłapie nietłumaczone `correction_fix_card` itd.
5. `userMessage`: najpierw `code` → `R.string`, nigdy raw `message` na UI.
6. Self-edit issues: kody zamiast `label` z LLM/API.
7. POS → `strings.xml` albo poprawić tag locale (`pt-BR`).
8. Test CI: skrypt jak `docs/_tmp_compare_strings.py` — fail jeśli jakikolwiek `values-*` ma inny zestaw kluczy niż `values/`.
9. Nowe klucze z planu UI (`correction_history_button`, zmiana title warning) dodać **od razu we wszystkich 17 plikach**.

Hardcoded `"—"`, `"•"`, `"∞"`, endonimy, tense L2 — zostawić, ewentualnie udokumentować jako wyjątki.

---

## 9. Powiązanie z planem UI

Plan: [plan-standaryzacja-ui.md](plan-standaryzacja-ui.md).

Zmiany copy (OK / Anuluj / Zgłoś poprawkę / Historia zmian / Potwierdzasz zmiany? / Edytuj) **powiększą** dług tłumaczeń. Nie wdrażać UI-copy tylko w PL/`values` — wrócimy do fallbacków EN w 15 językach.
