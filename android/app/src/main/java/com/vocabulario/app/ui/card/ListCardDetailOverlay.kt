package com.vocabulario.app.ui.card

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.vocabulario.app.R
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.ImportDisplayFlip
import com.vocabulario.app.ui.components.parseImportDisplayFromContent

@Composable
fun ListCardDetailOverlay(
    card: CardResponse,
    profile: LanguageProfileResponse?,
    onDismiss: () -> Unit,
) {
    BackHandler(onBack = onDismiss)
    val scheme = MaterialTheme.colorScheme

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = scheme.background,
        ) {
            Column(Modifier.fillMaxSize()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .statusBarsPadding()
                        .padding(start = 20.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        card.lemma_l2.ifBlank { "—" },
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.testTag(TestTags.BTN_VIEW_CARD_CLOSE),
                    ) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = stringResource(R.string.action_close),
                        )
                    }
                }
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .navigationBarsPadding()
                        .padding(horizontal = 20.dp)
                        .padding(bottom = 40.dp),
                ) {
                    val importDisplay = parseImportDisplayFromContent(card.content)
                    if (importDisplay != null) {
                        ImportDisplayFlip(
                            display = importDisplay,
                            enableTts = true,
                            learningLang = profile?.learning_lang
                                ?: card.content["language"].asJsonString(),
                        )
                    } else {
                        CardDetailContent(
                            content = card.content,
                            lemmaFallback = card.lemma_l2,
                            languageCode = card.content["language"].asJsonString()
                                ?: profile?.learning_lang,
                            compact = false,
                            fullDetail = true,
                            scrollable = false,
                            userTenses = emptyList(),
                            userCefr = profile?.cefr_level ?: "C2",
                            enrichmentStatus = card.enrichment_status,
                            enrichmentError = card.enrichment_error,
                            profile = profile,
                        )
                    }
                }
            }
        }
    }
}
