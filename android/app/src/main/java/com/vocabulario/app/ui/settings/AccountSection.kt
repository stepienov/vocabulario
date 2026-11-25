package com.vocabulario.app.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.AppToggle
import com.vocabulario.app.ui.components.GoogleButton

@Composable
internal fun AccountSectionBody(
    account: AccountUiState,
    onChangePassword: () -> Unit,
    onSendReset: () -> Unit,
    onDeleteAccount: () -> Unit,
    onLinkGoogle: () -> Unit,
    onAddPassword: () -> Unit,
    onVerifyEmail: () -> Unit,
    onLogout: () -> Unit,
    onRetry: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
        Column(Modifier.fillMaxWidth().padding(start = 16.dp, top = 4.dp, end = 16.dp, bottom = 6.dp)) {
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
                TextButton(onClick = onLogout, modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_LOGOUT)) {
                    Text(stringResource(R.string.action_logout))
                }
                return@Column
            }
            if (!account.emailVerified) {
                TextButton(onClick = onVerifyEmail, enabled = !account.stale, modifier = Modifier.heightIn(min = 44.dp)) {
                    Text(stringResource(R.string.verify_email_title))
                }
            }
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
            if (account.hasPassword && !account.hasGoogle && !account.passwordUpgradeRequired) {
                GoogleButton(
                    text = stringResource(R.string.account_link_google),
                    onClick = onLinkGoogle,
                    enabled = !account.stale,
                    modifier = Modifier.fillMaxWidth().padding(start = 12.dp, top = 12.dp, bottom = 12.dp).height(44.dp).testTag(TestTags.SETTINGS_LINK_GOOGLE),
                )
            }
            if (account.hasGoogle && !account.hasPassword) {
                TextButton(
                    onClick = onAddPassword,
                    enabled = !account.stale,
                    modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_ADD_PASSWORD),
                ) { Text(stringResource(R.string.account_add_password)) }
            }
            if (account.hasPassword && account.passwordUpgradeRequired) {
                Spacer(Modifier.height(12.dp))
                Text(
                    stringResource(R.string.account_password_reset_needed),
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                TextButton(
                    onClick = onSendReset,
                    enabled = !account.resetSending && !account.stale,
                    modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                ) { Text(stringResource(R.string.account_password_reset_send)) }
            } else if (account.hasPassword) {
                TextButton(
                    onClick = onChangePassword,
                    enabled = !account.stale,
                    modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_CHANGE_PASSWORD),
                ) { Text(stringResource(R.string.account_change_password)) }
            }
            TextButton(onClick = onLogout, modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_LOGOUT)) {
                Text(stringResource(R.string.action_logout))
            }
            val canManage = (account.hasPassword || account.hasGoogle) && !account.passwordUpgradeRequired
            if (canManage) {
                TextButton(
                    onClick = onDeleteAccount,
                    enabled = !account.stale,
                    modifier = Modifier.heightIn(min = 44.dp).testTag(TestTags.SETTINGS_DELETE_ACCOUNT),
                    colors = ButtonDefaults.textButtonColors(contentColor = scheme.error),
                ) { Text(stringResource(R.string.account_delete)) }
            }
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
            Column {
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
                if (form.usesGoogle) {
                    Text(
                        stringResource(R.string.account_google_confirm_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    AppGrayField(
                        value = form.password,
                        onValueChange = onPasswordChange,
                        placeholder = stringResource(R.string.auth_password),
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    )
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 48.dp)
                        .testTag(TestTags.DELETE_ACCOUNT_CONFIRM)
                        .toggleable(
                            value = form.confirmed,
                            enabled = !form.busy,
                            role = Role.Switch,
                            onValueChange = onConfirmedChange,
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AppToggle(
                        checked = form.confirmed,
                        onCheckedChange = null,
                        enabled = !form.busy,
                    )
                    Text(
                        stringResource(R.string.account_delete_confirm_check),
                        modifier = Modifier.padding(start = 12.dp),
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
internal fun LinkGoogleDialog(
    form: LinkGoogleUiState,
    accountEmail: String?,
    onPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.account_link_google),
        dismissOnClickOutside = !form.busy,
        text = {
            Column {
                Text(
                    stringResource(R.string.account_link_google_hint, accountEmail.orEmpty()),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(12.dp))
                AppGrayField(
                    value = form.password,
                    onValueChange = onPasswordChange,
                    placeholder = stringResource(R.string.account_current_password),
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
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
                primaryText = stringResource(R.string.auth_google),
                onPrimary = onSubmit,
                primaryEnabled = !form.busy,
            )
        },
    )
}

@Composable
internal fun AddPasswordDialog(
    form: AddPasswordUiState,
    onNewChange: (String) -> Unit,
    onRepeatChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    val passwordKeyboard = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Next)
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.account_add_password),
        dismissOnClickOutside = !form.busy,
        text = {
            Column {
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
                    stringResource(R.string.account_add_password_hint),
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
                primaryText = stringResource(R.string.auth_google),
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
