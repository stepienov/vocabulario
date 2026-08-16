package com.vocabulario.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** Safe: JSON null is not Kotlin null, so `?.jsonObject` still throws. */
fun JsonElement?.asJsonObject(): JsonObject? = this as? JsonObject

fun JsonElement?.asJsonArray(): JsonArray? = this as? JsonArray

fun JsonElement?.asJsonString(): String? =
    (this as? JsonPrimitive)?.contentOrNull?.let(::repairDisplayText)

/**
 * LLM/Windows sometimes stores UTF-8 punctuation as CP852 mojibake
 * (`ÔÇ×casaÔÇŁ` instead of `„casa”`). Fix at read time so old cards render.
 */
fun repairDisplayText(raw: String): String {
    if (raw.isEmpty() || raw.none { it == 'Ô' || it == 'â' || it == 'Â' }) return raw
    var out = raw
    CP852_PUNCT.forEach { (bad, good) ->
        if (out.contains(bad)) out = out.replace(bad, good)
    }
    return out
}

private val CP852_PUNCT = listOf(
    "ÔÇť" to "\u201C",
    "ÔÇŁ" to "\u201D",
    "ÔÇ×" to "\u201E",
    "ÔÇś" to "\u2018",
    "ÔÇÖ" to "\u2019",
    "ÔÇô" to "\u2013",
    "ÔÇö" to "\u2014",
    "ÔÇŽ" to "\u2026",
    "â€œ" to "\u201C",
    "â€\u009d" to "\u201D",
    "â€ž" to "\u201E",
    "â€˜" to "\u2018",
    "â€™" to "\u2019",
    "Â«" to "\u00AB",
    "Â»" to "\u00BB",
)
