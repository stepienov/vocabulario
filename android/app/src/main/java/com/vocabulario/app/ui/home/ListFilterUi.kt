package com.vocabulario.app.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Sort
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppChipShape
import com.vocabulario.app.ui.components.AppGrayField

@Composable
fun ListSortOrder.label(): String = when (this) {
    ListSortOrder.LemmaAsc -> stringResource(R.string.sort_lemma_asc)
    ListSortOrder.LemmaDesc -> stringResource(R.string.sort_lemma_desc)
    ListSortOrder.Newest -> stringResource(R.string.sort_newest)
    ListSortOrder.Oldest -> stringResource(R.string.sort_oldest)
}

@Composable
fun CardStateFilter.label(): String = when (this) {
    CardStateFilter.New -> stringResource(R.string.status_new)
    CardStateFilter.Learning -> stringResource(R.string.status_learning)
    CardStateFilter.Review -> stringResource(R.string.status_review)
    CardStateFilter.Mastered -> stringResource(R.string.status_mastered)
}

@Composable
fun ListWordsToolbar(
    query: String,
    onQueryChange: (String) -> Unit,
    filter: ListFilterState,
    onSort: () -> Unit,
    onFilter: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    fun hideKeyboard() {
        keyboard?.hide()
        focusManager.clearFocus()
    }
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        AppGrayField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier
                .weight(1f)
                .testTag(TestTags.LIST_SEARCH_INPUT),
            singleLine = true,
            leadingIcon = {
                Icon(
                    Icons.Default.Search,
                    contentDescription = stringResource(R.string.list_search_hint),
                    tint = scheme.onSurfaceVariant,
                )
            },
            trailingIcon = if (query.isNotEmpty()) {
                {
                    IconButton(onClick = { onQueryChange("") }) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = stringResource(R.string.action_close),
                            tint = scheme.onSurfaceVariant,
                        )
                    }
                }
            } else {
                null
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { hideKeyboard() }),
        )
        IconButton(
            onClick = onSort,
            modifier = Modifier.testTag(TestTags.BTN_LIST_SORT),
        ) {
            Icon(
                Icons.Default.Sort,
                contentDescription = stringResource(R.string.action_sort),
                tint = scheme.primary,
            )
        }
        IconButton(
            onClick = onFilter,
            modifier = Modifier.testTag(TestTags.BTN_LIST_FILTER),
        ) {
            BadgedBox(
                badge = {
                    if (filter.isActive) {
                        Badge { Text("${filter.activeCount}") }
                    }
                },
            ) {
                Icon(
                    Icons.Default.FilterList,
                    contentDescription = if (filter.isActive) {
                        stringResource(R.string.action_filter_active, filter.activeCount)
                    } else {
                        stringResource(R.string.action_filter)
                    },
                    tint = if (filter.isActive) scheme.primary else scheme.onSurfaceVariant,
                )
            }
        }
    }
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
    unselectedColor: Color,
    onClick: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        selected = selected,
        onClick = onClick,
        shape = AppChipShape,
        color = if (selected) scheme.primary else unselectedColor,
        contentColor = if (selected) scheme.onPrimary else scheme.onSurface,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (selected) {
                Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
            }
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
            )
        }
    }
}
