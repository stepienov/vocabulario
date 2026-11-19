package com.vocabulario.app.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
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
    onChangeEmail: () -> Unit,
    onResendChange: () -> Unit,
    onCancelChange: () -> Unit,
    onDeleteAccount: () -> Unit,
    onRetry: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        if (account.email == null) {
            Text(
                stringResource(if (account.unavailable) R.string.account_unavailable else R.string.account_loading),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
            )
            if (account.unavailable) {
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.fillMaxWidth(),
                    shape = AppButtonShape,
                ) { Text(stringResource(R.string.action_retry)) }
            }
            return@Column
        }
        Text(account.email, style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(4.dp))
        Text(
            stringResource(if (account.emailVerified) R.string.account_email_verified else R.string.account_email_unverified),
            style = MaterialTheme.typography.bodySmall,
            color = if (account.emailVerified) scheme.onSurfaceVariant else scheme.error,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            stringResource(R.string.account_profiles_note),
            style = MaterialTheme.typography.bodySmall,
            color = scheme.onSurfaceVariant,
        )
        if (account.stale) {
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(R.string.account_stale_note),
                style = MaterialTheme.typography.bodySmall,
                color = scheme.error,
            )
            Spacer(Modifier.height(4.dp))
            OutlinedButton(
                onClick = onRetry,
                modifier = Modifier.fillMaxWidth(),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.action_retry)) }
        }
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(R.string.account_methods_title),
            style = MaterialTheme.typography.labelLarge,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            stringResource(if (account.hasPassword) R.string.account_method_password_set else R.string.account_method_password_none),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurfaceVariant,
        )
        Text(
            stringResource(if (account.hasGoogle) R.string.account_google_linked else R.string.account_method_google_none),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurfaceVariant,
        )
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
                enabled = !account.resetSending && !account.stale,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.account_password_reset_send)) }
        } else if (account.hasPassword) {
            Spacer(Modifier.height(12.dp))
            OutlinedButton(
                onClick = onChangePassword,
                enabled = !account.stale,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.account_change_password)) }
        }
        // Konta tylko z Google dostaną zmianę adresu razem z logowaniem Google jako ponownym uwierzytelnieniem.
        if (account.hasPassword && !account.passwordUpgradeRequired) {
            val pending = account.pendingChange
            Spacer(Modifier.height(8.dp))
            if (pending == null) {
                OutlinedButton(
                    onClick = onChangeEmail,
                    enabled = !account.stale,
                    modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_CHANGE_EMAIL),
                    shape = AppButtonShape,
                ) { Text(stringResource(R.string.account_change_email)) }
            } else {
                Text(
                    stringResource(R.string.account_email_change_pending, pending.new_email),
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = onResendChange,
                    enabled = !account.changeBusy,
                    modifier = Modifier.fillMaxWidth(),
                    shape = AppButtonShape,
                ) { Text(stringResource(R.string.account_email_change_resend)) }
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = onCancelChange,
                    enabled = !account.changeBusy,
                    modifier = Modifier.fillMaxWidth(),
                    shape = AppButtonShape,
                ) { Text(stringResource(R.string.account_email_change_cancel)) }
            }
        }
        // Konta tylko z Google dostaną usuwanie razem z dowodem Google (F-005).
        if (account.hasPassword && !account.passwordUpgradeRequired) {
            Spacer(Modifier.height(16.dp))
            OutlinedButton(
                onClick = onDeleteAccount,
                enabled = !account.stale,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_DELETE_ACCOUNT),
                shape = AppButtonShape,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = scheme.error),
            ) { Text(stringResource(R.string.account_delete)) }
        }
    }
}

@Composable
internal fun DeleteAccountDialog(
    form: DeleteAccountUiState,
    onPasswordChange: (String) -> Unit,
    onConfirmedChange: (Boolean) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.account_delete),
        dismissOnClickOutside = !form.busy,
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(stringResource(R.string.account_delete_scope), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.account_delete_grace),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (form.unsentCount > 0) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.account_delete_unsent, form.unsentCount),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                Spacer(Modifier.height(12.dp))
                AppGrayField(
                    value = form.password,
                    onValueChange = onPasswordChange,
                    placeholder = stringResource(R.string.auth_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = form.confirmed,
                        onCheckedChange = onConfirmedChange,
                        enabled = !form.busy,
                        modifier = Modifier.testTag(TestTags.DELETE_ACCOUNT_CONFIRM),
                    )
                    Text(
                        stringResource(R.string.account_delete_confirm_check),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
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
                primaryText = stringResource(R.string.account_delete),
                onPrimary = onSubmit,
                primaryEnabled = !form.busy && form.confirmed,
            )
        },
    )
}

@Composable
internal fun ChangeEmailDialog(
    form: ChangeEmailUiState,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.account_change_email),
        dismissOnClickOutside = !form.busy,
        text = {
            Column {
                AppGrayField(
                    value = form.newEmail,
                    onValueChange = onEmailChange,
                    placeholder = stringResource(R.string.account_new_email),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
                )
                Spacer(Modifier.height(10.dp))
                AppGrayField(
                    value = form.password,
                    onValueChange = onPasswordChange,
                    placeholder = stringResource(R.string.account_current_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.account_change_email_hint),
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
                primaryText = stringResource(R.string.account_email_change_send),
                onPrimary = onSubmit,
                primaryEnabled = !form.busy,
            )
        },
    )
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
