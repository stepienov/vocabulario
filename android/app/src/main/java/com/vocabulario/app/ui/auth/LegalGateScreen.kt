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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel

/** Konto czeka na akceptację aktualnych warunków; nauka i sync stoją, dane na urządzeniu zostają. */
@Composable
fun LegalGateScreen(
    onLogout: () -> Unit,
    viewModel: LegalGateViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val scheme = MaterialTheme.colorScheme
    val ready = state.consent.manifest != null &&
        state.consent.termsAccepted && state.consent.adultConfirmed

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
            stringResource(R.string.legal_gate_title),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(R.string.legal_gate_body),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(20.dp))
        LegalConsentFields(
            consent = state.consent,
            onTermsChange = viewModel::setTermsAccepted,
            onAdultChange = viewModel::setAdultConfirmed,
            onRetry = viewModel::load,
        )
        state.error?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = scheme.error, textAlign = TextAlign.Center)
        }
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = viewModel::accept,
            enabled = ready && !state.busy,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 52.dp)
                .testTag(TestTags.LEGAL_ACCEPT),
            shape = AppButtonShape,
        ) { ButtonLabel(stringResource(R.string.legal_gate_accept), style = MaterialTheme.typography.titleMedium) }
        Spacer(Modifier.height(16.dp))
        Text(
            stringResource(R.string.legal_gate_data_kept),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(12.dp))
        TextButton(
            onClick = onLogout,
            modifier = Modifier.testTag(TestTags.LEGAL_LOGOUT),
        ) { Text(stringResource(R.string.action_logout)) }
    }
}
