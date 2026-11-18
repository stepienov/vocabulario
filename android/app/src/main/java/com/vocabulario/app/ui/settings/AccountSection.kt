package com.vocabulario.app.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField

@Composable
internal fun AccountSectionBody(
    account: AccountUiState,
    onChangePassword: () -> Unit,
    onSendReset: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        if (account.email == null) {
            Text(
                stringResource(if (account.unavailable) R.string.account_unavailable else R.string.account_loading),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
            return@Column
        }
        Text(account.email, style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(4.dp))
        Text(
            stringResource(if (account.emailVerified) R.string.account_email_verified else R.string.account_email_unverified),
            style = MaterialTheme.typography.bodySmall,
            color = if (account.emailVerified) scheme.onSurfaceVariant else scheme.error,
        )
        if (account.hasGoogle) {
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(R.string.account_google_linked),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
        }
        if (account.hasPassword && account.passwordUpgradeRequired) {
            Spacer(Modifier.height(12.dp))
            Text(
                stringResource(R.string.account_password_reset_needed),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onSendReset,
                enabled = !account.resetSending,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.account_password_reset_send)) }
        } else if (account.hasPassword) {
            Spacer(Modifier.height(12.dp))
            OutlinedButton(
                onClick = onChangePassword,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.account_change_password)) }
        }
    }
}

@Composable
internal fun ChangePasswordDialog(
    form: ChangePasswordUiState,
    onCurrentChange: (String) -> Unit,
    onNewChange: (String) -> Unit,
    onRepeatChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    val passwordKeyboard = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Next)
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.account_change_password),
        dismissOnClickOutside = !form.busy,
        text = {
            Column {
                AppGrayField(
                    value = form.current,
                    onValueChange = onCurrentChange,
                    placeholder = stringResource(R.string.account_current_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = passwordKeyboard,
                )
                Spacer(Modifier.height(10.dp))
                AppGrayField(
                    value = form.new,
                    onValueChange = onNewChange,
                    placeholder = stringResource(R.string.account_new_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = passwordKeyboard,
                )
                Spacer(Modifier.height(10.dp))
                AppGrayField(
                    value = form.repeat,
                    onValueChange = onRepeatChange,
                    placeholder = stringResource(R.string.account_repeat_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = passwordKeyboard.copy(imeAction = ImeAction.Done),
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.account_new_password_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                form.error?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.Neutral,
                primaryText = stringResource(R.string.action_save),
                onPrimary = onSubmit,
                primaryEnabled = !form.busy,
            )
        },
    )
}
