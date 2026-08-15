package com.vocabulario.app.ui.card

/**
 * One row of the conjugation grid: singular (left) and plural (right).
 * Either side may be null when counts differ (e.g. Spanish imperative).
 */
data class ConjugationGridRow<T>(
    val singular: T?,
    val plural: T?,
)

private enum class GrammaticalNumber { SINGULAR, PLURAL, UNKNOWN }

/**
 * Arrange person forms as singular | plural columns for every tense/language
 * that has a person grid with both numbers.
 */
fun <T> conjugationPersonGridRows(
    persons: List<T>,
    keyOf: (T) -> String,
    labelOf: (T) -> String = keyOf,
): List<ConjugationGridRow<T>> {
    if (persons.isEmpty()) return emptyList()

    val singular = ArrayList<T>()
    val plural = ArrayList<T>()
    val unknown = ArrayList<T>()
    for (person in persons) {
        when (grammaticalNumber(keyOf(person), labelOf(person))) {
            GrammaticalNumber.SINGULAR -> singular.add(person)
            GrammaticalNumber.PLURAL -> plural.add(person)
            GrammaticalNumber.UNKNOWN -> unknown.add(person)
        }
    }

    if (singular.isEmpty() || plural.isEmpty()) {
        return persons.chunked(2).map { chunk ->
            ConjugationGridRow(chunk.getOrNull(0), chunk.getOrNull(1))
        }
    }

    val rows = ArrayList<ConjugationGridRow<T>>()
    val n = maxOf(singular.size, plural.size)
    for (i in 0 until n) {
        rows.add(ConjugationGridRow(singular.getOrNull(i), plural.getOrNull(i)))
    }
    for (item in unknown) {
        rows.add(ConjugationGridRow(item, null))
    }
    return rows
}

private fun grammaticalNumber(key: String, label: String): GrammaticalNumber {
    val k = normalizePersonToken(key)
    val l = normalizePersonToken(label)

    // Longer / more specific plural keys first (ustedes before usted).
    if (k in PLURAL_KEYS || k.startsWith("nosotros") || k.startsWith("vosotros") ||
        k.startsWith("ustedes") || k.startsWith("ellos") || k.startsWith("ellas")
    ) {
        return GrammaticalNumber.PLURAL
    }
    if (k in SINGULAR_KEYS || (k.startsWith("usted") && !k.startsWith("ustedes"))) {
        return GrammaticalNumber.SINGULAR
    }

    val base = k.substringBefore('_')
    if (base != k) {
        if (base in PLURAL_KEYS) return GrammaticalNumber.PLURAL
        if (base in SINGULAR_KEYS) return GrammaticalNumber.SINGULAR
    }

    when {
        PLURAL_LABEL_HINT.containsMatchIn(l) -> return GrammaticalNumber.PLURAL
        SINGULAR_LABEL_HINT.containsMatchIn(l) -> return GrammaticalNumber.SINGULAR
    }
    return GrammaticalNumber.UNKNOWN
}

private fun normalizePersonToken(raw: String): String =
    raw.trim().lowercase()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
        .replace("ą", "a")
        .replace("ę", "e")
        .replace("ł", "l")
        .replace("ń", "n")
        .replace("ś", "s")
        .replace("ź", "z")
        .replace("ż", "z")
        .replace("ß", "ss")

private val PLURAL_KEYS = setOf(
    "nosotros", "vosotros", "ellos", "ellas", "ustedes",
    "noi", "voi", "loro",
    "nous", "vous", "ils", "elles",
    "eles", "elas", "voces", "nosaltres", "vosaltres",
    "wir", "ihr", "sie",
    "my", "wy", "oni", "one",
    "my_mv", "my_fv", "my_m", "my_f",
    "wy_mv", "wy_fv", "wy_m", "wy_f",
    "vy", "ony",
    "we", "you_pl", "they", "you_all",
)

private val SINGULAR_KEYS = setOf(
    "yo", "tu", "el", "ella", "ello", "usted",
    "vos", // voseo 2sg (not vosotros)
    "je", "il", "elle", "on",
    "ich", "du", "er", "es",
    "io", "lui", "lei",
    "eu", "voce", "ele", "ela",
    "ja", "ty", "on", "ona", "ono",
    "ja_m", "ja_f", "ja_z", "ty_m", "ty_f", "ty_z",
    "i", "you_sg", "he", "she", "it",
)

private val PLURAL_LABEL_HINT = Regex(
    """\b(nosotros|vosotros|ellos|ellas|ustedes|nous|vous|ils|elles|wir|ihr|""" +
        """my|wy|oni|one|noi|voi|loro|eles|elas|voces|we|they)\b""",
)

private val SINGULAR_LABEL_HINT = Regex(
    """\b(yo|tu|el|ella|ello|usted|je|il|elle|on|ich|du|er|es|io|lui|lei|""" +
        """eu|voce|ele|ela|ja|ty|ona|ono|i|he|she|it)\b""",
)
