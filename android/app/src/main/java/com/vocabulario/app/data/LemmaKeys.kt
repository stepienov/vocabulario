package com.vocabulario.app.data

private val LEMMA_ARTICLES = setOf(
    "el", "la", "los", "las",
    "le", "les", "un", "une",
    "der", "die", "das", "ein", "eine",
    "the", "a", "an",
    "il", "lo", "i", "gli",
    "o", "os", "as",
)

fun lemmaKey(raw: String?): String {
    val lower = raw?.trim()?.lowercase().orEmpty()
    if (lower.isEmpty()) return ""
    val parts = lower.split(Regex("\\s+"))
    val rest = if (parts.size > 1 && parts[0] in LEMMA_ARTICLES) {
        parts.drop(1).joinToString(" ")
    } else {
        lower
    }
    return rest.removePrefix("l'").removePrefix("l’")
}

fun lemmaKeys(raw: String?): Set<String> {
    val exact = raw?.trim()?.lowercase().orEmpty()
    if (exact.isEmpty()) return emptySet()
    return setOf(exact, lemmaKey(exact)).filter { it.isNotEmpty() }.toSet()
}

fun Set<String>.containsLemma(raw: String?): Boolean {
    val keys = lemmaKeys(raw)
    return keys.isNotEmpty() && keys.any { it in this }
}
