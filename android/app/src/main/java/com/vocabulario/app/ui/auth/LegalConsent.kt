package com.vocabulario.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppToggle

/**
 * Zgody z T-003: osobne, niezaznaczone domyślnie pola „18+” i „warunki”, linki do dokumentów
 * oraz informacja o prywatności bez „zgadzam się”. Wspólne dla rejestracji, Google i bramki.
 */
@Composable
fun LegalConsentFields(
    consent: LegalConsentState,
    onTermsChange: (Boolean) -> Unit,
    onAdultChange: (Boolean) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uriHandler = LocalUriHandler.current
    val manifest = consent.manifest
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        ConsentRow(
            checked = consent.adultConfirmed,
            label = stringResource(R.string.legal_adult_confirm),
            onChange = onAdultChange,
            tag = TestTags.LEGAL_ADULT,
        )
        ConsentRow(
            checked = consent.termsAccepted,
            label = stringResource(R.string.legal_terms_accept),
            onChange = onTermsChange,
            tag = TestTags.LEGAL_TERMS,
        )
        when {
            manifest != null -> {
                manifest.urlOf("terms")?.let { url ->
                    TextButton(onClick = { uriHandler.openUri(url) }) {
                        Text(stringResource(R.string.legal_read_terms))
                    }
                }
                Text(
                    stringResource(R.string.legal_privacy_info),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                manifest.urlOf("privacy")?.let { url ->
                    TextButton(onClick = { uriHandler.openUri(url) }) {
                        Text(stringResource(R.string.legal_read_privacy))
                    }
                }
            }
            consent.loadFailed -> {
                Text(
                    stringResource(R.string.err_legal_load),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
                TextButton(onClick = onRetry) { Text(stringResource(R.string.action_retry)) }
            }
            else -> Text(
                stringResource(R.string.legal_loading),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ConsentRow(checked: Boolean, label: String, onChange: (Boolean) -> Unit, tag: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .toggleable(value = checked, role = Role.Switch, onValueChange = onChange)
            .testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AppToggle(checked = checked, onCheckedChange = null)
        Text(
            label,
            modifier = Modifier.padding(start = 12.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
