package com.vocabulario.app.ui.auth

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
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
import com.vocabulario.app.ui.components.AppDialogButtonRow

@Composable
fun LogoutUnsentDialog(
    prompt: LogoutPrompt,
    onSyncAndLogout: () -> Unit,
    onCancel: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onCancel,
        title = stringResource(R.string.logout_unsent_title),
        text = {
            Column {
                val reason = when (prompt.reason) {
                    LogoutPromptReason.INITIAL -> null
                    LogoutPromptReason.SYNC_INCOMPLETE -> R.string.logout_unsent_sync_incomplete
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
            AppDialogButtonRow(
                primaryText = stringResource(R.string.action_sync_and_logout),
                onPrimary = onSyncAndLogout,
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onCancel,
                secondaryKind = AppDialogAction.Neutral,
            )
        },
    )
}
