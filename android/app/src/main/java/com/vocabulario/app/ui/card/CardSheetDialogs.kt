package com.vocabulario.app.ui.card

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogShape

private val DialogButtonHeight = 48.dp

@Composable
fun CardDialogButtonRow(
    modifier: Modifier = Modifier,
    primaryText: String,
    onPrimary: () -> Unit,
    primaryEnabled: Boolean = true,
    primaryModifier: Modifier = Modifier,
    secondaryText: String? = null,
    onSecondary: (() -> Unit)? = null,
    secondaryModifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    if (secondaryText != null && onSecondary != null) {
        Row(
            modifier = modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedButton(
                onClick = onSecondary,
                modifier = secondaryModifier
                    .weight(1f)
                    .height(DialogButtonHeight),
                shape = AppButtonShape,
            ) {
                Text(secondaryText, fontWeight = FontWeight.SemiBold, color = scheme.onSurface)
            }
            Button(
                onClick = onPrimary,
                enabled = primaryEnabled,
                modifier = primaryModifier
                    .weight(1f)
                    .height(DialogButtonHeight),
                shape = AppButtonShape,
            ) {
                Text(primaryText, fontWeight = FontWeight.SemiBold)
            }
        }
    } else {
        Button(
            onClick = onPrimary,
            enabled = primaryEnabled,
            modifier = primaryModifier
                .fillMaxWidth()
                .height(DialogButtonHeight),
            shape = AppButtonShape,
        ) {
            Text(primaryText, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
fun CardBlockingAlertDialog(
    onDismissRequest: () -> Unit,
    modifier: Modifier = Modifier,
    title: @Composable () -> Unit,
    text: @Composable () -> Unit,
    buttons: @Composable () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    AlertDialog(
        onDismissRequest = onDismissRequest,
        modifier = modifier,
        shape = AppDialogShape,
        containerColor = scheme.surface,
        tonalElevation = 0.dp,
        title = title,
        text = text,
        confirmButton = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(end = 8.dp, bottom = 8.dp),
            ) {
                buttons()
            }
        },
        dismissButton = {},
    )
}
