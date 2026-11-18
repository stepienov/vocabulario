package com.vocabulario.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButton
import com.vocabulario.app.ui.components.AppDialogButtonRow

/** Logout przy niewysłanych zmianach: synchronizacja, anulowanie albo świadome odrzucenie (T-002 §5). */
@Composable
fun LogoutUnsentDialog(
    prompt: LogoutPrompt,
    onSyncAndLogout: () -> Unit,
    onAskDiscard: () -> Unit,
    onDiscard: () -> Unit,
    onCancel: () -> Unit,
) {
    if (prompt.confirmDiscard) {
        AppAlertDialog(
            onDismissRequest = onCancel,
            title = stringResource(R.string.logout_discard_confirm_title),
            text = { Text(stringResource(R.string.logout_discard_confirm_message, prompt.unsentCount)) },
            warning = true,
            buttons = {
                AppDialogButtonRow(
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = onCancel,
                    secondaryKind = AppDialogAction.Neutral,
                    primaryText = stringResource(R.string.action_discard_and_logout),
                    onPrimary = onDiscard,
                    primaryKind = AppDialogAction.Destroy,
                )
            },
        )
        return
    }
    AppAlertDialog(
        onDismissRequest = onCancel,
        title = stringResource(R.string.logout_unsent_title),
        text = {
            Column {
                val reason = when (prompt.reason) {
                    LogoutPromptReason.INITIAL -> null
                    LogoutPromptReason.SYNC_INCOMPLETE -> R.string.logout_unsent_sync_incomplete
                    LogoutPromptReason.CHANGED -> R.string.logout_unsent_changed
                }
                if (reason != null) {
                    Text(stringResource(reason), fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                }
                Text(stringResource(R.string.logout_unsent_message))
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.auth_notice_unsent, prompt.unsentCount),
                    fontWeight = FontWeight.SemiBold,
                )
            }
        },
        buttons = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AppDialogButton(
                    text = stringResource(R.string.action_sync_and_logout),
                    onClick = onSyncAndLogout,
                    kind = AppDialogAction.Confirm,
                    modifier = Modifier.fillMaxWidth(),
                )
                AppDialogButton(
                    text = stringResource(R.string.action_discard_and_logout),
                    onClick = onAskDiscard,
                    kind = AppDialogAction.CancelRed,
                    modifier = Modifier.fillMaxWidth(),
                )
                AppDialogButton(
                    text = stringResource(R.string.action_cancel),
                    onClick = onCancel,
                    kind = AppDialogAction.Neutral,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
    )
}
