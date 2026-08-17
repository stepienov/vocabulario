package com.vocabulario.app.ui.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
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
import kotlin.math.abs
import kotlinx.coroutines.flow.distinctUntilChanged

private val WheelItemHeight = 40.dp
private const val VisibleRows = 3

@Composable
fun WheelTimePicker(
    hour: Int,
    minute: Int,
    onHourChange: (Int) -> Unit,
    onMinuteChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
    testTag: String? = null,
) {
    val scheme = MaterialTheme.colorScheme
    Box(
        modifier = modifier
            .fillMaxWidth()
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.Center)
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
            key("hour") {
                WheelColumn(
                    value = hour.coerceIn(0, 23),
                    range = 0..23,
                    onValueChange = onHourChange,
                    modifier = Modifier.weight(1f),
                )
            }
            key("minute") {
                WheelColumn(
                    value = minute.coerceIn(0, 59),
                    range = 0..59,
                    onValueChange = onMinuteChange,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.Center)
                .height(WheelItemHeight),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier
                    .size(5.dp)
                    .clip(CircleShape)
                    .background(scheme.onSurface),
            )
            Box(Modifier.height(6.dp))
            Box(
                Modifier
                    .size(5.dp)
                    .clip(CircleShape)
                    .background(scheme.onSurface),
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
    val items = remember(range) { range.toList() }
    val startIndex = items.indexOf(value).coerceAtLeast(0)
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = startIndex)
    val fling = rememberSnapFlingBehavior(lazyListState = listState)
    val valueState = rememberUpdatedState(value)
    val onValueChangeState = rememberUpdatedState(onValueChange)
    val selectedIndex by remember { derivedStateOf { listState.centeredItemIndex() } }
    val consumeParentScroll = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset =
                Offset.Zero

            override fun onPostScroll(
                consumed: Offset,
                available: Offset,
                source: NestedScrollSource,
            ): Offset = Offset(0f, available.y)
        }
    }

    val programmaticScroll = remember { mutableStateOf(false) }
    LaunchedEffect(value) {
        val target = items.indexOf(value).coerceAtLeast(0)
        if (listState.isScrollInProgress) return@LaunchedEffect
        if (listState.centeredItemIndex() == target) return@LaunchedEffect
        programmaticScroll.value = true
        try {
            listState.scrollToItem(target)
        } finally {
            programmaticScroll.value = false
        }
    }
    LaunchedEffect(listState, items) {
        var userScrolling = false
        snapshotFlow { listState.isScrollInProgress }
            .distinctUntilChanged()
            .collect { inProgress ->
                if (programmaticScroll.value) {
                    userScrolling = false
                    return@collect
                }
                if (inProgress) {
                    userScrolling = true
                    return@collect
                }
                if (!userScrolling) return@collect
                userScrolling = false
                val index = listState.centeredItemIndex().coerceIn(0, items.lastIndex)
                val next = items[index]
                if (next != valueState.value) onValueChangeState.value(next)
            }
    }

    LazyColumn(
        state = listState,
        flingBehavior = fling,
        modifier = modifier
            .height(WheelItemHeight * VisibleRows)
            .nestedScroll(consumeParentScroll),
        contentPadding = PaddingValues(vertical = WheelItemHeight),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        items(items.size) { index ->
            val selected = index == selectedIndex
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

private fun LazyListState.centeredItemIndex(): Int {
    val layout = layoutInfo
    val visible = layout.visibleItemsInfo
    if (visible.isEmpty()) return firstVisibleItemIndex
    val center = (layout.viewportStartOffset + layout.viewportEndOffset) / 2
    return visible.minByOrNull { item ->
        abs((item.offset + item.size / 2) - center)
    }?.index ?: firstVisibleItemIndex
}
