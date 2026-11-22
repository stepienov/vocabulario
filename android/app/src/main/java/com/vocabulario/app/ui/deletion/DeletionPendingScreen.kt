package com.vocabulario.app.ui.deletion

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel
import java.time.ZoneId
import java.util.Locale

/** Konto czeka na usunięcie: biblioteka ukryta, dane lokalne zostają do zakończenia usuwania. */
@Composable
fun DeletionPendingScreen(viewModel: DeletionPendingViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    val context = androidx.compose.ui.platform.LocalContext.current
    val scheme = MaterialTheme.colorScheme
    val view = state.view

    state.cancelPassword?.let { password ->
        AppAlertDialog(
            onDismissRequest = viewModel::closeCancel,
            title = stringResource(R.string.deletion_pending_cancel),
            dismissOnClickOutside = !state.busy,
            text = {
                Column {
                    Text(
                        stringResource(R.string.deletion_pending_cancel_hint),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(12.dp))
                    AppGrayField(
                        value = password,
                        onValueChange = viewModel::updateCancelPassword,
                        placeholder = stringResource(R.string.auth_password),
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done,
                        ),
                    )
                    state.error?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = scheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            buttons = {
                AppDialogButtonRow(
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = viewModel::closeCancel,
                    secondaryKind = AppDialogAction.Neutral,
                    primaryText = stringResource(R.string.deletion_pending_cancel),
                    onPrimary = viewModel::submitCancel,
                    primaryEnabled = !state.busy,
                )
            },
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp)
            .padding(top = 36.dp, bottom = 28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        BrandLogo(height = 44.dp, maxWidth = 280.dp)
        Spacer(Modifier.height(28.dp))
        Text(
            stringResource(R.string.deletion_pending_title),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(12.dp))
        if (view != null) {
            val zone = ZoneId.systemDefault()
            val locale = Locale.getDefault()
            val purging = view.state != "grace" || !view.can_cancel
            Text(
                if (purging) {
                    stringResource(R.string.deletion_pending_purging)
                } else {
                    stringResource(
                        R.string.deletion_pending_body,
                        formatDeletionInstant(view.cancel_until, zone, locale),
                        formatDeletionInstant(view.purge_due_at, zone, locale),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
                color = scheme.onBackground,
            )
            Spacer(Modifier.height(24.dp))
            Button(
                onClick = viewModel::refresh,
                enabled = !state.busy,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp)
                    .testTag(TestTags.DELETION_PENDING_REFRESH),
                shape = AppButtonShape,
            ) { ButtonLabel(stringResource(R.string.deletion_pending_refresh), style = MaterialTheme.typography.titleMedium) }
            if (!purging) {
                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    onClick = {
                        if (state.cancelWithGoogle) viewModel.cancelWithGoogle(context) else viewModel.openCancel()
                    },
                    enabled = !state.busy,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 52.dp)
                        .testTag(TestTags.DELETION_PENDING_CANCEL),
                    shape = AppButtonShape,
                ) { ButtonLabel(stringResource(R.string.deletion_pending_cancel), style = MaterialTheme.typography.titleMedium) }
            }
        }
        if (state.cancelPassword == null) {
            state.error?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = scheme.error, textAlign = TextAlign.Center)
            }
        }
    }
}
