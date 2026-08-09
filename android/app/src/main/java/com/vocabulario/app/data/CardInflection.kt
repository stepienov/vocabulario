package com.vocabulario.app.data

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject

/**
 * Resolves the conjugation display block from card JSON.
 * Uses legacy [conjugation] when present; otherwise maps [inflection].verbs (card.v1).
 */
fun conjugationFromContent(content: JsonObject): JsonObject? {
    content["conjugation"].asJsonObject()?.let { return it }
    val inflection = content["inflection"].asJsonObject() ?: return null
    val verbs = inflection["verbs"].asJsonObject() ?: return null
    val tenses = verbs["tenses"].asJsonObject()
    val nonFinite = verbs["non_finite"].asJsonObject()
    val periphrases = inflection["periphrases"].asJsonArray()
    val uiMeta = verbs["ui_meta"].asJsonObject()
    if (tenses == null && nonFinite == null && periphrases.isNullOrEmpty()) {
        return null
    }
    return buildJsonObject {
        tenses?.let { put("tenses", it) }
        nonFinite?.let { put("non_finite", it) }
        uiMeta?.let { put("ui_meta", it) }
        periphrases?.let { put("periphrases", it) }
    }
}
