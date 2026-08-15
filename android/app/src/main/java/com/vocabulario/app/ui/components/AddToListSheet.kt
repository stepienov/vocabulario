package com.vocabulario.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.ui.TestTags
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.ui.home.NameListDialog
import com.vocabulario.app.ui.home.isReservedListNameMessage

private val SheetControlHeight = 52.dp
private val SheetControlSpacing = 10.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddToListSheet(
    lemma: String,
    gloss: String?,
    lists: List<WordListResponse>,
    pickListOpen: Boolean,
    showCreateListPrompt: Boolean,
    createListName: String,
    createNameError: String?,
    onDismiss: () -> Unit,
    onLearning: () -> Unit,
    onOther: () -> Unit,
    onPickList: (String) -> Unit,
    onCreateNameChange: (String) -> Unit,
    onCreateAndAdd: () -> Unit,
    onShowCreatePrompt: () -> Unit,
    onBackFromCreatePrompt: () -> Unit,
    onBackFromListPicker: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val customLists = remember(lists) { lists.filterNot { it.is_system } }
    val context = LocalContext.current
    val reservedName = isReservedListNameMessage(context, createListName)

    if (showCreateListPrompt) {
        NameListDialog(
            visible = true,
            title = stringResource(R.string.list_new),
            name = createListName,
            onNameChange = onCreateNameChange,
            nameError = createNameError,
            reservedHint = reservedName,
            onDismiss = onBackFromCreatePrompt,
            onConfirm = onCreateAndAdd,
            confirmEnabled = createListName.trim().isNotBlank() && createNameError == null,
            extraBody = {
                Text(
                    lemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
            },
            confirmTag = TestTags.SHEET_CREATE_AND_ADD,
            cancelTag = TestTags.SHEET_BACK_FROM_CREATE,
        )
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        shape = AppButtonShape,
        containerColor = scheme.surface,
        tonalElevation = 0.dp,
    ) {
        AppDialogWindowChrome()
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 28.dp, top = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                lemma,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            if (!gloss.isNullOrBlank()) {
                Text(
                    gloss,
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 6.dp),
                )
            }
            Spacer(Modifier.height(22.dp))

            when {
                !pickListOpen -> {
                    SheetPrimaryButton(
                        text = stringResource(R.string.list_learning),
                        onClick = onLearning,
                        modifier = Modifier.testTag(TestTags.SHEET_ADD_LEARNING),
                    )
                    Spacer(Modifier.height(SheetControlSpacing))
                    SheetOutlinedButton(
                        text = stringResource(R.string.list_other),
                        onClick = onOther,
                        modifier = Modifier.testTag(TestTags.SHEET_ADD_OTHER),
                    )
                }
                else -> {
                    customLists.forEach { list ->
                        SheetListRow(
                            text = list.name,
                            onClick = { onPickList(list.id) },
                        )
                        Spacer(Modifier.height(SheetControlSpacing))
                    }
                    SheetOutlinedButton(
                        text = stringResource(R.string.list_new),
                        onClick = onShowCreatePrompt,
                        modifier = Modifier.testTag(TestTags.SHEET_NEW_LIST),
                    )
                    Spacer(Modifier.height(SheetControlSpacing))
                    SheetOutlinedButton(
                        text = stringResource(R.string.action_cancel),
                        onClick = onBackFromListPicker,
                        modifier = Modifier.testTag(TestTags.SHEET_BACK_FROM_LIST_PICKER),
                    )
                }
            }
        }
    }
}

@Composable
private fun SheetPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(SheetControlHeight),
        shape = AppButtonShape,
        colors = ButtonDefaults.buttonColors(containerColor = scheme.primary),
    ) {
        Text(text, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun SheetOutlinedButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(SheetControlHeight),
        shape = AppButtonShape,
        border = BorderStroke(1.dp, scheme.outline),
    ) {
        Text(text, fontWeight = FontWeight.SemiBold, color = scheme.onSurface)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SheetListRow(
    text: String,
    onClick: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = AppButtonShape,
        color = scheme.surfaceVariant,
        modifier = Modifier
            .fillMaxWidth()
            .height(SheetControlHeight),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            contentAlignment = Alignment.CenterStart,
        ) {
            Text(
                text,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
