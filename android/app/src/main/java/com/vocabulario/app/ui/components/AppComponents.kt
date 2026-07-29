package com.vocabulario.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

val AppCardShape = RoundedCornerShape(16.dp)
val AppButtonShape = RoundedCornerShape(14.dp)
val AppChipShape = RoundedCornerShape(20.dp)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppScreenScaffold(
    title: String,
    onBack: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
    content: @Composable (Modifier) -> Unit,
) {
    Scaffold(
        modifier = modifier,
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Wstecz")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        content(Modifier.padding(padding).padding(horizontal = 20.dp))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val shape = AppCardShape
    if (onClick != null) {
        Card(
            onClick = onClick,
            modifier = modifier.fillMaxWidth(),
            shape = shape,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        ) { content() }
    } else {
        Card(
            modifier = modifier.fillMaxWidth(),
            shape = shape,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        ) { content() }
    }
}

@Composable
fun SettingsGroup(
    title: String,
    content: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            title.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
        )
        AppCard {
            Column(modifier = Modifier.padding(vertical = 4.dp)) {
                content()
            }
        }
        Spacer(Modifier.height(20.dp))
    }
}

@Composable
fun SettingsRadioRow(
    label: String,
    subtitle: String? = null,
    selected: Boolean,
    onSelect: () -> Unit,
    showDivider: Boolean = true,
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onSelect)
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.bodyLarge)
                subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            RadioButton(
                selected = selected,
                onClick = onSelect,
                colors = RadioButtonDefaults.colors(selectedColor = MaterialTheme.colorScheme.primary),
            )
        }
        if (showDivider) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant),
            )
        }
    }
}

@Composable
fun SettingsCheckRow(
    label: String,
    subtitle: String? = null,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    showDivider: Boolean = true,
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onCheckedChange(!checked) }
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.bodyLarge)
                subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Checkbox(
                checked = checked,
                onCheckedChange = onCheckedChange,
                colors = CheckboxDefaults.colors(checkedColor = MaterialTheme.colorScheme.primary),
            )
        }
        if (showDivider) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant),
            )
        }
    }
}

@Composable
fun TagChip(text: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = AppChipShape,
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
fun PracticeProgressBar(progress: Float, modifier: Modifier = Modifier) {
    LinearProgressIndicator(
        progress = { progress.coerceIn(0f, 1f) },
        modifier = modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(4.dp)),
        color = com.vocabulario.app.ui.theme.ProgressMuted,
        trackColor = MaterialTheme.colorScheme.surfaceVariant,
    )
}

@Composable
fun PromptCard(text: String, modifier: Modifier = Modifier) {
    AppCard(modifier = modifier) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 32.dp, horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text,
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChoiceTile(
    text: String,
    selected: Boolean,
    isCorrect: Boolean?,
    enabled: Boolean,
    onClick: () -> Unit,
    dimmed: Boolean = false,
    gloss: String? = null,
    showActions: Boolean = false,
    canFavorite: Boolean = true,
    canAddLearning: Boolean = true,
    onFavorite: (() -> Unit)? = null,
    onAddLearning: (() -> Unit)? = null,
) {
    val borderColor = when {
        selected && isCorrect == true -> com.vocabulario.app.ui.theme.GradeKnown
        else -> MaterialTheme.colorScheme.outline
    }
    val bgColor = when {
        selected && isCorrect == true -> MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
        dimmed -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
        else -> MaterialTheme.colorScheme.surface
    }
    val textAlpha = if (dimmed) 0.55f else 1f
    Surface(
        onClick = onClick,
        enabled = enabled && !dimmed,
        modifier = Modifier.fillMaxWidth(),
        shape = AppButtonShape,
        color = bgColor,
        shadowElevation = if (selected && !dimmed) 0.dp else 1.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.5.dp, borderColor, AppButtonShape)
                .padding(horizontal = 16.dp, vertical = 14.dp),
        ) {
            Text(
                text,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = textAlpha),
            )
            if (showActions && !gloss.isNullOrBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    gloss,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (showActions) {
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    IconButton(
                        onClick = { onFavorite?.invoke() },
                        enabled = canFavorite && onFavorite != null,
                    ) {
                        Icon(
                            Icons.Default.FavoriteBorder,
                            contentDescription = "Ulubione",
                            tint = if (canFavorite) MaterialTheme.colorScheme.onSurfaceVariant
                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
                        )
                    }
                    IconButton(
                        onClick = { onAddLearning?.invoke() },
                        enabled = canAddLearning && onAddLearning != null,
                    ) {
                        Icon(
                            Icons.Default.Add,
                            contentDescription = "Do nauki",
                            tint = if (canAddLearning) MaterialTheme.colorScheme.onSurfaceVariant
                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.25f),
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun GradeRow(
    onHard: () -> Unit,
    onLearning: () -> Unit,
    onKnown: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        GradeSquare("Trudne", com.vocabulario.app.ui.theme.GradeHard, Modifier.weight(1f), onHard)
        GradeSquare("Uczę się", com.vocabulario.app.ui.theme.GradeLearning, Modifier.weight(1f), onLearning)
        GradeSquare("Umiem", com.vocabulario.app.ui.theme.GradeKnown, Modifier.weight(1f), onKnown)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GradeSquare(
    label: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = modifier.height(64.dp),
        shape = RoundedCornerShape(12.dp),
        color = color,
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Text(
                label,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = Color.White,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
fun GradeButton(
    label: String,
    color: Color,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = AppButtonShape,
        color = color,
    ) {
        Text(
            label,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 16.dp),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = Color.White,
        )
    }
}

@Composable
fun NavTile(
    title: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AppCard(modifier = modifier, onClick = onClick) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            }
            Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
fun WordListItem(
    lemma: String,
    gloss: String?,
    pos: String?,
    enrichmentStatus: String? = null,
    onClick: (() -> Unit)? = null,
) {
    AppCard(onClick = onClick) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(lemma, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                gloss?.let {
                    Spacer(Modifier.height(4.dp))
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                when (enrichmentStatus) {
                    "pending" -> {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Przygotowuję kartę…",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    "failed" -> {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Nie udało się przygotować karty",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
            pos?.let { TagChip(it) }
        }
    }
}

@Composable
fun EmptyState(message: String, subtitle: String? = null) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
        subtitle?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }
}
