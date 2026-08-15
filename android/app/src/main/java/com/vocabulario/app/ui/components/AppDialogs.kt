package com.vocabulario.app.ui.components

import android.os.Build
import android.view.WindowManager
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import com.vocabulario.app.ui.theme.ActionConfirm
import com.vocabulario.app.ui.theme.ActionTeal

private val AppDialogButtonHeight = 40.dp
private val AppGrayFieldShape = AppDialogShape

enum class AppDialogAction {
    Confirm,
    ConfirmOutlined,
    Destroy,
    Teal,
    Neutral,
    CancelRed,
}

@Composable
fun AppGrayField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    readOnly: Boolean = false,
    singleLine: Boolean = true,
    isError: Boolean = false,
    placeholder: String? = null,
    leadingIcon: @Composable (() -> Unit)? = null,
    trailingIcon: @Composable (() -> Unit)? = null,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    minLines: Int = 1,
    maxLines: Int = if (singleLine) 1 else Int.MAX_VALUE,
    containerColor: Color? = null,
    unfocusedBorderColor: Color? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val fill = containerColor ?: scheme.surfaceVariant
    val idleBorder = unfocusedBorderColor ?: Color.Transparent
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        enabled = enabled,
        readOnly = readOnly,
        singleLine = singleLine,
        minLines = minLines,
        maxLines = maxLines,
        isError = isError,
        placeholder = placeholder?.let {
            { Text(it, color = scheme.onSurfaceVariant) }
        },
        leadingIcon = leadingIcon,
        trailingIcon = trailingIcon,
        visualTransformation = visualTransformation,
        keyboardOptions = keyboardOptions,
        keyboardActions = keyboardActions,
        shape = AppGrayFieldShape,
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = scheme.onSurface,
            unfocusedTextColor = scheme.onSurface,
            disabledTextColor = scheme.onSurface.copy(alpha = 0.6f),
            focusedContainerColor = fill,
            unfocusedContainerColor = fill,
            disabledContainerColor = fill,
            errorContainerColor = fill,
            unfocusedBorderColor = idleBorder,
            focusedBorderColor = scheme.outline,
            disabledBorderColor = idleBorder,
            errorBorderColor = scheme.error,
            cursorColor = scheme.primary,
        ),
    )
}

@Composable
fun AppDialogButton(
    text: String,
    onClick: () -> Unit,
    kind: AppDialogAction,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    val heightMod = modifier.heightIn(min = AppDialogButtonHeight)
    val padding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
    when (kind) {
        AppDialogAction.Confirm -> Button(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.buttonColors(
                containerColor = ActionConfirm,
                contentColor = Color.White,
            ),
        ) { ButtonLabel(text, color = Color.White) }
        AppDialogAction.Destroy -> Button(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.buttonColors(
                containerColor = scheme.error,
                contentColor = scheme.onError,
            ),
        ) { ButtonLabel(text) }
        AppDialogAction.Teal -> Button(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.buttonColors(
                containerColor = ActionTeal,
                contentColor = Color.White,
            ),
        ) { ButtonLabel(text, color = Color.White) }
        AppDialogAction.ConfirmOutlined -> OutlinedButton(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.outlinedButtonColors(contentColor = ActionConfirm),
            border = BorderStroke(1.dp, ActionConfirm),
        ) { ButtonLabel(text, color = ActionConfirm) }
        AppDialogAction.Neutral -> OutlinedButton(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.outlinedButtonColors(contentColor = scheme.onSurface),
        ) { ButtonLabel(text, color = scheme.onSurface) }
        AppDialogAction.CancelRed -> OutlinedButton(
            onClick = onClick,
            enabled = enabled,
            modifier = heightMod,
            shape = AppButtonShape,
            contentPadding = padding,
            colors = ButtonDefaults.outlinedButtonColors(contentColor = scheme.error),
            border = BorderStroke(1.dp, scheme.error),
        ) { ButtonLabel(text, color = scheme.error) }
    }
}

@Composable
fun AppDialogButtonRow(
    primaryText: String,
    onPrimary: () -> Unit,
    modifier: Modifier = Modifier,
    primaryKind: AppDialogAction = AppDialogAction.Confirm,
    primaryEnabled: Boolean = true,
    primaryModifier: Modifier = Modifier,
    secondaryText: String? = null,
    onSecondary: (() -> Unit)? = null,
    secondaryKind: AppDialogAction = AppDialogAction.CancelRed,
    secondaryModifier: Modifier = Modifier,
    middleText: String? = null,
    onMiddle: (() -> Unit)? = null,
    middleKind: AppDialogAction = AppDialogAction.ConfirmOutlined,
    middleModifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (secondaryText != null && onSecondary != null) {
            AppDialogButton(
                text = secondaryText,
                onClick = onSecondary,
                kind = secondaryKind,
                modifier = secondaryModifier.weight(1f),
            )
        }
        if (middleText != null && onMiddle != null) {
            AppDialogButton(
                text = middleText,
                onClick = onMiddle,
                kind = middleKind,
                modifier = middleModifier.weight(1f),
            )
        }
        AppDialogButton(
            text = primaryText,
            onClick = onPrimary,
            kind = primaryKind,
            enabled = primaryEnabled,
            modifier = if (secondaryText == null && middleText == null) {
                primaryModifier.fillMaxWidth()
            } else {
                primaryModifier.weight(1f)
            },
        )
    }
}

@Composable
fun AppAlertDialog(
    onDismissRequest: () -> Unit,
    buttons: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    title: String? = null,
    titleContent: (@Composable () -> Unit)? = null,
    text: (@Composable () -> Unit)? = null,
    warning: Boolean = false,
    dismissOnClickOutside: Boolean = true,
    dimAlpha: Float = 0.28f,
) {
    Dialog(
        onDismissRequest = onDismissRequest,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            dismissOnClickOutside = dismissOnClickOutside,
            dismissOnBackPress = dismissOnClickOutside,
        ),
    ) {
        AppDialogWindowChrome(dimAlpha = dimAlpha)
        Box(
            modifier = Modifier
                .fillMaxSize()
                .clickable(
                    enabled = dismissOnClickOutside,
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = onDismissRequest,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Surface(
                modifier = modifier
                    .fillMaxWidth(0.92f)
                    .widthIn(max = 520.dp)
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = {},
                    ),
                shape = AppDialogShape,
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 0.dp,
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    if (titleContent != null) {
                        titleContent()
                    } else if (title != null) {
                        Text(
                            title,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                    if (text != null) {
                        Spacer(Modifier.height(if (warning) 6.dp else 8.dp))
                        val scheme = MaterialTheme.colorScheme
                        CompositionLocalProvider(
                            LocalContentColor provides
                                if (warning) scheme.error else scheme.onSurface,
                        ) {
                            text()
                        }
                    }
                    Spacer(Modifier.height(16.dp))
                    buttons()
                }
            }
        }
    }
}

@Composable
fun AppDialogWindowChrome(dimAlpha: Float = 0.28f, blurDp: Int = 10) {
    val view = LocalView.current
    val density = LocalDensity.current
    DisposableEffect(view, dimAlpha, blurDp) {
        val window = dialogWindowOf(view)
        if (window != null) {
            window.setDimAmount(dimAlpha)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                window.addFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND)
                val params = window.attributes
                params.blurBehindRadius = with(density) { blurDp.dp.roundToPx() }
                window.attributes = params
            }
        }
        onDispose { }
    }
}

private fun dialogWindowOf(view: android.view.View): android.view.Window? {
    var parent = view.parent
    while (parent != null) {
        if (parent is DialogWindowProvider) return parent.window
        parent = parent.parent
    }
    return null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppPillDropdown(
    options: List<Pair<String, String>>,
    selectedCode: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String = "",
    testTag: String? = null,
    labelTextAlign: TextAlign = TextAlign.Start,
    labelBottomPadding: Dp = 6.dp,
) {
    var expanded by remember { mutableStateOf(false) }
    val matched = options.firstOrNull { it.first.equals(selectedCode, true) }?.second
    val selectedLabel = matched ?: if (selectedCode.isBlank()) placeholder else selectedCode
    val scheme = MaterialTheme.colorScheme
    val dark = scheme.background.luminance() < 0.5f
    val fieldFill = if (dark) scheme.surface else Color.White
    val valueColor = if (matched == null && selectedCode.isBlank()) scheme.onSurfaceVariant else scheme.onSurface
    Column(modifier = modifier.fillMaxWidth()) {
        if (!label.isNullOrBlank()) {
            Text(
                label,
                style = MaterialTheme.typography.labelLarge,
                color = scheme.onBackground,
                textAlign = labelTextAlign,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        start = if (labelTextAlign == TextAlign.Center) 0.dp else 4.dp,
                        bottom = labelBottomPadding,
                    ),
            )
        }
        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = it },
            modifier = Modifier
                .fillMaxWidth()
                .then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
        ) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                .fillMaxWidth(),
            shape = AppButtonShape,
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = valueColor,
                unfocusedTextColor = valueColor,
                disabledTextColor = scheme.onSurface.copy(alpha = 0.6f),
                focusedContainerColor = fieldFill,
                unfocusedContainerColor = fieldFill,
                disabledContainerColor = fieldFill,
                focusedBorderColor = scheme.outline,
                unfocusedBorderColor = scheme.outline,
                disabledBorderColor = scheme.outline,
                focusedTrailingIconColor = scheme.onSurfaceVariant,
                unfocusedTrailingIconColor = scheme.onSurfaceVariant,
                cursorColor = scheme.primary,
            ),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (code, name) ->
                DropdownMenuItem(
                    text = { Text(name, color = scheme.onSurface) },
                    onClick = {
                        expanded = false
                        onSelect(code)
                    },
                    modifier = if (testTag != null) {
                        Modifier.testTag("${testTag}__$code")
                    } else {
                        Modifier
                    },
                )
            }
        }
        }
    }
}

