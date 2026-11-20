package com.vocabulario.app.ui.sync

import android.text.format.DateUtils
import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.CloudDone
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Sync
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.sync.BlockedAction
import com.vocabulario.app.data.sync.BlockedKind
import com.vocabulario.app.data.sync.OP_PROFILE_UPDATE
import com.vocabulario.app.data.sync.ProfileBlock
import com.vocabulario.app.data.sync.SyncHeadline
import com.vocabulario.app.data.sync.canRetry
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard

@StringRes
private fun headlineRes(headline: SyncHeadline): Int = when (headline) {
    SyncHeadline.IDLE -> R.string.sync_headline_idle
    SyncHeadline.SYNCING -> R.string.sync_headline_syncing
    SyncHeadline.SYNCED -> R.string.sync_headline_synced
    SyncHeadline.SAVED_LOCALLY -> R.string.sync_headline_saved_locally
    SyncHeadline.OFFLINE -> R.string.sync_headline_offline
    SyncHeadline.OFFLINE_WITH_PENDING -> R.string.sync_headline_offline_pending
    SyncHeadline.PARTIAL -> R.string.sync_headline_partial
    SyncHeadline.SIGN_IN_REQUIRED -> R.string.sync_headline_sign_in
    SyncHeadline.VERIFICATION_REQUIRED -> R.string.sync_headline_verification
    SyncHeadline.CONSENT_REQUIRED -> R.string.sync_headline_consent
    SyncHeadline.NEEDS_ATTENTION -> R.string.sync_headline_attention
}

private fun headlineIcon(headline: SyncHeadline): ImageVector = when (headline) {
    SyncHeadline.SYNCED, SyncHeadline.IDLE -> Icons.Outlined.CloudDone
    SyncHeadline.OFFLINE, SyncHeadline.OFFLINE_WITH_PENDING -> Icons.Outlined.CloudOff
    SyncHeadline.NEEDS_ATTENTION, SyncHeadline.SIGN_IN_REQUIRED,
    SyncHeadline.VERIFICATION_REQUIRED, SyncHeadline.CONSENT_REQUIRED,
    -> Icons.Outlined.ErrorOutline
    else -> Icons.Outlined.Sync
}

@StringRes
private fun blockedTitleRes(row: BlockedRow, hasProfile: Boolean): Int {
    val item = row.item
    return when {
        item.kind == BlockedKind.REVIEW -> R.string.sync_item_review
        item.kind == BlockedKind.MOVE -> R.string.sync_item_move
        item.kind == BlockedKind.UNDO -> R.string.sync_item_undo
        item.type == OP_PROFILE_UPDATE ->
            if (hasProfile) R.string.sync_item_profile_update_for else R.string.sync_item_profile_update
        else -> R.string.sync_item_other
    }
}

/** Kody przyczyn są wewnętrzne; użytkownik widzi tylko zlokalizowane zdanie. */
@StringRes
private fun blockedReasonRes(row: BlockedRow): Int = when (row.item.reason) {
    ProfileBlock.CONFLICT, ProfileBlock.OPERATION_ID_CONFLICT -> R.string.sync_reason_conflict
    ProfileBlock.NOT_FOUND -> R.string.sync_reason_not_found
    ProfileBlock.INVALID -> R.string.sync_reason_invalid
    ProfileBlock.PAIR_EXISTS -> R.string.sync_reason_pair_exists
    else -> R.string.sync_reason_generic
}

@StringRes
private fun actionRes(action: BlockedAction): Int = when (action) {
    BlockedAction.APPLY_MINE -> R.string.sync_action_apply_mine
    BlockedAction.ACCEPT_SERVER -> R.string.sync_action_accept_server
    BlockedAction.DISCARD -> R.string.sync_action_discard
}

/** Pełna karta w ustawieniach: krótki status, liczby i pozycje wymagające decyzji. */
@Composable
fun SyncStatusCard(viewModel: SyncStatusViewModel = hiltViewModel()) {
    val ui by viewModel.state.collectAsState()
    var expanded by rememberSaveable { mutableStateOf(false) }
    val headline = stringResource(headlineRes(ui.headline))
    val showDetails = ui.queue.total > 0 || ui.blocked.isNotEmpty() || ui.lastCompleteAt != null
    val toggleLabel = stringResource(if (expanded) R.string.sync_details_hide else R.string.sync_details_show)
    AppCard(modifier = Modifier.testTag(TestTags.SYNC_CARD)) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { liveRegion = LiveRegionMode.Polite; contentDescription = headline }
                    .let { if (showDetails) it.clickable(onClickLabel = toggleLabel) { expanded = !expanded } else it },
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusIcon(ui.headline)
                Text(
                    headline,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (showDetails) {
                    Icon(
                        if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = null,
                    )
                }
            }
            if (expanded) {
                SyncDetails(ui)
            }
            ui.notice?.let {
                Text(
                    stringResource(R.string.sync_notice_needs_network),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            if (ui.headline.canRetry()) {
                OutlinedButton(
                    onClick = viewModel::retry,
                    shape = AppButtonShape,
                    modifier = Modifier.fillMaxWidth().testTag(TestTags.SYNC_RETRY),
                ) { Text(stringResource(R.string.sync_action_retry)) }
            }
            if (ui.blocked.isNotEmpty()) {
                Text(
                    stringResource(R.string.sync_blocked_title),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                ui.blocked.forEach { row -> BlockedRowView(row) { viewModel.act(row, it) } }
            }
        }
    }
}

@Composable
private fun StatusIcon(headline: SyncHeadline) {
    if (headline == SyncHeadline.SYNCING) {
        CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
    } else {
        Icon(
            headlineIcon(headline),
            contentDescription = null,
            modifier = Modifier.size(22.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SyncDetails(ui: SyncStatusUi) {
    val context = LocalContext.current
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        val muted = MaterialTheme.colorScheme.onSurfaceVariant
        if (ui.queue.waiting > 0) {
            Text(stringResource(R.string.sync_detail_waiting, ui.queue.waiting), style = MaterialTheme.typography.bodySmall, color = muted)
        }
        if (ui.queue.blocked > 0) {
            Text(stringResource(R.string.sync_detail_blocked, ui.queue.blocked), style = MaterialTheme.typography.bodySmall, color = muted)
        }
        if (ui.queue.lookupsNeedsReview > 0) {
            Text(stringResource(R.string.sync_detail_needs_review, ui.queue.lookupsNeedsReview), style = MaterialTheme.typography.bodySmall, color = muted)
        }
        ui.lastCompleteAt?.let { at ->
            val text = DateUtils.formatDateTime(
                context,
                at,
                DateUtils.FORMAT_SHOW_DATE or DateUtils.FORMAT_SHOW_TIME or DateUtils.FORMAT_ABBREV_MONTH,
            )
            Text(stringResource(R.string.sync_detail_last_complete, text), style = MaterialTheme.typography.bodySmall, color = muted)
        }
    }
}

@Composable
private fun BlockedRowView(row: BlockedRow, onAction: (BlockedAction) -> Unit) {
    Surface(
        shape = AppButtonShape,
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                stringResource(blockedTitleRes(row, row.profileLabel != null), row.profileLabel.orEmpty()),
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                stringResource(blockedReasonRes(row)),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                row.actions.forEach { action ->
                    TextButton(onClick = { onAction(action) }) { Text(stringResource(actionRes(action))) }
                }
            }
        }
    }
}

/** Jedna linia na ekranie głównym; pojawia się tylko, gdy coś czeka lub wymaga uwagi. */
@Composable
fun SyncStatusLine(onOpen: () -> Unit, viewModel: SyncStatusViewModel = hiltViewModel()) {
    val ui by viewModel.state.collectAsState()
    val quiet = ui.headline == SyncHeadline.IDLE || ui.headline == SyncHeadline.SYNCED ||
        ui.headline == SyncHeadline.OFFLINE
    if (quiet) return
    val text = stringResource(headlineRes(ui.headline))
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(TestTags.SYNC_LINE)
            .semantics { liveRegion = LiveRegionMode.Polite }
            .clickable(onClick = onOpen),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            StatusIcon(ui.headline)
            Text(text, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        }
    }
}
