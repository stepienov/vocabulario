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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.playListingUrl
import com.vocabulario.app.data.publicSiteUrl
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel

/**
 * Serwer wymaga nowszej wersji (426). Biblioteka, sesja i kolejki zostają na urządzeniu;
 * pomoc prowadzi na publiczną stronę wsparcia, która nie podlega minimalnej wersji.
 */
@Composable
fun UpdateRequiredScreen(onCheckAgain: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val uriHandler = LocalUriHandler.current
    val packageName = LocalContext.current.packageName

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
            stringResource(R.string.update_required_title),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(R.string.update_required_body),
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            color = scheme.onBackground,
        )
        Spacer(Modifier.height(24.dp))
        Button(
            onClick = { runCatching { uriHandler.openUri(playListingUrl(packageName)) } },
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 52.dp)
                .testTag(TestTags.UPDATE_REQUIRED_ACTION),
            shape = AppButtonShape,
        ) { ButtonLabel(stringResource(R.string.update_required_action), style = MaterialTheme.typography.titleMedium) }
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = onCheckAgain) { Text(stringResource(R.string.sync_action_retry)) }
        TextButton(
            onClick = { runCatching { uriHandler.openUri(publicSiteUrl(ApiBaseUrl.resolve(), "/support")) } },
        ) { Text(stringResource(R.string.support_open_site)) }
    }
}
