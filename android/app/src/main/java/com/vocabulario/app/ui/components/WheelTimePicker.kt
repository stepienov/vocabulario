package com.vocabulario.app.ui.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.map

private val WheelItemHeight = 40.dp
private const val VisibleRows = 3

@Composable
fun WheelTimePicker(
    hour: Int,
    minute: Int,
    onTimeChange: (hour: Int, minute: Int) -> Unit,
    modifier: Modifier = Modifier,
    testTag: String? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val consumeVertical = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset =
                Offset(0f, available.y)
        }
    }
    Box(
        modifier = modifier
            .fillMaxWidth()
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
            .nestedScroll(consumeVertical)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(WheelItemHeight)
                .clip(RoundedCornerShape(12.dp))
                .background(scheme.surfaceVariant.copy(alpha = 0.7f)),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(WheelItemHeight * VisibleRows),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            WheelColumn(
                value = hour.coerceIn(0, 23),
                range = 0..23,
                onValueChange = { onTimeChange(it, minute.coerceIn(0, 59)) },
                modifier = Modifier.weight(1f),
            )
            Text(
                ":",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onSurface,
            )
            WheelColumn(
                value = minute.coerceIn(0, 59),
                range = 0..59,
                onValueChange = { onTimeChange(hour.coerceIn(0, 23), it) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun WheelColumn(
    value: Int,
    range: IntRange,
    onValueChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val items = range.toList()
    val startIndex = items.indexOf(value).coerceAtLeast(0)
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = startIndex)
    val fling = rememberSnapFlingBehavior(lazyListState = listState)

    LaunchedEffect(value) {
        val target = items.indexOf(value).coerceAtLeast(0)
        if (listState.firstVisibleItemIndex != target && !listState.isScrollInProgress) {
            listState.scrollToItem(target)
        }
    }
    LaunchedEffect(listState) {
        snapshotFlow { listState.isScrollInProgress to listState.firstVisibleItemIndex }
            .filter { !it.first }
            .map { it.second.coerceIn(0, items.lastIndex) }
            .distinctUntilChanged()
            .collect { index ->
                val next = items[index]
                if (next != value) onValueChange(next)
            }
    }

    LazyColumn(
        state = listState,
        flingBehavior = fling,
        modifier = modifier.height(WheelItemHeight * VisibleRows),
        contentPadding = PaddingValues(vertical = WheelItemHeight),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        items(items.size) { index ->
            val selected = index == listState.firstVisibleItemIndex
            Text(
                items[index].toString().padStart(2, '0'),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(WheelItemHeight),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = if (selected) 1f else 0.35f),
            )
        }
    }
}
