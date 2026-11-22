package com.vocabulario.app.ui.auth

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.vocabulario.app.R
import com.vocabulario.app.ui.report.SupportHelpDialog
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel
import kotlinx.coroutines.delay

/** Bramka weryfikacji adresu: nauka, import i sync czekają; dane na urządzeniu zostają. */
@Composable
fun VerifyEmailScreen(
    onLogout: () -> Unit,
    viewModel: VerifyEmailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var supportOpen by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme
    val lifecycleOwner = LocalLifecycleOwner.current

    // Powrót z poczty/przeglądarki: jeden odczyt stanu, bez pętli zapytań.
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.check(userAsked = false)
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    var nowMillis by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(state.resendAtMillis) {
        nowMillis = System.currentTimeMillis()
        while (nowMillis < state.resendAtMillis) {
            delay(1_000)
            nowMillis = System.currentTimeMillis()
        }
    }
    val waitSeconds = ((state.resendAtMillis - nowMillis + 999) / 1000).coerceAtLeast(0)

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
            stringResource(R.string.verify_email_title),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            state.email?.let { stringResource(R.string.verify_email_body, it) }
                ?: stringResource(R.string.verify_email_body_no_address),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )

        deliveryText(state.delivery)?.let { text ->
            Spacer(Modifier.height(16.dp))
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = scheme.surfaceVariant,
                contentColor = scheme.onSurfaceVariant,
            ) {
                Text(text, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }

        Spacer(Modifier.height(24.dp))
        Button(
            onClick = { viewModel.check(userAsked = true) },
            enabled = !state.busy,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 52.dp)
                .testTag(TestTags.VERIFY_EMAIL_CHECK),
            shape = AppButtonShape,
        ) { ButtonLabel(stringResource(R.string.verify_email_check), style = MaterialTheme.typography.titleMedium) }
        Spacer(Modifier.height(10.dp))
        OutlinedButton(
            onClick = viewModel::resend,
            enabled = !state.busy && waitSeconds == 0L,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 52.dp)
                .testTag(TestTags.VERIFY_EMAIL_RESEND),
            shape = AppButtonShape,
        ) {
            ButtonLabel(
                if (waitSeconds > 0) {
                    stringResource(R.string.verify_email_resend_in, waitSeconds.toInt())
                } else {
                    stringResource(R.string.verify_email_resend)
                },
                style = MaterialTheme.typography.titleMedium,
            )
        }

        state.error?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = scheme.error, textAlign = TextAlign.Center)
        }
        state.info?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = scheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }

        Spacer(Modifier.height(20.dp))
        listOf(
            R.string.verify_email_spam_hint,
            R.string.verify_email_data_kept,
            R.string.verify_email_wrong_address,
        ).forEach { res ->
            Text(
                stringResource(res),
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        Spacer(Modifier.height(12.dp))
        TextButton(
            onClick = onLogout,
            modifier = Modifier.testTag(TestTags.VERIFY_EMAIL_LOGOUT),
        ) { Text(stringResource(R.string.action_logout)) }
        TextButton(onClick = { supportOpen = true }) { Text(stringResource(R.string.support_title)) }
    }
    if (supportOpen) SupportHelpDialog(onDismiss = { supportOpen = false })
}

@Composable
internal fun deliveryText(delivery: MailDelivery): String? = when (delivery) {
    MailDelivery.NONE -> null
    MailDelivery.SENDING -> stringResource(R.string.verify_email_status_sending)
    MailDelivery.SENT -> stringResource(R.string.verify_email_status_sent)
    MailDelivery.DELAYED -> stringResource(R.string.verify_email_status_delayed)
    MailDelivery.FAILED -> stringResource(R.string.verify_email_status_failed)
}
