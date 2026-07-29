package com.vocabulario.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

val SUPPORTED_UI_LANGS = listOf(
    "pl" to "Polski",
    "en" to "English",
    "es" to "Español",
    "de" to "Deutsch",
    "fr" to "Français",
    "it" to "Italiano",
    "pt" to "Português",
    "uk" to "Українська",
)

val SUPPORTED_LEARNING_LANGS = SUPPORTED_UI_LANGS

fun langDisplayName(code: String): String =
    SUPPORTED_LEARNING_LANGS.firstOrNull { it.first == code.lowercase() }?.second ?: code.uppercase()

/** Część mowy w języku UI (PL). */
fun posLabelPl(pos: String?): String = when (pos?.lowercase()?.trim()) {
    "verb", "v", "vb" -> "czasownik"
    "noun", "n", "nn" -> "rzeczownik"
    "adj", "adjective", "a" -> "przymiotnik"
    "adv", "adverb" -> "przysłówek"
    "prep", "preposition" -> "przyimek"
    "conj", "conjunction" -> "spójnik"
    "pron", "pronoun" -> "zaimek"
    "interj", "interjection" -> "wykrzyknik"
    "det", "determiner", "article" -> "przedimek"
    null, "" -> ""
    else -> pos
}

val CEFR_LEVELS = listOf("A1", "A2", "B1", "B2", "C1", "C2")

val VERB_TENSES = listOf(
    "presente" to "Presente",
    "preterito_perfecto" to "Pretérito perfecto",
    "preterito_indefinido" to "Pretérito indefinido",
    "preterito_imperfecto" to "Imperfecto",
    "futuro_simple" to "Futuro simple",
    "condicional_simple" to "Condicional",
    "presente_subjuntivo" to "Presente de subjuntivo",
    "imperfecto_subjuntivo" to "Imperfecto de subjuntivo",
    "futuro_subjuntivo" to "Futuro de subjuntivo",
    "preterito_pluscuamperfecto" to "Pretérito pluscuamperfecto",
    "condicional_compuesto" to "Condicional compuesto",
    "futuro_perfecto" to "Futuro perfecto",
    "imperativo_afirmativo" to "Imperativo afirmativo",
    "imperativo_negativo" to "Imperativo negativo",
)

val NON_FINITE_FORMS = listOf(
    "gerundio" to "Gerundio",
    "participio" to "Participio",
)

/** Domyślnie widoczne w karcie, gdy użytkownik nie wybrał czasów w profilu. */
val DEFAULT_CARD_TENSES = listOf("presente", "gerundio", "participio")

/** Mapowanie starych kluczy profilu na klucze z pełnej koniugacji w bazie. */
val TENSE_KEY_ALIASES = mapOf(
    "imperfecto" to "preterito_imperfecto",
    "futuro" to "futuro_simple",
    "condicional" to "condicional_simple",
)

fun normalizeTenseKey(key: String): String = TENSE_KEY_ALIASES[key] ?: key

/** Jedno zdanie na pasmo poziomów — A2 dla AX, B2 dla BX, C2 dla CX. */
val EXAMPLE_BANDS = listOf("A2", "B2", "C2")

/** Przykład dla pasma użytkownika; fallback na niższe pasmo, gdy brak zdania. */
fun examplesForUserLevel(
    examples: JsonArray?,
    userCefr: String,
    maxCount: Int = 2,
): List<JsonObject> {
    if (examples == null) return emptyList()
    val all = examples.mapNotNull { runCatching { it.jsonObject }.getOrNull() }
    if (all.isEmpty()) return emptyList()

    val band = userCefr.take(1).uppercase()
    val bandIdx = EXAMPLE_BANDS.indexOfFirst { it.startsWith(band) }.coerceAtLeast(0)
    for (idx in bandIdx downTo 0) {
        val level = EXAMPLE_BANDS[idx]
        val matched = all.filter {
            it["cefr"]?.jsonPrimitive?.content?.uppercase() == level
        }
        if (matched.isNotEmpty()) return matched.take(maxCount)
    }
    return all.take(maxCount)
}

val NEW_CARDS_OPTIONS = listOf(
    5 to "5 nowych / dzień",
    10 to "10 nowych / dzień",
    20 to "20 nowych / dzień",
    50 to "50 nowych / dzień",
    0 to "Bez limitu",
)
