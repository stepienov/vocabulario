package com.vocabulario.app.ui.card

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.CardCorrectionResponse
import com.vocabulario.app.data.api.CardHistoryEventResponse
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogWindowChrome
import com.vocabulario.app.ui.components.AppGrayField
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Orange accent for correction / self-edit processing (distinct from enrichment blue). */
val CorrectionActivityColor @Composable get() = Color(0xFFE65100)

data class CorrectionSection(val id: String, val labelRes: Int)

val correctionSections = listOf(
    CorrectionSection("lemma", R.string.correction_section_lemma),
    CorrectionSection("pos", R.string.correction_section_pos),
    CorrectionSection("gloss", R.string.correction_section_gloss),
    CorrectionSection("meanings", R.string.correction_section_meanings),
    CorrectionSection("examples", R.string.correction_section_examples),
    CorrectionSection("conjugation", R.string.correction_section_conjugation),
    CorrectionSection("similar", R.string.correction_section_similar),
    CorrectionSection("pronunciation", R.string.correction_section_pronunciation),
    CorrectionSection("other", R.string.correction_section_other),
)

@Composable
fun correctionResultMessage(resultCode: String?): String {
    val res = when (resultCode) {
        "correction_accepted" -> R.string.correction_code_accepted
        "correction_unfounded" -> R.string.correction_code_unfounded
        "correction_insufficient_info" -> R.string.correction_code_insufficient
        "correction_not_applicable" -> R.string.correction_code_not_applicable
        "correction_processing_failed" -> R.string.correction_code_failed
        else -> R.string.correction_code_unfounded
    }
    return stringResource(res)
}

@Composable
fun cardActivityStatusLabel(status: String?): String? = when (status) {
    "correction_processing" -> stringResource(R.string.correction_processing)
    "self_edit_processing" -> stringResource(R.string.self_edit_processing)
    else -> null
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun CardCorrectionReportSheet(
    visible: Boolean,
    submitting: Boolean,
    quotaRemaining: Int?,
    onDismiss: () -> Unit,
    onSubmit: (sections: List<String>, note: String) -> Unit,
    onSelfEdit: () -> Unit,
) {
    if (!visible) return
    var selected by remember { mutableStateOf(setOf<String>()) }
    var note by remember { mutableStateOf("") }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val quotaBlocked = quotaRemaining != null && quotaRemaining <= 0

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        AppDialogWindowChrome()
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
                .verticalScroll(rememberScrollState())
                .testTag(TestTags.SHEET_CORRECTION_REPORT),
        ) {
            Text(
                stringResource(R.string.correction_report_title),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                stringResource(R.string.correction_report_subtitle),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(10.dp))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                correctionSections.forEach { section ->
                    FilterChip(
                        selected = section.id in selected,
                        onClick = {
                            selected = if (section.id in selected) {
                                selected - section.id
                            } else {
                                selected + section.id
                            }
                        },
                        label = {
                            Text(
                                stringResource(section.labelRes),
                                style = MaterialTheme.typography.labelSmall,
                            )
                        },
                        modifier = Modifier.testTag("${TestTags.CORRECTION_SECTION_PREFIX}${section.id}"),
                        colors = FilterChipDefaults.filterChipColors(),
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
            AppGrayField(
                value = note,
                onValueChange = { note = it },
                modifier = Modifier.testTag(TestTags.CORRECTION_NOTE),
                placeholder = stringResource(R.string.correction_note_hint),
                singleLine = false,
                minLines = 3,
                maxLines = 6,
            )
            if (quotaBlocked) {
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.correction_daily_limit),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Spacer(Modifier.height(14.dp))
            Button(
                onClick = { onSubmit(selected.toList(), note.trim()) },
                enabled = !submitting && !quotaBlocked,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 48.dp)
                    .testTag(TestTags.BTN_CORRECTION_SUBMIT),
                shape = AppButtonShape,
            ) {
                if (submitting) {
                    CircularProgressIndicator(modifier = Modifier.size(22.dp))
                } else {
                    Text(stringResource(R.string.correction_submit))
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(
                stringResource(R.string.correction_self_edit_link),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onSelfEdit)
                    .padding(vertical = 4.dp)
                    .testTag(TestTags.BTN_CORRECTION_SELF_EDIT_LINK),
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
fun CardCorrectionResultDialog(
    correction: CardCorrectionResponse?,
    cardLemma: String,
    onDismiss: () -> Unit,
    onEditSelf: () -> Unit,
) {
    val item = correction ?: return
    if (item.status == "reported") return
    val accepted = item.status == "accepted"
    val scheme = MaterialTheme.colorScheme
    CardBlockingAlertDialog(
        onDismissRequest = {},
        title = {
            Text(
                stringResource(
                    if (accepted) R.string.correction_result_accepted_title
                    else R.string.correction_result_rejected_title,
                ),
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    cardLemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = scheme.onSurface,
                )
                Text(
                    stringResource(
                        if (accepted) R.string.correction_result_accepted_body
                        else R.string.correction_result_rejected_body,
                        cardLemma,
                        correctionResultMessage(item.result_code),
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        },
        buttons = {
            if (accepted) {
                CardDialogButtonRow(
                    primaryText = stringResource(R.string.action_ok),
                    onPrimary = onDismiss,
                    primaryModifier = Modifier.testTag(TestTags.BTN_CORRECTION_OK),
                )
            } else {
                CardDialogButtonRow(
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = onDismiss,
                    primaryText = stringResource(R.string.correction_edit_self),
                    onPrimary = onEditSelf,
                    primaryKind = AppDialogAction.Teal,
                    primaryModifier = Modifier.testTag(TestTags.BTN_CORRECTION_EDIT_SELF),
                )
            }
        },
        modifier = Modifier.testTag(TestTags.DIALOG_CORRECTION_RESULT),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CardHistorySheet(
    visible: Boolean,
    loading: Boolean,
    restoring: Boolean,
    events: List<CardHistoryEventResponse>,
    onDismiss: () -> Unit,
    onRestore: (eventId: String) -> Unit,
) {
    if (!visible) return
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val formatter = remember {
        DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.getDefault())
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        modifier = Modifier.testTag(TestTags.SHEET_CARD_HISTORY),
    ) {
        AppDialogWindowChrome()
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Text(
                stringResource(R.string.card_history_title),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(12.dp))
            when {
                loading -> {
                    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = CorrectionActivityColor)
                    }
                }
                events.isEmpty() -> {
                    Text(
                        stringResource(R.string.card_history_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                else -> {
                    events.forEachIndexed { index, event ->
                        if (index > 0) {
                            HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                        }
                        val whenText = runCatching {
                            formatter.format(
                                Instant.parse(event.created_at).atZone(ZoneId.systemDefault()),
                            )
                        }.getOrElse { event.created_at }
                        val actorLabel = when (event.actor) {
                            "system" -> stringResource(R.string.card_history_actor_system)
                            else -> stringResource(R.string.card_history_actor_you)
                        }
                        Text(
                            "$whenText — $actorLabel",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            historyEventTitle(event),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                        )
                        historyEventSummary(event)?.let { summary ->
                            Spacer(Modifier.height(4.dp))
                            Text(summary, style = MaterialTheme.typography.bodySmall)
                        }
                        if (event.can_restore) {
                            Spacer(Modifier.height(8.dp))
                            TextButton(
                                onClick = { onRestore(event.id) },
                                enabled = !restoring,
                                modifier = Modifier.testTag(TestTags.BTN_CARD_HISTORY_RESTORE),
                            ) {
                                Text(stringResource(R.string.card_history_restore))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun historyEventTitle(event: CardHistoryEventResponse): String = when (event.event_type) {
    "correction_submitted" -> stringResource(R.string.card_history_event_report)
    "correction_accepted" -> stringResource(R.string.card_history_event_accepted)
    "correction_rejected" -> correctionResultMessage(event.result_code)
    "self_edit_applied" -> stringResource(R.string.card_history_event_self_edit)
    "self_edit_reviewed" -> stringResource(R.string.card_history_event_reviewed)
    "restored_to_original" -> stringResource(R.string.card_history_restored)
    else -> event.event_type
}

@Composable
fun CardActivitySpinner(
    modifier: Modifier = Modifier,
    color: Color = CorrectionActivityColor,
) {
    CircularProgressIndicator(
        modifier = modifier.size(22.dp),
        strokeWidth = 2.5.dp,
        color = color,
    )
}
