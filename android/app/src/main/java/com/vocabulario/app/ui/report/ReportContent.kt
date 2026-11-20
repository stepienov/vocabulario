package com.vocabulario.app.ui.report

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.api.ReportLimits
import com.vocabulario.app.data.api.ReportReason
import com.vocabulario.app.data.publicSiteUrl
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField

/** Przycisk „Zgłoś treść” (min. 48 dp); sam dialog otwiera się z wyboru powodu. */
@Composable
fun ReportContentButton(target: ReportTarget, modifier: Modifier = Modifier) {
    var open by remember { mutableStateOf(false) }
    IconButton(
        onClick = { open = true },
        modifier = modifier.size(48.dp).testTag(TestTags.REPORT_BUTTON),
    ) {
        Icon(Icons.Outlined.Flag, contentDescription = stringResource(R.string.report_action))
    }
    if (open) ReportContentDialog(target = target, onDismiss = { open = false })
}

@Composable
fun ReportContentDialog(
    target: ReportTarget,
    onDismiss: () -> Unit,
    viewModel: ContentReportViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val phase = state.phase
    val finished = phase is ReportPhase.Sent || phase is ReportPhase.Rejected
    val sending = phase == ReportPhase.Sending
    val queued = phase as? ReportPhase.Queued
    val scheme = MaterialTheme.colorScheme

    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.report_title),
        text = {
            Column(
                modifier = Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                when {
                    phase is ReportPhase.Sent -> Text(
                        stringResource(
                            if (phase.status == "resolved") R.string.report_resolved else R.string.report_sent,
                        ),
                    )
                    phase is ReportPhase.Rejected -> Text(stringResource(R.string.report_rejected))
                    queued != null -> Text(stringResource(R.string.report_queued))
                    else -> {
                        ReportReason.all.forEach { reason ->
                            ReasonRow(
                                label = stringResource(reasonLabel(reason)),
                                selected = state.reason == reason,
                                enabled = !sending,
                                onSelect = { viewModel.setReason(reason) },
                            )
                        }
                        Text(
                            stringResource(R.string.report_preview_label),
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.onSurfaceVariant,
                        )
                        Text(
                            target.excerpt.trim().take(ReportLimits.EXCERPT_MAX),
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 6,
                        )
                        AppGrayField(
                            value = state.note,
                            onValueChange = viewModel::setNote,
                            modifier = Modifier.testTag(TestTags.REPORT_NOTE),
                            enabled = !sending,
                            singleLine = false,
                            minLines = 2,
                            maxLines = 4,
                            placeholder = stringResource(R.string.report_note_label),
                        )
                        Text(
                            stringResource(R.string.report_warning),
                            style = MaterialTheme.typography.bodySmall,
                            color = scheme.onSurfaceVariant,
                        )
                        if (state.failed) {
                            Text(
                                stringResource(R.string.report_failed),
                                style = MaterialTheme.typography.bodySmall,
                                color = scheme.error,
                            )
                        }
                    }
                }
            }
        },
        buttons = {
            when {
                finished -> AppDialogButtonRow(
                    primaryText = stringResource(R.string.action_close),
                    onPrimary = onDismiss,
                )
                queued != null -> AppDialogButtonRow(
                    secondaryText = stringResource(R.string.report_discard),
                    onSecondary = viewModel::discardQueued,
                    secondaryModifier = Modifier.testTag(TestTags.REPORT_DISCARD),
                    primaryText = stringResource(R.string.action_retry),
                    onPrimary = viewModel::retry,
                )
                else -> AppDialogButtonRow(
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = onDismiss,
                    secondaryKind = AppDialogAction.Neutral,
                    primaryText = stringResource(R.string.report_send),
                    onPrimary = { viewModel.submit(target) },
                    primaryEnabled = !sending && target.excerpt.isNotBlank(),
                    primaryModifier = Modifier.testTag(TestTags.REPORT_SEND),
                )
            }
        },
    )
}

private fun reasonLabel(reason: String): Int = when (reason) {
    ReportReason.INCORRECT -> R.string.report_reason_incorrect
    ReportReason.OFFENSIVE -> R.string.report_reason_offensive
    ReportReason.PRIVACY -> R.string.report_reason_privacy
    else -> R.string.report_reason_other
}

@Composable
private fun ReasonRow(label: String, selected: Boolean, enabled: Boolean, onSelect: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, enabled = enabled)
        Text(label, modifier = Modifier.padding(start = 12.dp), style = MaterialTheme.typography.bodyMedium)
    }
}

/** „Pomoc i kontakt”: kopiowalny adres wsparcia i link do strony publicznej; bez wysyłania danych. */
@Composable
fun SupportHelpDialog(
    onDismiss: () -> Unit,
    viewModel: SupportViewModel = hiltViewModel(),
) {
    val email by viewModel.email.collectAsState()
    val clipboard = LocalClipboardManager.current
    val uriHandler = LocalUriHandler.current
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.support_title),
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                val address = email
                if (address == null) {
                    Text(stringResource(R.string.support_no_email), style = MaterialTheme.typography.bodyMedium)
                } else {
                    Text(
                        stringResource(R.string.support_email_label),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(address, style = MaterialTheme.typography.bodyLarge)
                    AppDialogButtonRow(
                        primaryText = stringResource(R.string.support_copy),
                        onPrimary = { clipboard.setText(AnnotatedString(address)) },
                        primaryKind = AppDialogAction.ConfirmOutlined,
                        primaryModifier = Modifier.testTag(TestTags.SUPPORT_COPY),
                    )
                }
                Spacer(Modifier.height(2.dp))
                AppDialogButtonRow(
                    primaryText = stringResource(R.string.support_open_site),
                    onPrimary = { uriHandler.openUri(publicSiteUrl(ApiBaseUrl.resolve(), "/support")) },
                    primaryKind = AppDialogAction.ConfirmOutlined,
                )
            }
        },
        buttons = {
            AppDialogButtonRow(primaryText = stringResource(R.string.action_close), onPrimary = onDismiss)
        },
    )
}
