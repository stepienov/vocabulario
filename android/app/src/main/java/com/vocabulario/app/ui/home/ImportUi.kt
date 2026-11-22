package com.vocabulario.app.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import com.vocabulario.app.R
import com.vocabulario.app.data.api.ImportJobItemResponse
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.imports.ImportJobState
import com.vocabulario.app.data.imports.ImportResult
import com.vocabulario.app.data.imports.ImportStatus
import com.vocabulario.app.data.imports.isPasteImportSource
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.AppToggle
import com.vocabulario.app.ui.theme.LocalVocabExtraColors

@Composable
fun ImportStatusPanel(
    state: ImportJobState,
    onAbort: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val source = localizedImportSource(state.sourceName).orEmpty()
    val writing = state.status == ImportStatus.Committing || state.stage == "write"
    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag(TestTags.IMPORT_STATUS_PANEL)
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(color = scheme.primary, strokeWidth = 3.dp)
        Spacer(Modifier.height(16.dp))
        Text(
            text = if (writing) {
                stringResource(R.string.import_stage_write)
            } else {
                stringResource(R.string.import_analyzing)
            },
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            color = scheme.onSurface,
        )
        Spacer(Modifier.height(12.dp))
        if (!writing) {
            Text(
                stringResource(R.string.import_analysis_description),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(12.dp))
        }
        if (source.isNotBlank()) {
            Surface(shape = AppButtonShape, color = scheme.primaryContainer) {
                Text(source, modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.labelMedium, color = scheme.onSurface)
            }
        }
        Spacer(Modifier.height(16.dp))
        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))
        Text(stringResource(R.string.import_analysis_wait), style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant)
        state.notice?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = scheme.error, textAlign = TextAlign.Center)
        }
        Spacer(Modifier.height(20.dp))
        OutlinedButton(
            onClick = onAbort,
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp)
                .testTag(TestTags.IMPORT_BTN_ABORT),
            shape = AppButtonShape,
        ) {
            Text(stringResource(R.string.action_cancel), fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun localizedImportSource(raw: String?): String? {
    if (raw.isNullOrBlank()) return null
    if (isPasteImportSource(raw)) return stringResource(R.string.import_paste_source)
    return raw
}

@Composable
private fun importStageTitle(stage: String, status: ImportStatus): String = when {
    status == ImportStatus.Cancelling || stage == "rollback" ->
        stringResource(R.string.import_stage_rollback)
    stage == "queued" -> stringResource(R.string.import_stage_queued)
    stage == "format" -> stringResource(R.string.import_stage_format)
    stage == "classify" -> stringResource(R.string.import_stage_classify)
    stage == "layout" -> stringResource(R.string.import_stage_layout)
    stage == "dedup" -> stringResource(R.string.import_stage_dedup)
    stage == "write" -> stringResource(R.string.import_stage_write)
    else -> stringResource(R.string.import_progress)
}

@Composable
fun ImportAbortConfirmDialog(
    fromReview: Boolean,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    DestroyConfirmDialog(
        visible = true,
        title = stringResource(
            if (fromReview) R.string.import_discard_title else R.string.import_abort_title,
        ),
        confirmText = stringResource(
            if (fromReview) R.string.action_ok else R.string.action_abort,
        ),
        onDismiss = onDismiss,
        onConfirm = onConfirm,
        confirmTag = TestTags.DIALOG_CONFIRM,
        cancelTag = TestTags.DIALOG_CANCEL,
        dialogTag = TestTags.IMPORT_ABORT_CONFIRM,
    )
}

@Composable
fun ImportReviewAccordion(
    state: ImportJobState,
    onExpand: (String?) -> Unit,
    onAbort: () -> Unit,
    onCommit: () -> Unit,
    onToggleReady: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.weight(1f).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(stringResource(R.string.import_analysis_result), style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold)
            state.targetListName?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant) }
            ImportStats(
                listOf(
                    (state.readyCount + state.duplicateCount + state.failedCount) to R.string.import_stat_all,
                    state.readyCount to R.string.import_stat_ready,
                    state.duplicateCount to R.string.import_stat_duplicate,
                    state.failedCount to R.string.import_stat_check,
                ),
            )
            state.notice?.let { Text(it, color = scheme.onSurfaceVariant) }
            if (state.readyItems.isNotEmpty()) {
                Surface(shape = RoundedCornerShape(10.dp), color = scheme.surface) {
                    Column(Modifier.fillMaxWidth().padding(12.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(stringResource(R.string.import_review_select), fontWeight = FontWeight.SemiBold)
                            Text("${state.selectedReadyCount} / ${state.readyCount}", color = scheme.onSurfaceVariant)
                        }
                        state.readyItems.forEach { item ->
                            ReadyImportItemRow(item, item.id in state.selectedItemIds) { onToggleReady(item.id) }
                        }
                    }
                }
            } else if (state.readyCount > 0) {
                Text(stringResource(R.string.import_review_loading), style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurfaceVariant)
            }
            if (state.selectedReadyCount > state.dailyRemaining) {
                Text(stringResource(R.string.import_quota_exceeded), color = scheme.error)
            }
            ImportReviewSection(
                title = "${stringResource(R.string.import_stat_check)} (${state.failedCount})",
                tag = TestTags.IMPORT_ACCORDION_FAIL,
                expanded = state.expandedSection == "failed",
                onClick = { onExpand("failed") },
                items = state.failedItems,
                clipboard = state.errorClipboard,
                clipboardCount = state.errorClipboardCount,
            )
            ImportReviewSection(
                title = stringResource(R.string.import_section_duplicates, state.duplicateCount),
                tag = TestTags.IMPORT_ACCORDION_DUP,
                expanded = state.expandedSection == "duplicate",
                onClick = { onExpand("duplicate") },
                items = state.duplicateItems,
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            OutlinedButton(
                onClick = onAbort,
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .testTag(TestTags.BTN_IMPORT_CANCEL),
                shape = AppButtonShape,
            ) {
                Text(stringResource(R.string.import_abandon))
            }
            Button(
                onClick = onCommit,
                enabled = state.canConfirmSelected,
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp)
                    .testTag(TestTags.BTN_IMPORT_CONFIRM),
                shape = AppButtonShape,
            ) {
                Text(stringResource(R.string.action_add) + " ${state.selectedReadyCount}")
            }
        }
    }
}

@Composable
private fun ImportStats(stats: List<Pair<Int, Int>>) {
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = if (stats.size > 2 && maxWidth.value / LocalDensity.current.fontScale < 300f) 2 else stats.size
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            stats.chunked(columns).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    row.forEach { (count, label) ->
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(Modifier.padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("$count", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                Text(stringResource(label), style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ImportReviewSection(
    title: String,
    tag: String,
    expanded: Boolean,
    onClick: () -> Unit,
    items: List<ImportJobItemResponse>,
    clipboard: String = "",
    clipboardCount: Int = 0,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(shape = RoundedCornerShape(10.dp), color = scheme.surface) {
        Column(Modifier.fillMaxWidth().padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().testTag(tag).clickable(onClick = onClick).heightIn(min = 40.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                Text(if (expanded) "⌃" else "⌄", color = scheme.onSurfaceVariant)
            }
            if (expanded) {
                if (clipboard.isNotBlank()) {
                    Text(stringResource(R.string.import_errors_hint), style = MaterialTheme.typography.bodySmall,
                        color = scheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 8.dp))
                }
                items.forEach {
                    HorizontalDivider(color = scheme.outlineVariant)
                    ImportJobItemRow(it)
                }
                if (clipboard.isNotBlank()) ImportCopyButton(clipboard, clipboardCount)
            }
        }
    }
}

@Composable
private fun ImportCopyButton(text: String, count: Int) {
    val clipboard = LocalClipboardManager.current
    var copied by remember(text) { mutableStateOf(false) }
    TextButton(
        onClick = {
            clipboard.setText(AnnotatedString(text))
            copied = true
        },
        modifier = Modifier.testTag(TestTags.IMPORT_COPY_ERRORS),
        contentPadding = PaddingValues(0.dp),
    ) {
        Text(stringResource(R.string.import_copy_check, count))
        if (copied) {
            Spacer(Modifier.size(6.dp))
            Icon(Icons.Default.Check, contentDescription = stringResource(R.string.import_copy_done),
                modifier = Modifier.size(18.dp))
        }
    }
}

@Composable
private fun ReadyImportItemRow(
    item: ImportJobItemResponse,
    checked: Boolean,
    onToggle: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val word = item.lemma?.takeIf { it.isNotBlank() }
        ?: item.input_label.takeIf { it.isNotBlank() }
        ?: stringResource(R.string.import_item_untitled)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .toggleable(value = checked, role = Role.Switch, onValueChange = { onToggle() })
            .heightIn(min = 48.dp)
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        AppToggle(
            checked = checked,
            onCheckedChange = null,
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                word,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = LocalVocabExtraColors.current.importLemma,
            )
            item.gloss?.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun ImportJobItemRow(item: ImportJobItemResponse) {
    val scheme = MaterialTheme.colorScheme
    val untitled = stringResource(R.string.import_item_untitled)
    val word = when (item.verdict) {
        "failed", "duplicate" -> item.input_label.takeIf { it.isNotBlank() }
            ?: item.lemma?.takeIf { it.isNotBlank() }
            ?: untitled
        else -> item.lemma?.takeIf { it.isNotBlank() }
            ?: item.input_label.takeIf { it.isNotBlank() }
            ?: untitled
    }
    val detail = when (item.verdict) {
        "failed" -> reasonLabel(item.reason_code)
        "duplicate" -> item.list_name?.takeIf { it.isNotBlank() }
            ?: if (item.reason_code == "in_file_duplicate") {
                null
            } else {
                reasonLabel(item.reason_code)
            }
        else -> item.gloss?.takeIf { it.isNotBlank() }
    }
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
        Text(
            word,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            color = scheme.onSurface,
        )
        if (!detail.isNullOrBlank()) {
            Spacer(Modifier.height(3.dp))
            Text(
                detail,
                style = MaterialTheme.typography.bodySmall,
                color = scheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun reasonLabel(code: String?): String = when (code) {
    "already_on_list" -> stringResource(R.string.import_reason_already_on_list)
    "in_file_duplicate" -> stringResource(R.string.import_reason_in_file_duplicate)
    "no_lemma" -> stringResource(R.string.import_reason_no_lemma)
    "llm_invalid" -> stringResource(R.string.import_reason_llm_invalid)
    "not_learning_lang" -> stringResource(R.string.import_reason_not_learning_lang)
    "write_failed" -> stringResource(R.string.import_reason_write_failed)
    "deselected" -> stringResource(R.string.import_reason_unknown)
    else -> stringResource(R.string.import_reason_unknown)
}

@Composable
fun ImportOutcomePanel(
    state: ImportJobState,
    onOk: () -> Unit,
    onShowList: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val created = state.result?.created ?: state.createdCount
    val duplicates = state.result?.duplicates ?: state.duplicateCount
    val failed = state.result?.failed ?: state.failedCount
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        color = scheme.surface,
        contentColor = scheme.onSurface,
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Column(
                modifier = Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (state.status == ImportStatus.Done) {
                    Surface(shape = AppButtonShape, color = scheme.tertiaryContainer) {
                        Icon(
                            Icons.Default.Check,
                            contentDescription = null,
                            modifier = Modifier.padding(10.dp).size(24.dp),
                            tint = scheme.onSurface,
                        )
                    }
                }
                Text(
                    when (state.status) {
                        ImportStatus.Cancelled -> stringResource(R.string.import_cancelled)
                        ImportStatus.Failed, ImportStatus.Error ->
                            state.error ?: stringResource(R.string.import_result_title)
                        else -> stringResource(R.string.import_done)
                    },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                if (state.status == ImportStatus.Done) {
                    state.targetListName?.let { listName ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Text("${stringResource(R.string.list_fallback)}:", color = scheme.onSurfaceVariant)
                            Surface(shape = AppButtonShape, color = scheme.primaryContainer) {
                                Text(
                                    listName,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                                    style = MaterialTheme.typography.labelMedium,
                                )
                            }
                        }
                    }
                    ImportStats(listOf(created to R.string.import_stat_added, state.skippedCount to R.string.import_stat_skipped))
                    ImportStats(listOf(duplicates to R.string.import_stat_duplicate, failed to R.string.import_stat_check))
                } else if (created + duplicates + failed > 0) {
                    Text(
                        if (failed > 0) {
                            stringResource(
                                R.string.import_result_body_failed,
                                created,
                                duplicates,
                                failed,
                            )
                        } else {
                            stringResource(
                                R.string.import_result_body,
                                created,
                                duplicates,
                            )
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = scheme.onSurface,
                    )
                }
                if (state.failedItems.isNotEmpty() && state.errorClipboard.isNotBlank()) {
                    HorizontalDivider(color = scheme.outlineVariant)
                    ImportCopyButton(state.errorClipboard, state.errorClipboardCount)
                }
                state.notice?.let { Text(it, color = scheme.onSurfaceVariant) }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            ) {
                if (state.status == ImportStatus.Done && !state.targetListId.isNullOrBlank()) {
                    OutlinedButton(
                        onClick = onShowList,
                        modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                        shape = AppButtonShape,
                    ) {
                        Text(stringResource(R.string.action_show_list))
                    }
                }
                Button(
                    onClick = onOk,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 48.dp)
                        .testTag(TestTags.IMPORT_RESULT_OK),
                    shape = AppButtonShape,
                ) {
                    Text(stringResource(R.string.action_ok))
                }
            }
        }
    }
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImportStartDialog(
    lists: List<WordListResponse>,
    sourceLabel: String?,
    pasteDraft: String,
    onPasteDraftChange: (String) -> Unit,
    onPickFile: () -> Unit,
    onClearFile: () -> Unit,
    onDismiss: () -> Unit,
    onStart: (listId: String?, newListName: String?) -> Unit,
    listDisplayName: @Composable (WordListResponse) -> String,
) {
    val scheme = MaterialTheme.colorScheme
    var listExpanded by remember { mutableStateOf(false) }
    var selectedListId by remember {
        mutableStateOf(lists.firstOrNull { it.is_system }?.id ?: lists.firstOrNull()?.id)
    }
    var creatingNew by remember { mutableStateOf(false) }
    var newListName by remember { mutableStateOf("") }
    var showPasteInfo by remember { mutableStateOf(false) }

    val hasFile = sourceLabel != null
    val hasPaste = pasteDraft.isNotBlank()
    val listReady = creatingNew && newListName.isNotBlank() || !creatingNew && selectedListId != null
    val canStart = (hasFile || hasPaste) && listReady

    AppAlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(TestTags.IMPORT_START_DIALOG),
        titleContent = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.import_paste), style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold)
                IconButton(onClick = { showPasteInfo = true }) {
                    Icon(Icons.Outlined.Info, contentDescription = stringResource(R.string.import_info_title),
                        tint = scheme.onSurfaceVariant)
                }
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                AppGrayField(
                    value = pasteDraft,
                    onValueChange = onPasteDraftChange,
                    modifier = Modifier
                        .height(140.dp)
                        .testTag(TestTags.IMPORT_PASTE_INPUT),
                    enabled = !hasFile,
                    singleLine = false,
                    minLines = 5,
                    maxLines = 8,
                )
                if (sourceLabel != null) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            stringResource(R.string.import_file_label, sourceLabel),
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.labelLarge,
                            color = scheme.primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        IconButton(
                            onClick = onClearFile,
                            modifier = Modifier.size(40.dp),
                        ) {
                            Icon(
                                Icons.Default.Close,
                                contentDescription = stringResource(R.string.action_cancel),
                                tint = scheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                OutlinedButton(
                    onClick = onPickFile,
                    enabled = !hasPaste,
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
                primaryText = stringResource(R.string.import_action_start),
                onPrimary = {
                    onStart(
                        if (creatingNew) null else selectedListId,
                        if (creatingNew) newListName.trim() else null,
                    )
                },
                primaryEnabled = canStart,
                primaryModifier = Modifier.testTag(TestTags.IMPORT_BTN_START),
            )
        },
    )
    if (showPasteInfo) {
        AppAlertDialog(
            onDismissRequest = { showPasteInfo = false },
            title = stringResource(R.string.import_info_title),
            text = { Text(stringResource(R.string.import_paste_info)) },
            buttons = {
                AppDialogButtonRow(
                    primaryText = stringResource(R.string.action_ok),
                    onPrimary = { showPasteInfo = false },
                    primaryKind = AppDialogAction.Neutral,
                )
            },
        )
    }
}

