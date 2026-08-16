# Audyt etykiet czasów i form nieosobowych

Nagłówek odmiany: **nazwa w języku uczonym** (środek, pogrubiona).
Pod spodem: tłumaczenie w **języku aplikacji**, jeśli istnieje i różni się od oryginału.
Ustawienie „etykiety czasów” zostało usunięte — zawsze ten sam układ.

Języki UI / nauki (16 LSP): `en`, `es`, `fr`, `de`, `it`, `pt-br`, `pt-pt`, `zh`, `ja`, `ko`, `ar`, `ru`, `hi`, `tr`, `vi`, `pl`.

## Co jest kompletne

- **Angielski jako język nauki** (`en`): wszystkie 11 form mają tłumaczenie na wszystkie 16 języków aplikacji. To przypadek z zrzutu (PL app + EN nauka).
- **Każdy język nauki** ma pełne nazwy L2 (nagłówek) oraz tłumaczenia na **polski** i **angielski**.
- Reszta par (np. niemiecki uczony + UI japoński) jest w tabelach poniżej jako braki — do uzupełnienia w `backend/app/lsp/*/manifest.yaml` i ponownego `python scripts/sync_tense_labels.py`.

Źródło prawdy: `ui_labels` w manifeście L2. Fallback w apce: `TenseUiLabels.kt`.

## ar

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `perfect` | الماضي | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ru, hi, tr, vi |
| `imperfect` | المضارع | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ru, hi, tr, vi |
| `imperative` | الأمر | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ru, hi, tr, vi |
| `masdar` | المصدر | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 4/4
- `es`: 0/4
- `fr`: 0/4
- `de`: 0/4
- `it`: 0/4
- `pt-br`: 0/4
- `pt-pt`: 0/4
- `zh`: 0/4
- `ja`: 0/4
- `ko`: 0/4
- `ar`: 4/4
- `ru`: 0/4
- `hi`: 0/4
- `tr`: 0/4
- `vi`: 0/4
- `pl`: 4/4

## de

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `prasens` | Präsens | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `perfekt` | Perfekt | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `prateritum` | Präteritum | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futur_i` | Futur I | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `plusquamperfekt` | Plusquamperfekt | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `konjunktiv_ii` | Konjunktiv II | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativ` | Imperativ | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `infinitiv` | Infinitiv | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `partizip_ii` | Partizip II | es, fr, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 9/9
- `es`: 0/9
- `fr`: 0/9
- `de`: 9/9
- `it`: 0/9
- `pt-br`: 0/9
- `pt-pt`: 0/9
- `zh`: 0/9
- `ja`: 0/9
- `ko`: 0/9
- `ar`: 0/9
- `ru`: 0/9
- `hi`: 0/9
- `tr`: 0/9
- `vi`: 0/9
- `pl`: 9/9

## en

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present_simple` | Present simple | — |
| `present_continuous` | Present continuous | — |
| `present_perfect` | Present perfect | — |
| `past_simple` | Past simple | — |
| `past_continuous` | Past continuous | — |
| `past_perfect` | Past perfect | — |
| `future_will` | Future (will) | — |
| `going_to` | Going to | — |
| `conditionals` | Conditionals | — |
| `ing_form` | -ing form | — |
| `past_participle` | Past participle | — |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 11/11
- `es`: 11/11
- `fr`: 11/11
- `de`: 11/11
- `it`: 11/11
- `pt-br`: 11/11
- `pt-pt`: 11/11
- `zh`: 11/11
- `ja`: 11/11
- `ko`: 11/11
- `ar`: 11/11
- `ru`: 11/11
- `hi`: 11/11
- `tr`: 11/11
- `vi`: 11/11
- `pl`: 11/11

## es

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `presente` | Presente | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_perfecto` | Pretérito perfecto | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_indefinido` | Pretérito indefinido | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_imperfecto` | Pretérito imperfecto | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro_simple` | Futuro simple | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `condicional_simple` | Condicional | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `presente_subjuntivo` | Presente de subjuntivo | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperfecto_subjuntivo` | Imperfecto de subjuntivo | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro_subjuntivo` | Futuro de subjuntivo | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_pluscuamperfecto` | Pretérito pluscuamperfecto | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `condicional_compuesto` | Condicional compuesto | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro_perfecto` | Futuro perfecto | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativo_afirmativo` | Imperativo afirmativo | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativo_negativo` | Imperativo negativo | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `gerundio` | Gerundio | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `participio` | Participio | fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 16/16
- `es`: 16/16
- `fr`: 0/16
- `de`: 0/16
- `it`: 0/16
- `pt-br`: 0/16
- `pt-pt`: 0/16
- `zh`: 0/16
- `ja`: 0/16
- `ko`: 0/16
- `ar`: 0/16
- `ru`: 0/16
- `hi`: 0/16
- `tr`: 0/16
- `vi`: 0/16
- `pl`: 16/16

## fr

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present` | Présent | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `passe_compose` | Passé composé | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imparfait` | Imparfait | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futur_simple` | Futur simple | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `conditionnel` | Conditionnel | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `subjonctif_present` | Subjonctif présent | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `plus_que_parfait` | Plus-que-parfait | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperatif` | Impératif | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `infinitif` | Infinitif | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `participe_passe` | Participe passé | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `gerondif` | Gérondif | es, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 11/11
- `es`: 0/11
- `fr`: 11/11
- `de`: 0/11
- `it`: 0/11
- `pt-br`: 0/11
- `pt-pt`: 0/11
- `zh`: 0/11
- `ja`: 0/11
- `ko`: 0/11
- `ar`: 0/11
- `ru`: 0/11
- `hi`: 0/11
- `tr`: 0/11
- `vi`: 0/11
- `pl`: 11/11

## hi

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present` | वर्तमान | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, tr, vi |
| `past` | भूत | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, tr, vi |
| `future` | भविष्य | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, tr, vi |
| `imperative` | आज्ञार्थ | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, tr, vi |
| `infinitive` | मूलधातु | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 5/5
- `es`: 0/5
- `fr`: 0/5
- `de`: 0/5
- `it`: 0/5
- `pt-br`: 0/5
- `pt-pt`: 0/5
- `zh`: 0/5
- `ja`: 0/5
- `ko`: 0/5
- `ar`: 0/5
- `ru`: 0/5
- `hi`: 5/5
- `tr`: 0/5
- `vi`: 0/5
- `pl`: 5/5

## it

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `presente` | Presente | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `passato_prossimo` | Passato prossimo | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperfetto` | Imperfetto | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro_semplice` | Futuro semplice | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `condizionale` | Condizionale | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `congiuntivo_presente` | Congiuntivo presente | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativo` | Imperativo | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `gerundio` | Gerundio | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `participio` | Participio | es, fr, de, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 9/9
- `es`: 0/9
- `fr`: 0/9
- `de`: 0/9
- `it`: 9/9
- `pt-br`: 0/9
- `pt-pt`: 0/9
- `zh`: 0/9
- `ja`: 0/9
- `ko`: 0/9
- `ar`: 0/9
- `ru`: 0/9
- `hi`: 0/9
- `tr`: 0/9
- `vi`: 0/9
- `pl`: 9/9

## ja

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `jisho` | 辞書形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `masu` | ます形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `te` | て形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `ta` | た形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `nai` | ない形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `potential` | 可能形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |
| `imperative` | 命令形 | es, fr, de, it, pt-br, pt-pt, zh, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 7/7
- `es`: 0/7
- `fr`: 0/7
- `de`: 0/7
- `it`: 0/7
- `pt-br`: 0/7
- `pt-pt`: 0/7
- `zh`: 0/7
- `ja`: 7/7
- `ko`: 0/7
- `ar`: 0/7
- `ru`: 0/7
- `hi`: 0/7
- `tr`: 0/7
- `vi`: 0/7
- `pl`: 7/7

## ko

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present` | 현재 | es, fr, de, it, pt-br, pt-pt, zh, ja, ar, ru, hi, tr, vi |
| `past` | 과거 | es, fr, de, it, pt-br, pt-pt, zh, ja, ar, ru, hi, tr, vi |
| `future` | 미래 | es, fr, de, it, pt-br, pt-pt, zh, ja, ar, ru, hi, tr, vi |
| `imperative` | 명령 | es, fr, de, it, pt-br, pt-pt, zh, ja, ar, ru, hi, tr, vi |
| `base` | 어간 | es, fr, de, it, pt-br, pt-pt, zh, ja, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 5/5
- `es`: 0/5
- `fr`: 0/5
- `de`: 0/5
- `it`: 0/5
- `pt-br`: 0/5
- `pt-pt`: 0/5
- `zh`: 0/5
- `ja`: 0/5
- `ko`: 5/5
- `ar`: 0/5
- `ru`: 0/5
- `hi`: 0/5
- `tr`: 0/5
- `vi`: 0/5
- `pl`: 5/5

## pl

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `czas_terazniejszy` | Czas teraźniejszy | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `czas_przeszly` | Czas przeszły | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `czas_przyszly` | Czas przyszły | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `tryb_rozkazujacy` | Tryb rozkazujący | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `tryb_przypuszczajacy` | Tryb przypuszczający | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `bezokolicznik` | Bezokolicznik | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imieslow_przeszly` | Imiesłów przeszły | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imieslow_przyszly` | Imiesłów przyszły | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 8/8
- `es`: 0/8
- `fr`: 0/8
- `de`: 0/8
- `it`: 0/8
- `pt-br`: 0/8
- `pt-pt`: 0/8
- `zh`: 0/8
- `ja`: 0/8
- `ko`: 0/8
- `ar`: 0/8
- `ru`: 0/8
- `hi`: 0/8
- `tr`: 0/8
- `vi`: 0/8
- `pl`: 8/8

## pt-br

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `presente` | Presente | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_perfeito` | Pretérito perfeito | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_imperfeito` | Pretérito imperfeito | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro` | Futuro | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `condicional` | Condicional | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `subjuntivo_presente` | Subjuntivo presente | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativo` | Imperativo | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `gerundio` | Gerúndio | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |
| `participio` | Particípio | es, fr, de, it, pt-pt, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 9/9
- `es`: 0/9
- `fr`: 0/9
- `de`: 0/9
- `it`: 0/9
- `pt-br`: 9/9
- `pt-pt`: 0/9
- `zh`: 0/9
- `ja`: 0/9
- `ko`: 0/9
- `ar`: 0/9
- `ru`: 0/9
- `hi`: 0/9
- `tr`: 0/9
- `vi`: 0/9
- `pl`: 9/9

## pt-pt

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `presente` | Presente | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_perfeito` | Pretérito perfeito | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `preterito_imperfeito` | Pretérito imperfeito | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `futuro` | Futuro | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `condicional` | Condicional | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `subjuntivo_presente` | Subjuntivo presente | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `imperativo` | Imperativo | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `infinitivo_pessoal` | Infinitivo pessoal | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `gerundio` | Gerúndio | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |
| `participio` | Particípio | es, fr, de, it, pt-br, zh, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 10/10
- `es`: 0/10
- `fr`: 0/10
- `de`: 0/10
- `it`: 0/10
- `pt-br`: 0/10
- `pt-pt`: 10/10
- `zh`: 0/10
- `ja`: 0/10
- `ko`: 0/10
- `ar`: 0/10
- `ru`: 0/10
- `hi`: 0/10
- `tr`: 0/10
- `vi`: 0/10
- `pl`: 10/10

## ru

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `nastoyashchee` | Настоящее | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |
| `proshedshee` | Прошедшее | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |
| `budushchee` | Будущее | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |
| `povelitelnoe` | Повелительное | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |
| `infinitiv` | Инфинитив | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |
| `deeprichastie` | Деепричастие | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 6/6
- `es`: 0/6
- `fr`: 0/6
- `de`: 0/6
- `it`: 0/6
- `pt-br`: 0/6
- `pt-pt`: 0/6
- `zh`: 0/6
- `ja`: 0/6
- `ko`: 0/6
- `ar`: 0/6
- `ru`: 6/6
- `hi`: 0/6
- `tr`: 0/6
- `vi`: 0/6
- `pl`: 6/6

## tr

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `simdi_zaman` | Şimdiki zaman | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, vi |
| `genis_zaman` | Geniş zaman | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, vi |
| `gecmis_zaman` | Geçmiş zaman | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, vi |
| `gelecek_zaman` | Gelecek zaman | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, vi |
| `mastar` | Mastar | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 5/5
- `es`: 0/5
- `fr`: 0/5
- `de`: 0/5
- `it`: 0/5
- `pt-br`: 0/5
- `pt-pt`: 0/5
- `zh`: 0/5
- `ja`: 0/5
- `ko`: 0/5
- `ar`: 0/5
- `ru`: 0/5
- `hi`: 0/5
- `tr`: 5/5
- `vi`: 0/5
- `pl`: 5/5

## vi

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present` | Hiện tại | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr |
| `past` | Quá khứ | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr |
| `future` | Tương lai | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr |
| `imperative` | Mệnh lệnh | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr |
| `infinitive` | Nguyên mẫu | es, fr, de, it, pt-br, pt-pt, zh, ja, ko, ar, ru, hi, tr |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 5/5
- `es`: 0/5
- `fr`: 0/5
- `de`: 0/5
- `it`: 0/5
- `pt-br`: 0/5
- `pt-pt`: 0/5
- `zh`: 0/5
- `ja`: 0/5
- `ko`: 0/5
- `ar`: 0/5
- `ru`: 0/5
- `hi`: 0/5
- `tr`: 0/5
- `vi`: 5/5
- `pl`: 5/5

## zh

| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |
| --- | --- | --- |
| `present` | 现在 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |
| `past` | 过去 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |
| `future` | 将来 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |
| `progressive` | 进行 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |
| `perfect` | 完成 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |
| `base` | 原形 | es, fr, de, it, pt-br, pt-pt, ja, ko, ar, ru, hi, tr, vi |

Pokrycie `ui_labels` per język aplikacji:

- `en`: 6/6
- `es`: 0/6
- `fr`: 0/6
- `de`: 0/6
- `it`: 0/6
- `pt-br`: 0/6
- `pt-pt`: 0/6
- `zh`: 6/6
- `ja`: 0/6
- `ko`: 0/6
- `ar`: 0/6
- `ru`: 0/6
- `hi`: 0/6
- `tr`: 0/6
- `vi`: 0/6
- `pl`: 6/6

## Podsumowanie braków

Komórek bez tłumaczenia (poza parą język uczony = język aplikacji): **1503**.

Źródło prawdy: `backend/app/lsp/*/manifest.yaml` → `ui_labels`.
Fallback w aplikacji: `TenseUiLabels.kt` (generowane tym skryptem).
