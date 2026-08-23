package com.vocabulario.app.data

/**
 * Per-tense person-key order from LSP manifests (`person_grids`).
 * UI must use this instead of a single card-wide `person_order`, otherwise
 * extra imperative keys (e.g. Spanish usted) are dumped after the plurals.
 */
internal object PersonGrids {
    private data class LangGrids(
        val defaultKeys: List<String>,
        val byTense: Map<String, List<String>> = emptyMap(),
    )

    private val es6 = listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos")
    private val esImp = listOf("tú", "usted", "nosotros", "vosotros", "ustedes")
    private val fr6 = listOf("je", "tu", "il", "nous", "vous", "ils")
    private val it6 = listOf("io", "tu", "lui", "noi", "voi", "loro")
    private val de6 = listOf("ich", "du", "er", "wir", "ihr", "sie")
    private val pt6 = listOf("eu", "tu", "ele", "nós", "vós", "eles")
    private val ptImp = listOf("tu", "você", "nós", "vós", "vocês")
    private val en6 = listOf("I", "you", "he_she_it", "we", "you_pl", "they")
    private val plPresent = listOf("ja", "ty", "on", "ona", "ono", "my", "wy", "oni", "one")
    private val plPast = listOf(
        "ja_m", "ja_f", "ty_m", "ty_f", "on", "ona", "ono",
        "my_mv", "my_fv", "wy_mv", "wy_fv", "oni", "one",
    )
    private val ru6 = listOf("ya", "ty", "on", "my", "vy", "oni")
    private val ja6 = listOf("watashi", "anata", "kare", "watashitachi", "anatatachi", "karera")
    private val ko6 = listOf("jeo", "neo", "geu", "uri", "neohui", "geudeul")
    private val vi6 = listOf("toi", "ban", "no", "chung_toi", "cac_ban", "ho")
    private val ar13 = listOf(
        "1sg", "2sg_m", "2sg_f", "3sg_m", "3sg_f",
        "2du", "3du",
        "1pl", "2pl_m", "2pl_f", "3pl_m", "3pl_f",
    )
    private val hi6 = listOf("main", "tu", "yeh", "hum", "aap", "ve")

    private val grids: Map<String, LangGrids> = mapOf(
        "es" to LangGrids(
            defaultKeys = es6,
            byTense = mapOf(
                "imperativo_afirmativo" to esImp,
                "imperativo_negativo" to esImp,
            ),
        ),
        "fr" to LangGrids(
            defaultKeys = fr6,
            byTense = mapOf("imperatif" to listOf("tu", "nous", "vous")),
        ),
        "it" to LangGrids(
            defaultKeys = it6,
            byTense = mapOf("imperativo" to listOf("tu", "noi", "voi")),
        ),
        "de" to LangGrids(
            defaultKeys = de6,
            byTense = mapOf("imperativ" to listOf("du", "ihr", "Sie")),
        ),
        "pt" to LangGrids(
            defaultKeys = pt6,
            byTense = mapOf("imperativo" to ptImp),
        ),
        "pt-br" to LangGrids(
            defaultKeys = pt6,
            byTense = mapOf("imperativo" to ptImp),
        ),
        "pt-pt" to LangGrids(
            defaultKeys = pt6,
            byTense = mapOf(
                "imperativo" to ptImp,
                "infinitivo_pessoal" to pt6,
            ),
        ),
        "en" to LangGrids(defaultKeys = en6),
        "pl" to LangGrids(
            defaultKeys = plPresent,
            byTense = mapOf(
                "czas_terazniejszy" to plPresent,
                "czas_przyszly" to plPresent,
                "czas_przeszly" to plPast,
                "tryb_przypuszczajacy" to plPast,
                "tryb_rozkazujacy" to listOf("ty", "my", "wy"),
            ),
        ),
        "ru" to LangGrids(
            defaultKeys = ru6,
            byTense = mapOf(
                "proshedshee" to listOf("m", "f", "n", "pl"),
                "povelitelnoe" to listOf("ty", "my", "vy"),
            ),
        ),
        "tr" to LangGrids(defaultKeys = listOf("ben", "sen", "o", "biz", "siz", "onlar")),
        "ja" to LangGrids(
            defaultKeys = listOf("form"),
            byTense = mapOf("masu" to ja6),
        ),
        "ko" to LangGrids(
            defaultKeys = ko6,
            byTense = mapOf("imperative" to listOf("neo", "uri")),
        ),
        "zh" to LangGrids(defaultKeys = listOf("form")),
        "vi" to LangGrids(
            defaultKeys = vi6,
            byTense = mapOf("imperative" to listOf("ban", "cac_ban")),
        ),
        "ar" to LangGrids(
            defaultKeys = ar13,
            byTense = mapOf("imperative" to listOf("2sg_m", "2sg_f", "2pl_m", "2pl_f")),
        ),
        "hi" to LangGrids(
            defaultKeys = hi6,
            byTense = mapOf("imperative" to listOf("tu", "aap")),
        ),
    )

    fun keysFor(lang: String?, tenseKey: String?): List<String> {
        val pack = grids[lang?.lowercase()?.trim()]
            ?: grids[lang?.lowercase()?.trim()?.substringBefore('-')]
            ?: return emptyList()
        if (tenseKey.isNullOrBlank()) return pack.defaultKeys
        val normalized = normalizeTenseKey(tenseKey, lang)
        return pack.byTense[normalized]
            ?: pack.byTense[tenseKey]
            ?: pack.defaultKeys
    }
}
