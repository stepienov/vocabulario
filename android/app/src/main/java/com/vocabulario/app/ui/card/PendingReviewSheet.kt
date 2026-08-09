package com.vocabulario.app.ui.card

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.TagChip

/**
 * Modal dla słowa „wymaga sprawdzenia". Dwa scenariusze:
 *  - brak propozycji → komunikat „nie znaleziono" + [Odrzuć] [Szukaj ponownie],
 *  - są propozycje → „Czy chodziło Ci o:" + kafelki + [Szukaj ponownie] [Zatwierdź] i pod nimi [Odrzuć].
 * Używa wspólnego kształtu/przycisków (CardBlockingAlertDialog + CardDialogButtonRow) — spójnie z resztą.
 */
@Composable
fun PendingReviewSheet(
    visible: Boolean,
    word: String,
    suggestions: List<LookupCandidate>,
    selectedIndex: Int?,
    loading: Boolean,
    submitting: Boolean,
    onSelect: (Int) -> Unit,
    onReject: () -> Unit,
    onSearchAgain: () -> Unit,
    onConfirm: () -> Unit,
    onClose: () -> Unit,
) {
    if (!visible) return
    val scheme = MaterialTheme.colorScheme
    val hasSuggestions = suggestions.isNotEmpty()

    CardBlockingAlertDialog(
        onDismissRequest = { if (!submitting) onClose() },
        modifier = Modifier.testTag(TestTags.SHEET_REVIEW_WORD),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    stringResource(R.string.review_title),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = { if (!submitting) onClose() },
                    modifier = Modifier
                        .size(32.dp)
                        .testTag(TestTags.BTN_REVIEW_CLOSE),
                ) {
                    Icon(Icons.Default.Close, contentDescription = stringResource(R.string.review_close))
                }
            }
        },
        text = {
            when {
                loading -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(28.dp), strokeWidth = 3.dp)
                    }
                }
                !hasSuggestions -> {
                    Text(
                        stringResource(R.string.review_no_match, word),
                        style = MaterialTheme.typography.bodyLarge,
                        color = scheme.onSurfaceVariant,
                    )
                }
                else -> {
                    Column {
                        Text(
                            stringResource(R.string.review_did_you_mean),
                            style = MaterialTheme.typography.bodyLarge,
                            color = scheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(12.dp))
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 300.dp)
                                .verticalScroll(rememberScrollState()),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            suggestions.forEachIndexed { index, candidate ->
                                SuggestionTile(
                                    candidate = candidate,
                                    selected = selectedIndex == index,
                                    enabled = !submitting,
                                    onClick = { onSelect(index) },
                                    modifier = Modifier.testTag("${TestTags.REVIEW_SUGGESTION}$index"),
                                )
                            }
                        }
                    }
                }
            }
        },
        buttons = {
            when {
                loading -> Unit
                !hasSuggestions -> {
                    CardDialogButtonRow(
                        secondaryText = stringResource(R.string.review_reject),
                        onSecondary = onReject,
                        secondaryModifier = Modifier.testTag(TestTags.BTN_REVIEW_REJECT),
                        primaryText = stringResource(R.string.review_search_again),
                        onPrimary = onSearchAgain,
                        primaryModifier = Modifier.testTag(TestTags.BTN_REVIEW_SEARCH_AGAIN),
                    )
                }
                else -> {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        CardDialogButtonRow(
                            secondaryText = stringResource(R.string.review_search_again),
                            onSecondary = onSearchAgain,
                            secondaryModifier = Modifier.testTag(TestTags.BTN_REVIEW_SEARCH_AGAIN),
                            primaryText = stringResource(R.string.review_confirm),
                            onPrimary = onConfirm,
                            primaryEnabled = selectedIndex != null && !submitting,
                            primaryModifier = Modifier.testTag(TestTags.BTN_REVIEW_CONFIRM),
                        )
                        TextButton(
                            onClick = onReject,
                            enabled = !submitting,
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag(TestTags.BTN_REVIEW_REJECT),
                        ) {
                            Text(
                                stringResource(R.string.review_reject),
                                fontWeight = FontWeight.SemiBold,
                                color = scheme.error,
                            )
                        }
                    }
                }
            }
        },
    )
}

@Composable
private fun SuggestionTile(
    candidate: LookupCandidate,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val tileColor = if (selected) scheme.primary.copy(alpha = 0.12f) else scheme.surfaceVariant
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .then(
                if (selected) Modifier.border(2.dp, scheme.primary, RoundedCornerShape(16.dp))
                else Modifier,
            )
            .clickable(enabled = enabled, onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        color = tileColor,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    candidate.lemma.ifBlank { "—" },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                if (candidate.gloss.isNotBlank()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        candidate.gloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = scheme.onSurfaceVariant,
                    )
                }
                candidate.pos?.takeIf { it.isNotBlank() }?.let { pos ->
                    Spacer(Modifier.height(8.dp))
                    TagChip(localizedPosLabel(pos).ifBlank { pos })
                }
            }
            if (selected) {
                Icon(
                    Icons.Default.Check,
                    contentDescription = null,
                    tint = scheme.primary,
                    modifier = Modifier.size(22.dp),
                )
            }
        }
    }
}
