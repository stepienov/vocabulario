package com.vocabulario.app.ui.practice

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vocabulario.app.R
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.PromptCard
import com.vocabulario.app.ui.theme.VocabularioTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PracticeChoicesTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun allEightChoicesFitAndOnlyLongTextShrinks() {
        val words = listOf(
            "ir", "acostumbrarse", "ver", "ganar", "leer",
            "responsabilizarse", "desacostumbrarse", "desinstitucionalización",
        )
        val state = PracticeUiState(choices = words.map { ChoiceOption(text = it) })
        compose.setContent {
            VocabularioTheme(themeMode = "light") {
                Column(Modifier.size(width = 320.dp, height = 400.dp)) {
                    PromptCard(
                        text = "tracić",
                        languageLabel = "Polski",
                        meanings = listOf("tracić", "przegrywać", "marnować"),
                        highlighted = true,
                    )
                    Spacer(Modifier.height(12.dp))
                    PracticeChoices(state, "l1_to_l2", {}, {}, Modifier.weight(1f))
                }
            }
        }

        compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE).assertCountEquals(8)
        words.forEach { compose.onNodeWithText(it).assertIsDisplayed() }
        val bounds = compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE)
            .fetchSemanticsNodes().map { it.boundsInRoot }
        val minimumHeight = with(compose.density) { 48.dp.toPx() }
        assertTrue("Choice bounds: $bounds; minimum height: $minimumHeight", bounds.all { it.height >= minimumHeight - 1f })
        assertEquals(4, bounds.map { it.top }.distinct().size)
        assertTrue(bounds.chunked(2).all { (left, right) -> left.left < right.left && left.top == right.top })
        val short = textLayout("ir")
        val long = textLayout("desinstitucionalización")
        assertEquals(16f, short.layoutInput.style.fontSize.value, 0.01f)
        assertTrue(long.layoutInput.style.fontSize.value < short.layoutInput.style.fontSize.value)
        assertTrue(!long.hasVisualOverflow)
        if (long.lineCount > 1) {
            assertTrue(long.getLineEnd(long.lineCount - 1) - long.getLineStart(long.lineCount - 1) > 1)
        }
    }

    @Test
    fun exceptionallyLongAnswerWrapsWithoutAnOrphanLetter() {
        val word = "desinstitucionalizacionextraordinariamentelarguisima"
        compose.setContent {
            VocabularioTheme(themeMode = "dark") {
                PracticeChoices(
                    PracticeUiState(choices = listOf(ChoiceOption(text = "ir"), ChoiceOption(text = word))),
                    "l1_to_l2",
                    {},
                    {},
                    Modifier.size(320.dp, 280.dp),
                )
            }
        }
        val layout = textLayout(word)
        assertEquals(10f, layout.layoutInput.style.fontSize.value, 0.01f)
        assertTrue(layout.lineCount > 1)
        assertTrue(!layout.hasVisualOverflow)
        assertTrue(layout.getLineEnd(layout.lineCount - 1) - layout.getLineStart(layout.lineCount - 1) > 1)
        assertEquals(16f, textLayout("ir").layoutInput.style.fontSize.value, 0.01f)
    }

    @Test
    fun revealedWrongAnswerKeepsItsAddAction() {
        val choice = ChoiceOption(text = "ganar", lemma_l2 = "ganar", gloss = "wygrywać")
        val state = PracticeUiState(
            choices = listOf(choice, ChoiceOption(text = "perder")),
            disabledChoiceTexts = setOf("ganar"),
        )
        var added: ChoiceOption? = null
        compose.setContent {
            VocabularioTheme(themeMode = "dark") {
                PracticeChoices(state, "l1_to_l2", {}, { added = it }, Modifier.size(320.dp, 280.dp))
            }
        }
        compose.onNodeWithText("wygrywać").assertIsDisplayed()
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        compose.onNodeWithContentDescription(context.getString(R.string.cd_add_to_list)).performClick()
        compose.runOnIdle { assertEquals(choice, added) }
    }

    private fun textLayout(text: String): TextLayoutResult {
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(text).performSemanticsAction(SemanticsActions.GetTextLayoutResult) {
            it(layouts)
        }
        return layouts.single()
    }
}
