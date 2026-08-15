package com.vocabulario.app.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.ImportDisplayCard
import com.vocabulario.app.data.api.ImportValidWord
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.imports.ImportJobState
import com.vocabulario.app.data.imports.ImportResult
import com.vocabulario.app.data.imports.ImportStatus
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.ImportDisplayFlip

@Composable
fun ImportStatusPanel(
    state: ImportJobState,
    onAbort: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val source = state.sourceName.orEmpty()
    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag(TestTags.IMPORT_STATUS_PANEL)
            .padding(vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        CircularProgressIndicator(color = scheme.primary, strokeWidth = 3.dp)
        Text(
            text = when (state.status) {
                ImportStatus.Processing ->
                    stringResource(R.string.import_status_analyzing, source)
                ImportStatus.Committing ->
                    stringResource(R.string.import_status_importing, source)
                else -> stringResource(R.string.import_progress)
            },
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            color = scheme.onSurface,
        )
        if (state.status == ImportStatus.Committing && state.total > 0) {
            Text(
                stringResource(R.string.import_progress_count, state.processed, state.total),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
        }
        Button(
            onClick = onAbort,
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp)
                .testTag(TestTags.IMPORT_BTN_ABORT),
            shape = AppButtonShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = scheme.error,
                contentColor = scheme.onError,
            ),
        ) {
            Text(stringResource(R.string.action_abort), fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
fun ImportAbortConfirmDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    DestroyConfirmDialog(
        visible = true,
        title = stringResource(R.string.import_abort_title),
        confirmText = stringResource(R.string.action_abort),
        onDismiss = onDismiss,
        onConfirm = onConfirm,
        confirmTag = TestTags.DIALOG_CONFIRM,
        cancelTag = TestTags.DIALOG_CANCEL,
        dialogTag = TestTags.IMPORT_ABORT_CONFIRM,
    )
}

@Composable
fun ImportResultDialog(
    result: ImportResult,
    onShowList: () -> Unit,
    onOk: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val body = if (result.failed > 0) {
        stringResource(
            R.string.import_result_body_failed,
            result.created,
            result.duplicates,
            result.failed,
        )
    } else {
        stringResource(R.string.import_result_body, result.created, result.duplicates)
    }
    AppAlertDialog(
        onDismissRequest = onOk,
        modifier = Modifier.testTag(TestTags.IMPORT_RESULT_MODAL),
        title = stringResource(R.string.import_result_title),
        text = { Text(body) },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_show_list),
                onSecondary = onShowList,
                secondaryKind = AppDialogAction.Neutral,
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onOk,
                primaryModifier = Modifier.testTag(TestTags.IMPORT_RESULT_OK),
            )
        },
    )
}

@Composable
fun ImportErrorDialog(
    message: String,
    onDismiss: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.import_result_title),
        text = { Text(message) },
        buttons = {
            AppDialogButtonRow(
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onDismiss,
                primaryModifier = Modifier.testTag(TestTags.IMPORT_RESULT_OK),
            )
        },
    )
}

@Composable
fun ImportReviewDialog(
    state: ImportJobState,
    onToggle: (String) -> Unit,
    onCancel: () -> Unit,
    onConfirm: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val flaggedKinds = setOf("construction", "phrase", "sentence")
    val preserve = state.mode == "preserve"
    val regularWords = if (!preserve) {
        state.valid.filter { it.entry_kind.lowercase() !in flaggedKinds }
    } else emptyList()
    val flaggedWords = if (!preserve) {
        state.valid.filter { it.entry_kind.lowercase() in flaggedKinds }
    } else emptyList()
    val regularCards = if (preserve) {
        state.displayCards.filter { it.display.prompt_style !in setOf("phrase", "sentence") }
    } else emptyList()
    val flaggedCards = if (preserve) {
        state.displayCards.filter { it.display.prompt_style in setOf("phrase", "sentence") }
    } else emptyList()

    AppAlertDialog(
        onDismissRequest = onCancel,
        modifier = Modifier.testTag(TestTags.IMPORT_REVIEW_MODAL),
        title = stringResource(R.string.import_start_title),
        text = {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 420.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (regularWords.isNotEmpty() || regularCards.isNotEmpty()) {
                    item {
                        Text(
                            stringResource(R.string.import_review_ready),
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    items(regularCards, key = { it.key }) { card ->
                        ImportReviewDisplayRow(
                            card = card,
                            checked = card.key !in state.deselectedKeys,
                            onToggle = { onToggle(card.key) },
                        )
                    }
                    items(regularWords, key = { it.input }) { word ->
                        ImportReviewWordRow(
                            word = word,
                            checked = word.input !in state.deselectedKeys,
                            onToggle = { onToggle(word.input) },
                        )
                    }
                }
                if (flaggedWords.isNotEmpty() || flaggedCards.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.import_review_flagged),
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = scheme.tertiary,
                        )
                    }
                    items(flaggedCards, key = { "f-${it.key}" }) { card ->
                        ImportReviewDisplayRow(
                            card = card,
                            checked = card.key !in state.deselectedKeys,
                            onToggle = { onToggle(card.key) },
                        )
                    }
                    items(flaggedWords, key = { "f-${it.input}" }) { word ->
                        ImportReviewWordRow(
                            word = word,
                            checked = word.input !in state.deselectedKeys,
                            onToggle = { onToggle(word.input) },
                        )
                    }
                }
                if (state.invalid.isNotEmpty()) {
                    item {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.import_invalid_title),
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = scheme.error,
                        )
                    }
                    items(state.invalid) { w ->
                        Text("• $w", color = scheme.onSurfaceVariant)
                    }
                }
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onCancel,
                secondaryModifier = Modifier.testTag(TestTags.BTN_IMPORT_CANCEL),
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onConfirm,
                primaryEnabled = state.selectedCount > 0,
                primaryModifier = Modifier.testTag(TestTags.BTN_IMPORT_CONFIRM),
            )
        },
    )
}

@Composable
private fun ImportReviewWordRow(
    word: ImportValidWord,
    checked: Boolean,
    onToggle: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(TestTags.IMPORT_REVIEW_ITEM)
            .clickable(onClick = onToggle),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked = checked, onCheckedChange = { onToggle() })
        Column(modifier = Modifier.weight(1f)) {
            Text(word.lemma, fontWeight = FontWeight.SemiBold, maxLines = 2)
            val sub = listOfNotNull(
                entryKindLabel(word.entry_kind),
                word.gloss.takeIf { it.isNotBlank() },
            ).joinToString(" · ")
            if (sub.isNotBlank()) {
                Text(sub, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ImportReviewDisplayRow(
    card: ImportDisplayCard,
    checked: Boolean,
    onToggle: () -> Unit,
) {
    var expanded by remember(card.key) { mutableStateOf(false) }
    Column(modifier = Modifier.fillMaxWidth().testTag(TestTags.IMPORT_REVIEW_ITEM)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onToggle),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = checked, onCheckedChange = { onToggle() })
            Text(
                card.lemma_l2,
                modifier = Modifier
                    .weight(1f)
                    .clickable { expanded = !expanded },
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
            )
        }
        if (expanded) {
            ImportDisplayFlip(
                display = card.display,
                modifier = Modifier.padding(start = 40.dp),
            )
        }
    }
}

@Composable
private fun entryKindLabel(kind: String): String? = when (kind.lowercase()) {
    "lemma" -> stringResource(R.string.kind_lemma)
    "phrase" -> stringResource(R.string.kind_phrase)
    "construction" -> stringResource(R.string.kind_construction)
    "sentence" -> stringResource(R.string.kind_sentence)
    "other" -> stringResource(R.string.kind_other)
    else -> null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImportStartDialog(
    lists: List<WordListResponse>,
    sourceLabel: String?,
    pasteMode: Boolean,
    pasteDraft: String,
    onPasteDraftChange: (String) -> Unit,
    onPickFile: () -> Unit,
    onDismiss: () -> Unit,
    onStart: (mode: String, listId: String?, newListName: String?) -> Unit,
    listDisplayName: @Composable (WordListResponse) -> String,
) {
    val scheme = MaterialTheme.colorScheme
    var mode by remember { mutableStateOf("vocabulario") }
    var listExpanded by remember { mutableStateOf(false) }
    var selectedListId by remember {
        mutableStateOf(lists.firstOrNull { it.is_system }?.id ?: lists.firstOrNull()?.id)
    }
    var creatingNew by remember { mutableStateOf(false) }
    var newListName by remember { mutableStateOf("") }

    val canStart = if (pasteMode) {
        pasteDraft.isNotBlank() && (creatingNew && newListName.isNotBlank() || !creatingNew && selectedListId != null)
    } else {
        sourceLabel != null && (creatingNew && newListName.isNotBlank() || !creatingNew && selectedListId != null)
    }

    AppAlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(TestTags.IMPORT_START_DIALOG),
        title = stringResource(R.string.import_start_title),
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (pasteMode) {
                    AppGrayField(
                        value = pasteDraft,
                        onValueChange = onPasteDraftChange,
                        modifier = Modifier
                            .height(140.dp)
                            .testTag(TestTags.IMPORT_PASTE_INPUT),
                        placeholder = stringResource(R.string.import_paste_hint),
                        singleLine = false,
                        minLines = 5,
                        maxLines = 8,
                    )
                } else {
                    if (sourceLabel != null) {
                        Text(
                            stringResource(R.string.import_file_label, sourceLabel),
                            style = MaterialTheme.typography.labelLarge,
                            color = scheme.primary,
                        )
                    }
                    OutlinedButton(
                        onClick = onPickFile,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = AppButtonShape,
                    ) {
                        Text(
                            if (sourceLabel == null) {
                                stringResource(R.string.import_add_file)
                            } else {
                                stringResource(R.string.import_other_file)
                            },
                        )
                    }
                }

                Text(
                    stringResource(R.string.import_how),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                ModeRadio(
                    selected = mode == "vocabulario",
                    label = stringResource(R.string.import_vocab_mode),
                    tag = TestTags.IMPORT_MODE_VOCAB,
                    onClick = { mode = "vocabulario" },
                )
                ModeRadio(
                    selected = mode == "preserve",
                    label = stringResource(R.string.import_preserve_mode),
                    tag = TestTags.IMPORT_MODE_PRESERVE,
                    onClick = { mode = "preserve" },
                )

                Text(
                    stringResource(R.string.import_pick_list),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                if (creatingNew) {
                    AppGrayField(
                        value = newListName,
                        onValueChange = { newListName = it },
                        placeholder = stringResource(R.string.list_name_hint),
                        singleLine = true,
                    )
                    TextButton(onClick = { creatingNew = false; newListName = "" }) {
                        Text(stringResource(R.string.action_cancel))
                    }
                } else {
                    ExposedDropdownMenuBox(
                        expanded = listExpanded,
                        onExpandedChange = { listExpanded = it },
                        modifier = Modifier.testTag(TestTags.IMPORT_LIST_PICKER),
                    ) {
                        val selected = lists.firstOrNull { it.id == selectedListId }
                        AppGrayField(
                            value = selected?.let { listDisplayName(it) }.orEmpty(),
                            onValueChange = {},
                            readOnly = true,
                            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable),
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(listExpanded) },
                        )
                        ExposedDropdownMenu(
                            expanded = listExpanded,
                            onDismissRequest = { listExpanded = false },
                        ) {
                            lists.filterNot { it.is_pending_inbox }.forEach { list ->
                                DropdownMenuItem(
                                    text = { Text(listDisplayName(list)) },
                                    onClick = {
                                        selectedListId = list.id
                                        listExpanded = false
                                    },
                                )
                            }
                            DropdownMenuItem(
                                text = { Text(stringResource(R.string.import_new_list_option)) },
                                onClick = {
                                    listExpanded = false
                                    creatingNew = true
                                },
                            )
                        }
                    }
                }
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryModifier = Modifier.testTag(TestTags.DIALOG_CANCEL),
                primaryText = stringResource(R.string.action_ok),
                onPrimary = {
                    onStart(
                        mode,
                        if (creatingNew) null else selectedListId,
                        if (creatingNew) newListName.trim() else null,
                    )
                },
                primaryEnabled = canStart,
                primaryModifier = Modifier.testTag(TestTags.IMPORT_BTN_START),
            )
        },
    )
}

@Composable
private fun ModeRadio(
    selected: Boolean,
    label: String,
    tag: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(tag)
            .selectable(selected = selected, onClick = onClick, role = Role.RadioButton),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = onClick)
        Text(label, modifier = Modifier.padding(start = 4.dp))
    }
}
