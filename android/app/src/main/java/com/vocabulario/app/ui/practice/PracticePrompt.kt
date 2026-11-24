package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString

internal fun practicePromptMeanings(item: SrsQueueItem, direction: String): List<String> {
    if (direction == "l2_to_l1") return listOf(item.lemma_l2)
    val meanings = item.content["meanings"].asJsonArray().orEmpty().mapNotNull { element ->
        element.asJsonObject()?.get("gloss_l1").asJsonString()?.trim()?.takeIf { it.isNotEmpty() }
    }
    return meanings.ifEmpty { listOf(item.gloss_primary?.takeIf { it.isNotBlank() } ?: "?") }
}

internal fun practiceChoiceRows(
    choices: List<ChoiceOption>,
    disabledTexts: Set<String>,
): List<List<ChoiceOption>> {
    val rows = mutableListOf<List<ChoiceOption>>()
    var pending: ChoiceOption? = null
    for (choice in choices) {
        if (choice.text in disabledTexts) {
            pending?.let { rows.add(listOf(it)) }
            pending = null
            rows.add(listOf(choice))
        } else if (pending == null) {
            pending = choice
        } else {
            rows.add(listOf(pending, choice))
            pending = null
        }
    }
    pending?.let { rows.add(listOf(it)) }
    return rows
}
