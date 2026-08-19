# Audyt struktur kart i słowników L2

Data: 2026-08-18  
Pytanie: czy każdy język nauki ma własny katalog form, nazwy oryginalne (L2) i tłumaczenia na języki UI; jak działają peryfrazy, synonimy i przeciwieństwa.

## Werdykt

**Tak — 16 języków nauki ma własne LSP** (`backend/app/lsp/{code}/manifest.yaml`). Katalog czasów, siatki osób, rzeczowniki/przymiotniki i reguły odmiany są dopasowane do języka.

**Nazwy czasów:** oryginał zawsze w L2 (`label_l2`); tłumaczenie na język UI idzie z `ui_labels`. Przed audytem pełne 16 języków UI miało tylko nauka angielskiego. **Uzupełniono:** każdy L2 × 16 UI × wszystkie klucze czasów i form nieosobowych. To samo wpadło do fallbacku Androida `TenseUiLabels.kt`.

**Synonimy / przeciwieństwa / peryfrazy / rodzina wyrazów** nie są osobnymi słownikami per L2 — to **ta sama sekcja karty** dla wszystkich języków, treść generuje LLM w L2 + glosa L1. Nagłówki UI biorą się z `strings.xml`.

## Co jest wspólne, a co per język

| Element karty | Źródło | Per L2? |
|---|---|---|
| Znaczenia, przykłady, zwroty | LLM (`prompts/v1.py`) | Treść tak, schemat ten sam |
| Synonimy L2, przeciwieństwa L2, wyrazy pokrewne | LLM, pola `synonyms_l2` / `antonyms_l2` / `word_family_l2` | Treść tak, schemat ten sam |
| Peryfrazy (wzorce, *ir a + inf.*) | LLM, `conjugation.periphrases[]` | Tylko gdy idiom należy do **tego** lematu; inaczej `[]` |
| Czasy / formy | LSP `verbs.tenses` + `non_finite` | **Tak — własny katalog** |
| Osoby w tabeli | LSP `person_grids` | **Tak** (yo/tú vs ich/du vs أنا…) |
| Nagłówek czasu | L2 + tłumaczenie UI | **Tak** (`ui_labels`) |
| Rzeczownik (przypadki, liczba, rodzaj) | LSP `nouns` | **Tak** (PL 7 przypadków, DE 4, ZH bez rodzaju…) |
| Przymiotnik | LSP `adjectives.full_declension` | **Tak** |

Android `LanguagePacks.kt` ma te same klucze czasów co LSP (`scripts/lsp_sync.py`: OK).

## Katalogi czasów (oryginał L2)

| L2 | Rodzaj odmiany | Czasy (klucze) | Formy nieosobowe |
|---|---|---|---|
| es | person_tense | 14 (Presente … Imperativo −/+) | Gerundio, Participio |
| en | minimal | 9 (Present simple … Conditionals) | -ing, Past participle |
| fr | person_tense | 8 | Infinitif, Participe passé, Gérondif |
| de | person_tense | 7 (Präsens … Imperativ) | Infinitiv, Partizip II |
| it | person_tense | 7 | Gerundio, Participio |
| pt-br | person_tense | 7 | Gerúndio, Particípio |
| pt-pt | jak BR + **Infinitivo pessoal** | 8 | jak BR |
| pl | person_tense | 5 (aspekt w `paradigm_rules`) | Bezokolicznik, 2 imiesłowy |
| ru | person_tense | 4 (aspekt: perfective bez teraźniejszego) | Инфинитив, Деепричастие |
| ja | conjugation_class | 辞書形, ます, て, た, ない, 可能, 命令 | て/た |
| ko | agglutinative | 현재/과거/미래/명령 | 어간 |
| zh | aspect_particle | 现在/过去/将来/进行/完成 | 原形 |
| vi | analytic | Hiện tại / Quá khứ / Tương lai / Mệnh lệnh | Nguyên mẫu |
| tr | agglutinative | Şimdiki, Geniş, Geçmiş, Gelecek | Mastar |
| ar | root_pattern | الماضي, المضارع, الأمر | المصدر |
| hi | person_tense | वर्तमान / भूत / भविष्य / आज्ञार्थ | मूलधातु |

Na karcie nagłówek to **nazwa L2**, a pod spodem tłumaczenie w języku aplikacji, np. *Pretérito indefinido* / *Czas przeszły prosty*.

## Tłumaczenia nazw czasów → UI

`ui_labels` w manifeście + `apply_manifest_ui_labels()` zapisuje na karcie `tense_labels_l2` i `tense_labels_app`.

| Stan | L2 z pełnym UI (16) | L2 tylko EN+natywny+PL |
|---|---|---|
| Przed | tylko **en** | pozostałe 15 |
| Po | **wszystkie 16** | — |

Test: `test_ui_labels_cover_all_ui_langs` w `backend/tests/test_lsp_all_manifests.py`.

Uzupełniono też puste etykiety osób (siatki były `labels: {}`): **ar, ja, ko, hi, vi** (np. أنا / 私 / 저 / मैं / tôi).

## Peryfrazy

Nie ma osobnego słownika peryfraz per język. Prompt każe LLM dodać **tylko idiomy tego lematu** (`ir a inf.`, *have to*, *être en train de*…). Jeśli język/lemat nie ma takich wzorców → pusta lista, sekcja się nie pokazuje.

Nagłówek UI jest wspólny (`settings_periphrases` / `section_periphrases`):

- EN: Patterns  
- PL: **Peryfrazy** (termin specjalistyczny — analogiczny problem jak „antonimy”)  
- ES: Patrones · FR: Tournures · DE: Muster · ZH: 句式 · VI: Cách diễn đạt  

Czyli mechanizm jest we wszystkich L2; treść pojawia się tam, gdzie LLM uzna idiom.

## Synonimy i przeciwieństwa

Schemat karty jest jeden. LLM dostaje definicję: ta sama część mowy, nie derywaty (te idą do *wyrazów pokrewnych*).

W polskim UI było niespójnie: ustawienia i tytuł już mówiły „przeciwieństwa”, a sekcja na karcie **Antonimy**.

Zmiana PL:

- `section_antonyms`: ANTONIMY → **PRZECIWIEŃSTWA**
- `section_antonyms_short`: Antonimy → **Przeciwieństwa**
- `settings_syn_ant` / `section_syn_ant` / `section_antonyms_title` / hint importu — już były „przeciwieństwa”

Przy okazji naprawiono zepsute `&amp;amp;` w IT/JA/TR/VI (`section_syn_ant`).

## Luki, których nie ruszano (nie słowniki UI)

1. **`card_sections` w YAML** — szablon przewiduje np. pinyin; żaden manifest tego nie wypełnia. Pinyin/romaji idą w `language_specific` z promptu, nie jako osobna sekcja UI.
2. **Odmiana rzeczownika/przymiotnika** — `validate.py` ma TODO; katalog przypadków jest w manifeście, walidator jeszcze nie tnie form.
3. **PL `preterito_perfecto`** w `ui_labels.pl` zostawione jako „Pretérito perfecto” (nazwa hiszpańska, nie spolszczenie) — tak było wcześniej; reszta czasów ES ma polskie opisy.

## Testy

```text
python scripts/lsp_sync.py          # OK — 16 L2, klucze = Android
python scripts/check_ui_strings.py  # OK — 511 kluczy
pytest backend/tests/test_lsp_all_manifests.py backend/tests/test_lsp_pl.py
# 72 passed
```

Narzędzie do ponownego zrzutu etykiet: `scripts/lsp_fill_ui_labels.py` (nie nadpisuje już istniejących `ui_labels`).
