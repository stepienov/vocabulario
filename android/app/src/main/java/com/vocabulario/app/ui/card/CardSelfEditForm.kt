package com.vocabulario.app.ui.card

import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

data class SelfEditPairRow(val l2: String = "", val l1: String = "")

data class SelfEditMeaningRow(
    val glossL1: String = "",
    val examples: List<SelfEditPairRow> = emptyList(),
    val usages: List<SelfEditPairRow> = emptyList(),
)

data class SelfEditFormState(
    val cardId: String,
    val lemma: String,
    val pos: String = "",
    val notes: String = "",
    val meanings: List<SelfEditMeaningRow> = emptyList(),
)

fun parseSelfEditForm(card: CardResponse): SelfEditFormState {
    val content = card.content
    val meanings = content["meanings"].asJsonArray().orEmpty().map { el ->
        val m = el.asJsonObject() ?: return@map SelfEditMeaningRow()
        SelfEditMeaningRow(
            glossL1 = m["gloss_l1"].asJsonString().orEmpty(),
            examples = m["examples"].asJsonArray()
                ?.mapNotNull { ex ->
                    val o = ex.asJsonObject() ?: return@mapNotNull null
                    SelfEditPairRow(
                        l2 = o["l2"].asJsonString().orEmpty(),
                        l1 = o["l1"].asJsonString().orEmpty(),
                    )
                }.orEmpty(),
            usages = m["usages"].asJsonArray()
                ?.mapNotNull { u ->
                    val o = u.asJsonObject() ?: return@mapNotNull null
                    SelfEditPairRow(
                        l2 = o["l2"].asJsonString().orEmpty(),
                        l1 = o["l1"].asJsonString().orEmpty(),
                    )
                }.orEmpty(),
        )
    }
    val normalized = meanings.ifEmpty {
        listOf(SelfEditMeaningRow(glossL1 = card.gloss_primary.orEmpty()))
    }
    return SelfEditFormState(
        cardId = card.id,
        lemma = content["lemma"].asJsonString() ?: card.lemma_l2,
        pos = content["pos"].asJsonString() ?: card.pos.orEmpty(),
        notes = content["notes"].asJsonString().orEmpty(),
        meanings = normalized,
    )
}

fun selfEditFormHasChanges(baseline: SelfEditFormState, current: SelfEditFormState): Boolean =
    baseline != current

fun buildSelfEditContent(original: JsonObject, state: SelfEditFormState): JsonObject {
    val originalMeanings = original["meanings"].asJsonArray().orEmpty()
    val meanings = buildJsonArray {
        state.meanings.forEachIndexed { index, row ->
            if (row.glossL1.isBlank() &&
                row.examples.all { it.l2.isBlank() && it.l1.isBlank() } &&
                row.usages.all { it.l2.isBlank() && it.l1.isBlank() }
            ) {
                return@forEachIndexed
            }
            val orig = originalMeanings.getOrNull(index)?.asJsonObject()
            add(
                buildJsonObject {
                    put("gloss_l1", row.glossL1.trim())
                    putJsonArray("synonyms_l1") {
                        orig?.get("synonyms_l1").asJsonArray()?.forEach { syn ->
                            add(syn)
                        }
                    }
                    putJsonArray("examples") {
                        row.examples
                            .filter { it.l2.isNotBlank() || it.l1.isNotBlank() }
                            .forEach { ex ->
                                add(
                                    buildJsonObject {
                                        put("l2", ex.l2.trim())
                                        put("l1", ex.l1.trim())
                                    },
                                )
                            }
                    }
                    putJsonArray("usages") {
                        row.usages
                            .filter { it.l2.isNotBlank() || it.l1.isNotBlank() }
                            .forEach { u ->
                                add(
                                    buildJsonObject {
                                        put("l2", u.l2.trim())
                                        put("l1", u.l1.trim())
                                    },
                                )
                            }
                    }
                },
            )
        }
    }
    return buildJsonObject {
        original.forEach { (key, value) -> put(key, value) }
        if (state.pos.isNotBlank()) put("pos", state.pos.trim())
        put("notes", state.notes.trim())
        put("meanings", meanings)
    }
}
