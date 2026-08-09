package com.vocabulario.app.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppChipShape

@Composable
fun ListSortOrder.label(): String = when (this) {
    ListSortOrder.LemmaAsc -> stringResource(R.string.sort_lemma_asc)
    ListSortOrder.LemmaDesc -> stringResource(R.string.sort_lemma_desc)
    ListSortOrder.PosAsc -> stringResource(R.string.sort_pos)
    ListSortOrder.Newest -> stringResource(R.string.sort_newest)
    ListSortOrder.Oldest -> stringResource(R.string.sort_oldest)
    ListSortOrder.Status -> stringResource(R.string.sort_status)
}

@Composable
fun CardStateFilter.label(): String = when (this) {
    CardStateFilter.New -> stringResource(R.string.status_new)
    CardStateFilter.Learning -> stringResource(R.string.status_learning)
    CardStateFilter.Review -> stringResource(R.string.status_review)
    CardStateFilter.Mastered -> stringResource(R.string.status_mastered)
}

@Composable
fun ListWordsMetaBar(
    filter: ListFilterState,
    onSort: () -> Unit,
    onFilter: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val posPart = if (filter.pos.isEmpty()) {
        ""
    } else {
        filter.pos.map { key ->
            if (key == "unknown") {
                stringResource(R.string.filter_pos_unknown)
            } else {
                localizedPosLabel(key).ifBlank { key }
            }
        }.joinToString(", ")
    }
    val statePart = if (filter.states.isEmpty()) {
        ""
    } else {
        filter.states.map { it.label() }.joinToString(", ")
    }
    val filterSummary = listOf(posPart, statePart).filter { it.isNotBlank() }.joinToString(" · ")
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = if (filterSummary.isNotBlank()) {
            Arrangement.SpaceBetween
        } else {
            Arrangement.End
        },
    ) {
        if (filterSummary.isNotBlank()) {
            Text(
                text = filterSummary,
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MetaBarAction(
                label = stringResource(R.string.action_sort),
                onClick = onSort,
                modifier = Modifier.testTag(TestTags.BTN_LIST_SORT),
            )
            MetaBarAction(
                label = if (filter.isActive) {
                    stringResource(R.string.action_filter_active, filter.activeCount)
                } else {
                    stringResource(R.string.action_filter)
                },
                onClick = onFilter,
                modifier = Modifier.testTag(TestTags.BTN_LIST_FILTER),
            )
        }
    }
}

@Composable
private fun MetaBarAction(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    Text(
        text = label,
        modifier = modifier
            .clickable(onClick = onClick)
            .padding(horizontal = 4.dp, vertical = 2.dp),
        style = MaterialTheme.typography.labelLarge,
        fontWeight = FontWeight.Medium,
        color = scheme.primary,
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FlowRowChips(content: @Composable () -> Unit) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        content()
    }
}

@Composable
fun FilterToggleChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = AppChipShape,
        color = if (selected) scheme.primaryContainer else scheme.surfaceVariant,
        contentColor = if (selected) scheme.onPrimaryContainer else scheme.onSurface,
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
        )
    }
}
