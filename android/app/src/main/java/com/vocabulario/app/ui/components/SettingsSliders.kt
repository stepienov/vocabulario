package com.vocabulario.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

private val ThumbSize = 18.dp
private val TrackHeight = 6.dp
private val TickRadius = 3.5.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsValueSlider(
    value: Int,
    onValueChange: (Int) -> Unit,
    valueRange: IntRange,
    modifier: Modifier = Modifier,
    valueLabel: String = value.toString(),
    tickLabels: List<String>? = null,
    showValueAbove: Boolean = tickLabels == null,
    onValueChangeFinished: ((Int) -> Unit)? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val min = valueRange.first.toFloat()
    val max = valueRange.last.toFloat()
    val steps = if (tickLabels != null) {
        (valueRange.last - valueRange.first - 1).coerceAtLeast(0)
    } else {
        0
    }
    var dragging by remember { mutableStateOf<Int?>(null) }
    val interactionSource = remember { MutableInteractionSource() }
    val isDragged by interactionSource.collectIsDraggedAsState()
    val isPressed by interactionSource.collectIsPressedAsState()
    val userMoving = isDragged || isPressed
    val shown = (dragging ?: value).coerceIn(valueRange)
    val active = scheme.primary
    val inactive = scheme.outline
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (showValueAbove) {
            Text(
                valueLabel,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                color = active,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 4.dp),
            )
        }
        Slider(
            value = shown.toFloat(),
            onValueChange = { raw ->
                val next = raw.roundToInt().coerceIn(valueRange)
                if (userMoving) {
                    dragging = next
                    onValueChange(next)
                }
            },
            onValueChangeFinished = {
                val committed = (dragging ?: shown).coerceIn(valueRange)
                dragging = null
                onValueChangeFinished?.invoke(committed)
            },
            valueRange = min..max,
            steps = steps,
            modifier = Modifier.fillMaxWidth(),
            interactionSource = interactionSource,
            colors = SliderDefaults.colors(
                thumbColor = active,
                activeTrackColor = Color.Transparent,
                inactiveTrackColor = Color.Transparent,
                activeTickColor = Color.Transparent,
                inactiveTickColor = Color.Transparent,
            ),
            thumb = {
                Box(
                    modifier = Modifier
                        .size(ThumbSize)
                        .clip(CircleShape)
                        .background(active),
                )
            },
            track = { state ->
                val fraction = if (max == min) {
                    0f
                } else {
                    ((state.value - min) / (max - min)).coerceIn(0f, 1f)
                }
                val tickCount = (max - min).toInt()
                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(22.dp),
                ) {
                    val y = size.height / 2f
                    val trackH = TrackHeight.toPx()
                    val radius = trackH / 2f
                    drawRoundRect(
                        color = inactive.copy(alpha = 0.55f),
                        topLeft = Offset(0f, y - radius),
                        size = Size(size.width, trackH),
                        cornerRadius = CornerRadius(radius, radius),
                    )
                    val activeW = size.width * fraction
                    if (activeW > 0f) {
                        drawRoundRect(
                            brush = Brush.horizontalGradient(
                                colors = listOf(active, active.copy(alpha = 0.55f)),
                                startX = 0f,
                                endX = activeW,
                            ),
                            topLeft = Offset(0f, y - radius),
                            size = Size(activeW, trackH),
                            cornerRadius = CornerRadius(radius, radius),
                        )
                    }
                    if (tickLabels != null && tickCount > 0) {
                        val tickR = TickRadius.toPx()
                        for (i in 0..tickCount) {
                            val x = size.width * (i / tickCount.toFloat())
                            val filled = i.toFloat() <= (state.value - min) + 0.01f
                            drawCircle(
                                brush = if (filled) SolidColor(active) else SolidColor(inactive),
                                radius = tickR,
                                center = Offset(x, y),
                            )
                        }
                    }
                }
            },
        )
        if (!tickLabels.isNullOrEmpty()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                tickLabels.forEachIndexed { index, label ->
                    val selected = index == shown
                    Text(
                        label,
                        style = if (selected) {
                            MaterialTheme.typography.titleSmall
                        } else {
                            MaterialTheme.typography.labelSmall
                        },
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (selected) active else scheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}
