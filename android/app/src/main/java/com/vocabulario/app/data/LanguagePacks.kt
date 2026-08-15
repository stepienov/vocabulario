package com.vocabulario.app.data

data class TenseItem(val key: String, val label: String)

data class LanguagePack(
    val code: String,
    val showConjugationDefault: Boolean = true,
    val conjugationKind: String = "person_tense",
    val tenses: List<TenseItem> = emptyList(),
    val nonFinite: List<TenseItem> = emptyList(),
    val defaultSelectedTenses: List<String> = emptyList(),
)

/**
 * Per-L2 tense catalogs — 16 języków LSP (sync z backend/app/lsp manifestami).
 */
object LanguagePacks {
    private val es = LanguagePack(
        code = "es",
        tenses = listOf(
            TenseItem("presente", "Presente"),
            TenseItem("preterito_perfecto", "Pretérito perfecto"),
            TenseItem("preterito_indefinido", "Pretérito indefinido"),
            TenseItem("preterito_imperfecto", "Imperfecto"),
            TenseItem("futuro_simple", "Futuro simple"),
            TenseItem("condicional_simple", "Condicional"),
            TenseItem("presente_subjuntivo", "Presente de subjuntivo"),
            TenseItem("imperfecto_subjuntivo", "Imperfecto de subjuntivo"),
            TenseItem("futuro_subjuntivo", "Futuro de subjuntivo"),
            TenseItem("preterito_pluscuamperfecto", "Pretérito pluscuamperfecto"),
            TenseItem("condicional_compuesto", "Condicional compuesto"),
            TenseItem("futuro_perfecto", "Futuro perfecto"),
            TenseItem("imperativo_afirmativo", "Imperativo afirmativo"),
            TenseItem("imperativo_negativo", "Imperativo negativo"),
        ),
        nonFinite = listOf(
            TenseItem("gerundio", "Gerundio"),
            TenseItem("participio", "Participio"),
        ),
        defaultSelectedTenses = listOf("presente"),
    )

    private val en = LanguagePack(
        code = "en",
        conjugationKind = "minimal",
        tenses = listOf(
            TenseItem("present_simple", "Present simple"),
            TenseItem("present_continuous", "Present continuous"),
            TenseItem("present_perfect", "Present perfect"),
            TenseItem("past_simple", "Past simple"),
            TenseItem("past_continuous", "Past continuous"),
            TenseItem("past_perfect", "Past perfect"),
            TenseItem("future_will", "Future (will)"),
            TenseItem("going_to", "Going to"),
            TenseItem("conditionals", "Conditionals"),
        ),
        nonFinite = listOf(
            TenseItem("ing_form", "-ing form"),
            TenseItem("past_participle", "Past participle"),
        ),
        defaultSelectedTenses = listOf("present_simple"),
    )

    private val fr = LanguagePack(
        code = "fr",
        tenses = listOf(
            TenseItem("present", "Présent"),
            TenseItem("passe_compose", "Passé composé"),
            TenseItem("imparfait", "Imparfait"),
            TenseItem("futur_simple", "Futur simple"),
            TenseItem("conditionnel", "Conditionnel"),
            TenseItem("subjonctif_present", "Subjonctif présent"),
            TenseItem("plus_que_parfait", "Plus-que-parfait"),
            TenseItem("imperatif", "Impératif"),
        ),
        nonFinite = listOf(
            TenseItem("infinitif", "Infinitif"),
            TenseItem("participe_passe", "Participe passé"),
            TenseItem("gerondif", "Gérondif"),
        ),
        defaultSelectedTenses = listOf("present"),
    )

    private val de = LanguagePack(
        code = "de",
        tenses = listOf(
            TenseItem("prasens", "Präsens"),
            TenseItem("perfekt", "Perfekt"),
            TenseItem("prateritum", "Präteritum"),
            TenseItem("futur_i", "Futur I"),
            TenseItem("plusquamperfekt", "Plusquamperfekt"),
            TenseItem("konjunktiv_ii", "Konjunktiv II"),
            TenseItem("imperativ", "Imperativ"),
        ),
        nonFinite = listOf(
            TenseItem("infinitiv", "Infinitiv"),
            TenseItem("partizip_ii", "Partizip II"),
        ),
        defaultSelectedTenses = listOf("prasens"),
    )

    private val it = LanguagePack(
        code = "it",
        tenses = listOf(
            TenseItem("presente", "Presente"),
            TenseItem("passato_prossimo", "Passato prossimo"),
            TenseItem("imperfetto", "Imperfetto"),
            TenseItem("futuro_semplice", "Futuro semplice"),
            TenseItem("condizionale", "Condizionale"),
            TenseItem("congiuntivo_presente", "Congiuntivo presente"),
            TenseItem("imperativo", "Imperativo"),
        ),
        nonFinite = listOf(
            TenseItem("gerundio", "Gerundio"),
            TenseItem("participio", "Participio"),
        ),
        defaultSelectedTenses = listOf("presente"),
    )

    private val ptBr = LanguagePack(
        code = "pt-br",
        tenses = listOf(
            TenseItem("presente", "Presente"),
            TenseItem("preterito_perfeito", "Pretérito perfeito"),
            TenseItem("preterito_imperfeito", "Pretérito imperfeito"),
            TenseItem("futuro", "Futuro"),
            TenseItem("condicional", "Condicional"),
            TenseItem("subjuntivo_presente", "Subjuntivo presente"),
            TenseItem("imperativo", "Imperativo"),
        ),
        nonFinite = listOf(
            TenseItem("gerundio", "Gerúndio"),
            TenseItem("participio", "Particípio"),
        ),
        defaultSelectedTenses = listOf("presente"),
    )

    private val ptPt = LanguagePack(
        code = "pt-pt",
        tenses = ptBr.tenses + TenseItem("infinitivo_pessoal", "Infinitivo pessoal"),
        nonFinite = ptBr.nonFinite,
        defaultSelectedTenses = ptBr.defaultSelectedTenses,
    )

    private val pl = LanguagePack(
        code = "pl",
        tenses = listOf(
            TenseItem("czas_terazniejszy", "Czas teraźniejszy"),
            TenseItem("czas_przeszly", "Czas przeszły"),
            TenseItem("czas_przyszly", "Czas przyszły"),
            TenseItem("tryb_rozkazujacy", "Tryb rozkazujący"),
            TenseItem("tryb_przypuszczajacy", "Tryb przypuszczający"),
        ),
        nonFinite = listOf(
            TenseItem("bezokolicznik", "Bezokolicznik"),
            TenseItem("imieslow_przeszly", "Imiesłów przeszły"),
            TenseItem("imieslow_przyszly", "Imiesłów przyszły"),
        ),
        defaultSelectedTenses = listOf("czas_terazniejszy"),
    )

    private val ru = LanguagePack(
        code = "ru",
        tenses = listOf(
            TenseItem("nastoyashchee", "Настоящее"),
            TenseItem("proshedshee", "Прошедшее"),
            TenseItem("budushchee", "Будущее"),
            TenseItem("povelitelnoe", "Повелительное"),
        ),
        nonFinite = listOf(
            TenseItem("infinitiv", "Инфинитив"),
            TenseItem("deeprichastie", "Деепричастие"),
        ),
        defaultSelectedTenses = listOf("nastoyashchee"),
    )

    private val ja = LanguagePack(
        code = "ja",
        conjugationKind = "conjugation_class",
        tenses = listOf(
            TenseItem("jisho", "辞書形"),
            TenseItem("masu", "ます形"),
            TenseItem("te", "て形"),
            TenseItem("ta", "た形"),
            TenseItem("nai", "ない形"),
            TenseItem("potential", "可能形"),
            TenseItem("imperative", "命令形"),
        ),
        nonFinite = listOf(
            TenseItem("te", "て形"),
            TenseItem("ta", "た形"),
        ),
        defaultSelectedTenses = listOf("jisho"),
    )

    private val ko = LanguagePack(
        code = "ko",
        conjugationKind = "agglutinative",
        tenses = listOf(
            TenseItem("present", "현재"),
            TenseItem("past", "과거"),
            TenseItem("future", "미래"),
            TenseItem("imperative", "명령"),
        ),
        nonFinite = listOf(TenseItem("base", "어간")),
        defaultSelectedTenses = listOf("present"),
    )

    private val zh = LanguagePack(
        code = "zh",
        conjugationKind = "aspect_particle",
        tenses = listOf(
            TenseItem("present", "现在"),
            TenseItem("past", "过去"),
            TenseItem("future", "将来"),
            TenseItem("progressive", "进行"),
            TenseItem("perfect", "完成"),
        ),
        nonFinite = listOf(TenseItem("base", "原形")),
        defaultSelectedTenses = listOf("present"),
    )

    private val vi = LanguagePack(
        code = "vi",
        conjugationKind = "analytic",
        tenses = listOf(
            TenseItem("present", "Hiện tại"),
            TenseItem("past", "Quá khứ"),
            TenseItem("future", "Tương lai"),
            TenseItem("imperative", "Mệnh lệnh"),
        ),
        nonFinite = listOf(TenseItem("infinitive", "Nguyên mẫu")),
        defaultSelectedTenses = listOf("present"),
    )

    private val packs: Map<String, LanguagePack> = mapOf(
        "en" to en,
        "es" to es,
        "fr" to fr,
        "de" to de,
        "it" to it,
        "pt-br" to ptBr,
        "pt-pt" to ptPt,
        "pt" to ptBr,
        "pl" to pl,
        "ru" to ru,
        "tr" to LanguagePack(
            code = "tr",
            conjugationKind = "agglutinative",
            tenses = listOf(
                TenseItem("simdi_zaman", "Şimdiki zaman"),
                TenseItem("genis_zaman", "Geniş zaman"),
                TenseItem("gecmis_zaman", "Geçmiş zaman"),
                TenseItem("gelecek_zaman", "Gelecek zaman"),
            ),
            nonFinite = listOf(TenseItem("mastar", "Mastar")),
            defaultSelectedTenses = listOf("simdi_zaman"),
        ),
        "ja" to ja,
        "ko" to ko,
        "zh" to zh,
        "vi" to vi,
        "ar" to LanguagePack(
            code = "ar",
            tenses = listOf(
                TenseItem("perfect", "الماضي"),
                TenseItem("imperfect", "المضارع"),
                TenseItem("imperative", "الأمر"),
            ),
            nonFinite = listOf(TenseItem("masdar", "المصدر")),
            defaultSelectedTenses = listOf("imperfect"),
        ),
        "hi" to LanguagePack(
            code = "hi",
            tenses = listOf(
                TenseItem("present", "वर्तमान"),
                TenseItem("past", "भूत"),
                TenseItem("future", "भविष्य"),
                TenseItem("imperative", "आज्ञार्थ"),
            ),
            nonFinite = listOf(TenseItem("infinitive", "मूलधातु")),
            defaultSelectedTenses = listOf("present"),
        ),
    )

    fun get(code: String?): LanguagePack =
        packs[code?.lowercase()?.trim()] ?: en

    fun tenseCatalog(code: String?): List<TenseItem> = get(code).tenses

    fun allTenseAndNonFinite(code: String?): List<TenseItem> {
        val p = get(code)
        return p.tenses + p.nonFinite
    }

    fun defaultSelectedTenses(code: String?): List<String> = get(code).defaultSelectedTenses

    fun showsTensePicker(code: String?): Boolean {
        val p = get(code)
        return p.showConjugationDefault && p.tenses.isNotEmpty()
    }

    fun tenseLabel(code: String?, key: String): String? {
        val n = normalizeTenseKey(key)
        return allTenseAndNonFinite(code).firstOrNull { it.key == n }?.label
            ?: allTenseAndNonFinite(code).firstOrNull { it.key == key }?.label
    }
}

fun verbTensesFor(learningLang: String?): List<Pair<String, String>> =
    LanguagePacks.tenseCatalog(learningLang).map { it.key to it.label }
