package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.SrsQueueItem
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PracticePromptTest {
    private val item = SrsQueueItem(
        card_id = "card",
        lemma_l2 = "perder",
        gloss_primary = "tracić",
        content = Json.parseToJsonElement(
            """{"meanings":[{"gloss_l1":"tracić"},{"gloss_l1":"przegrywać"},{"gloss_l1":"marnować"}]}""",
        ).jsonObject,
        status = "new",
    )

    @Test
    fun promptShowsAllGlossesOnlyWhenAskingInUiLanguage() {
        assertEquals(listOf("tracić", "przegrywać", "marnować"), practicePromptMeanings(item, "l1_to_l2"))
        assertEquals(listOf("perder"), practicePromptMeanings(item, "l2_to_l1"))
    }

    @Test
    fun promptSkipsMissingGlossesAndFallsBackToPrimary() {
        val content = Json.parseToJsonElement(
            """{"meanings":[null,{},{"gloss_l1":"  "},{"gloss_l1":" zdobyć "}]}""",
        ).jsonObject
        assertEquals(listOf("zdobyć"), practicePromptMeanings(item.copy(content = content), "l1_to_l2"))
        val empty = Json.parseToJsonElement("""{"meanings":[]}""").jsonObject
        assertEquals(listOf("tracić"), practicePromptMeanings(item.copy(content = empty), "l1_to_l2"))
        assertEquals(listOf("?"), practicePromptMeanings(item.copy(content = empty, gloss_primary = null), "l1_to_l2"))
    }

    @Test
    fun choicesFormPairsAndKeepRevealedWrongChoicesFullWidth() {
        val choices = (1..8).map { ChoiceOption(text = "choice$it") }
        assertEquals(listOf(2, 2, 2, 2), practiceChoiceRows(choices, emptySet()).map { it.size })
        val rows = practiceChoiceRows(choices, setOf("choice2", "choice6"))
        assertEquals(choices, rows.flatten())
        assertEquals(listOf("choice2"), rows.first { it.any { choice -> choice.text == "choice2" } }.map { it.text })
        assertEquals(listOf("choice6"), rows.first { it.any { choice -> choice.text == "choice6" } }.map { it.text })
        assertEquals(listOf(2, 1), practiceChoiceRows(choices.take(3), emptySet()).map { it.size })
    }
}
