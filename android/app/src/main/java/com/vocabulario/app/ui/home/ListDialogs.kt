package com.vocabulario.app.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField

data class ListPickOption(
    val id: String,
    val name: String,
)

@Composable
fun NameListDialog(
    visible: Boolean,
    title: String,
    name: String,
    onNameChange: (String) -> Unit,
    nameError: String?,
    reservedHint: Boolean,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
    confirmEnabled: Boolean,
    extraBody: (@Composable () -> Unit)? = null,
    nameFieldTag: String? = TestTags.SHEET_LIST_NAME,
    confirmTag: String? = null,
    cancelTag: String? = null,
) {
    if (!visible) return
    val scheme = MaterialTheme.colorScheme
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = title,
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                extraBody?.invoke()
                AppGrayField(
                    value = name,
                    onValueChange = onNameChange,
                    placeholder = stringResource(R.string.list_name_hint),
                    singleLine = true,
                    isError = nameError != null && !reservedHint,
                    modifier = if (nameFieldTag != null) Modifier.testTag(nameFieldTag) else Modifier,
                )
                if (nameError != null) {
                    Text(
                        nameError,
                        style = MaterialTheme.typography.labelMedium,
                        color = if (reservedHint) scheme.onSurfaceVariant else scheme.error,
                    )
                }
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryModifier = if (cancelTag != null) Modifier.testTag(cancelTag) else Modifier,
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onConfirm,
                primaryEnabled = confirmEnabled,
                primaryModifier = if (confirmTag != null) Modifier.testTag(confirmTag) else Modifier,
            )
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoveToListDialog(
    visible: Boolean,
    title: String,
    options: List<ListPickOption>,
    selectedId: String?,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
    onNewList: () -> Unit,
    onConfirm: () -> Unit,
    confirmEnabled: Boolean = true,
) {
    if (!visible) return
    var expanded by remember { mutableStateOf(false) }
    val selectedName = options.firstOrNull { it.id == selectedId }?.name.orEmpty()
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = title,
        text = {
            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = it },
                modifier = Modifier.fillMaxWidth(),
            ) {
                AppGrayField(
                    value = selectedName,
                    onValueChange = {},
                    readOnly = true,
                    modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable),
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                )
                ExposedDropdownMenu(
                    expanded = expanded,
                    onDismissRequest = { expanded = false },
                ) {
                    options.forEach { option ->
                        DropdownMenuItem(
                            text = { Text(option.name) },
                            onClick = {
                                onSelect(option.id)
                                expanded = false
                            },
                        )
                    }
                }
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.CancelRed,
                middleText = stringResource(R.string.list_new),
                onMiddle = onNewList,
                middleKind = AppDialogAction.ConfirmOutlined,
                primaryText = stringResource(R.string.action_ok),
                onPrimary = onConfirm,
                primaryEnabled = confirmEnabled,
            )
        },
    )
}

@Composable
fun DestroyConfirmDialog(
    visible: Boolean,
    title: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
    confirmText: String = stringResource(R.string.action_delete),
    confirmEnabled: Boolean = true,
    confirmTag: String? = null,
    cancelTag: String? = null,
    dialogTag: String? = null,
) {
    if (!visible) return
    AppAlertDialog(
        onDismissRequest = onDismiss,
        modifier = if (dialogTag != null) Modifier.testTag(dialogTag) else Modifier,
        title = title,
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.Neutral,
                secondaryModifier = if (cancelTag != null) Modifier.testTag(cancelTag) else Modifier,
                primaryText = confirmText,
                onPrimary = onConfirm,
                primaryKind = AppDialogAction.Destroy,
                primaryEnabled = confirmEnabled,
                primaryModifier = if (confirmTag != null) Modifier.testTag(confirmTag) else Modifier,
            )
        },
    )
}
