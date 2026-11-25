package com.vocabulario.app.ui.practice

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vocabulario.app.R
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.RelatedMembership
import com.vocabulario.app.data.RelatedMembershipIndex
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.LemmaActionRow
import com.vocabulario.app.ui.components.LemmaAddButton
import com.vocabulario.app.ui.components.LemmaOnListIndicator
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
                PracticeQuiz(
                    state, "l1_to_l2",
                    listOf("tracić", "przegrywać", "marnować"), "Polski", {}, {},
                    Modifier.size(width = 320.dp, height = 400.dp),
                )
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
        assertEquals(18f, short.layoutInput.style.fontSize.value, 0.01f)
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
        assertEquals(18f, textLayout("ir").layoutInput.style.fontSize.value, 0.01f)
    }

    @Test
    fun multiWordAnswerWrapsBeforeShrinkingAndTilesStayCentered() {
        val answer = "przyjmować odpowiedzialność"
        compose.setContent {
            VocabularioTheme {
                PracticeChoices(
                    PracticeUiState(choices = listOf(ChoiceOption(text = answer), ChoiceOption(text = "ir"))),
                    "l1_to_l2", {}, {}, Modifier.size(320.dp, 280.dp),
                )
            }
        }
        val layout = textLayout(answer)
        assertTrue(layout.lineCount == 2)
        assertEquals("przyjmować", answer.substring(layout.getLineStart(0), layout.getLineEnd(0, visibleEnd = true)))
        assertEquals("odpowiedzialność", answer.substring(layout.getLineStart(1), layout.getLineEnd(1, visibleEnd = true)))
        assertTrue(layout.layoutInput.style.fontSize.value > 10f)
        assertTrue(!layout.hasVisualOverflow)
        assertEquals(18f, textLayout("ir").layoutInput.style.fontSize.value, 0.01f)
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

    @Test
    fun sixWrongAnswersNeverMoveTilesAndCanBeRevisitedWithoutSubmitting() {
        val choices = (0..7).map { ChoiceOption(text = "word$it", lemma_l2 = "lemma$it", gloss = "gloss$it") }
        val state = mutableStateOf(PracticeUiState(choices = choices))
        val theme = mutableStateOf("light")
        val height = mutableStateOf(400.dp)
        var submissions = 0
        compose.setContent {
            VocabularioTheme(themeMode = theme.value) {
                PracticeQuiz(
                    state.value, "l2_to_l1", listOf("perder"), "Español",
                    { submissions++ }, {}, Modifier.size(320.dp, height.value),
                )
            }
        }
        for (mode in listOf("light", "dark")) {
            for (availableHeight in listOf(400.dp, 540.dp)) {
                compose.runOnIdle {
                    theme.value = mode
                    height.value = availableHeight
                    submissions = 0
                    state.value = state.value.copy(disabledChoiceTexts = emptySet())
                }
                val before = compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE)
                    .fetchSemanticsNodes().map { it.boundsInRoot }
                val footer = compose.onNodeWithTag(TestTags.PRACTICE_CHOICE_DETAILS).fetchSemanticsNode().boundsInRoot
                for (count in listOf(2, 5, 6)) {
                    compose.runOnIdle {
                        state.value = state.value.copy(disabledChoiceTexts = choices.take(count).map { it.text }.toSet())
                    }
                    val after = compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE)
                        .fetchSemanticsNodes().map { it.boundsInRoot }
                    assertEquals(before, after)
                    assertEquals(footer, compose.onNodeWithTag(TestTags.PRACTICE_CHOICE_DETAILS).fetchSemanticsNode().boundsInRoot)
                    assertTrue(after.all { it.bottom <= footer.top })
                    choices.forEach { compose.onNodeWithText(it.text).assertIsDisplayed() }
                    compose.onNodeWithText("gloss${count - 1}").assertIsDisplayed()
                }
                compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE)[0].performClick()
                compose.onNodeWithText("lemma0").assertIsDisplayed()
                compose.onNodeWithText("gloss0").assertIsDisplayed()
                compose.runOnIdle { assertEquals(0, submissions) }
                compose.onAllNodesWithTag(TestTags.PRACTICE_CHOICE)[7].performClick()
                compose.runOnIdle { assertEquals(1, submissions) }
            }
            compose.runOnIdle { submissions = 0 }
        }
    }

    @Test
    fun customListChipAndCheckHideAdd() {
        val choice = ChoiceOption(text = "pamiętać", lemma_l2 = "recordar", gloss = "pamiętać")
        val state = mutableStateOf(
            PracticeUiState(
                choices = listOf(choice, ChoiceOption(text = "tracić")),
                disabledChoiceTexts = setOf(choice.text),
                relatedMembership = RelatedMembershipIndex(
                    listOf(RelatedMembership("recordar", "Powtórki", false, "card", null, setOf("recordar"))),
                ),
            ),
        )
        compose.setContent {
            VocabularioTheme(themeMode = "dark") {
                PracticeChoices(state.value, "l2_to_l1", {}, {}, Modifier.size(320.dp, 300.dp))
            }
        }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        compose.onNodeWithText("Powtórki").assertIsDisplayed()
        compose.onNodeWithText("recordar").assertIsDisplayed()
        compose.onNodeWithContentDescription(context.getString(R.string.cd_on_list)).assertIsDisplayed()
        compose.onNodeWithContentDescription(context.getString(R.string.cd_add_to_list)).assertDoesNotExist()
    }

    @Test
    fun listPlusAndCheckHaveIdenticalSizeAndAlignment() {
        compose.setContent {
            VocabularioTheme(themeMode = "light") {
                Column(Modifier.size(320.dp, 300.dp)) {
                    LemmaActionRow(
                        "ganar", "wygrywać",
                        trailing = { LemmaOnListIndicator(Modifier.testTag("saved")) },
                        modifier = Modifier.testTag("saved-row"),
                    )
                    Spacer(Modifier.height(8.dp))
                    LemmaActionRow(
                        "ahorrar", "oszczędzać",
                        trailing = { LemmaAddButton({}, "add", Modifier.testTag("add")) },
                        modifier = Modifier.testTag("add-row"),
                    )
                }
            }
        }
        val saved = compose.onNodeWithTag("saved").fetchSemanticsNode().boundsInRoot
        val add = compose.onNodeWithTag("add").fetchSemanticsNode().boundsInRoot
        val size = with(compose.density) { 40.dp.toPx() }
        assertEquals(size, saved.width, 1f)
        assertEquals(size, saved.height, 1f)
        assertEquals(saved.width, add.width, 1f)
        assertEquals(saved.height, add.height, 1f)
        assertEquals(saved.right, add.right, 1f)
        val savedRow = compose.onNodeWithTag("saved-row").fetchSemanticsNode().boundsInRoot
        val addRow = compose.onNodeWithTag("add-row").fetchSemanticsNode().boundsInRoot
        assertEquals(savedRow.center.y, saved.center.y, 1f)
        assertEquals(addRow.center.y, add.center.y, 1f)
    }

    private fun textLayout(text: String): TextLayoutResult {
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(text).performSemanticsAction(SemanticsActions.GetTextLayoutResult) {
            it(layouts)
        }
        return layouts.single()
    }
}
