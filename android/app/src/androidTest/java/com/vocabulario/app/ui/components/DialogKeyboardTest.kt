package com.vocabulario.app.ui.components

import android.accessibilityservice.AccessibilityServiceInfo
import android.graphics.Rect
import android.content.res.Resources
import android.view.View
import android.view.accessibility.AccessibilityWindowInfo
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.layout.positionOnScreen
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.platform.app.InstrumentationRegistry
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.home.ImportStartDialog
import com.vocabulario.app.ui.home.NameListDialog
import com.vocabulario.app.ui.settings.ChangePasswordDialog
import com.vocabulario.app.ui.settings.ChangePasswordUiState
import com.vocabulario.app.ui.theme.VocabularioTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class DialogKeyboardTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var activityView: View

    @Test
    fun listNameAboveKeyboard() {
        var name by mutableStateOf("")
        compose.setContent {
            activityView = LocalView.current
            VocabularioTheme {
                NameListDialog(true, "Nowa lista", name, { name = it }, null, false, {}, {}, true)
            }
        }
        checkField(compose.onNodeWithTag(TestTags.SHEET_LIST_NAME))
    }

    @Test
    fun listNameAboveKeyboardWhenOpenedFromSheet() {
        var showCreate by mutableStateOf(false)
        var name by mutableStateOf("")
        compose.setContent {
            activityView = LocalView.current
            VocabularioTheme {
                AddToListSheet(
                    lemma = "palabra", gloss = null, lists = emptyList(), pickListOpen = true,
                    showCreateListPrompt = showCreate, createListName = name, createNameError = null,
                    onDismiss = {}, onLearning = {}, onOther = {}, onPickList = {},
                    onCreateNameChange = { name = it }, onCreateAndAdd = {}, onShowCreatePrompt = {},
                    onBackFromCreatePrompt = {}, onBackFromListPicker = {},
                )
            }
        }
        compose.runOnIdle { showCreate = true }
        checkField(compose.onNodeWithTag(TestTags.SHEET_LIST_NAME))
    }

    @Test
    fun importTextAboveKeyboard() {
        var text by mutableStateOf("")
        compose.setContent {
            activityView = LocalView.current
            VocabularioTheme {
                ImportStartDialog(
                    lists = emptyList(), sourceLabel = null, pasteDraft = text,
                    onPasteDraftChange = { text = it }, onPickFile = {}, onClearFile = {},
                    onDismiss = {}, onStart = { _, _ -> }, listDisplayName = { it.name },
                )
            }
        }
        checkField(compose.onNodeWithTag(TestTags.IMPORT_PASTE_INPUT))
    }

    @Test
    fun lastPasswordFieldAboveKeyboard() {
        var form by mutableStateOf(ChangePasswordUiState())
        compose.setContent {
            activityView = LocalView.current
            VocabularioTheme {
                ChangePasswordDialog(
                    form = form,
                    onCurrentChange = { form = form.copy(current = it) },
                    onNewChange = { form = form.copy(new = it) },
                    onRepeatChange = { form = form.copy(repeat = it) },
                    onSubmit = {}, onDismiss = {},
                )
            }
        }
        checkField(compose.onAllNodes(hasSetTextAction())[2])
    }

    private fun checkField(field: SemanticsNodeInteraction) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        val info = automation.serviceInfo
        info.flags = info.flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
        automation.serviceInfo = info
        Thread.sleep(1500)
        field.performScrollTo().performClick()
        compose.waitUntil(15_000) {
            automation.windows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        }
        Thread.sleep(3000)
        field.performTextInput("test")
        val node = field.fetchSemanticsNode()
        val top = node.layoutInfo.coordinates?.positionOnScreen() ?: Offset.Zero
        val bottom = top.y + node.size.height
        val bounds = Rect()
        automation.windows.first { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }.getBoundsInScreen(bounds)
        val ime = ViewCompat.getRootWindowInsets(activityView)?.getInsets(WindowInsetsCompat.Type.ime())?.bottom ?: 0
        val keyboardTop = if (ime > 0) Resources.getSystem().displayMetrics.heightPixels - ime else bounds.top
        assertTrue("Field bottom $bottom is below keyboard top $keyboardTop", bottom <= keyboardTop)
    }
}
