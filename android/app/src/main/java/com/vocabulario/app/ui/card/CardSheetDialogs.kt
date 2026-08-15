package com.vocabulario.app.ui.card

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow

@Composable
fun CardDialogButtonRow(
    modifier: Modifier = Modifier,
    primaryText: String,
    onPrimary: () -> Unit,
    primaryEnabled: Boolean = true,
    primaryModifier: Modifier = Modifier,
    primaryKind: AppDialogAction = AppDialogAction.Confirm,
    secondaryText: String? = null,
    onSecondary: (() -> Unit)? = null,
    secondaryModifier: Modifier = Modifier,
    secondaryKind: AppDialogAction = AppDialogAction.CancelRed,
) {
    AppDialogButtonRow(
        modifier = modifier,
        primaryText = primaryText,
        onPrimary = onPrimary,
        primaryEnabled = primaryEnabled,
        primaryModifier = primaryModifier,
        primaryKind = primaryKind,
        secondaryText = secondaryText,
        onSecondary = onSecondary,
        secondaryModifier = secondaryModifier,
        secondaryKind = secondaryKind,
    )
}

@Composable
fun CardBlockingAlertDialog(
    onDismissRequest: () -> Unit,
    modifier: Modifier = Modifier,
    title: @Composable () -> Unit,
    text: @Composable () -> Unit,
    buttons: @Composable () -> Unit,
    warning: Boolean = false,
    dismissOnClickOutside: Boolean = false,
) {
    AppAlertDialog(
        onDismissRequest = onDismissRequest,
        modifier = modifier,
        titleContent = title,
        text = text,
        buttons = buttons,
        warning = warning,
        dismissOnClickOutside = dismissOnClickOutside,
    )
}
