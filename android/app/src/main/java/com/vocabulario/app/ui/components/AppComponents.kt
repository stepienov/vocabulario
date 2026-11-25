package com.vocabulario.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vocabulario.app.R
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.theme.GradeAgain
import com.vocabulario.app.ui.theme.GradeHard
import com.vocabulario.app.ui.theme.GradeKnown
import com.vocabulario.app.ui.theme.GradeLearning
import com.vocabulario.app.ui.theme.LocalVocabExtraColors
import com.vocabulario.app.ui.theme.posChipContainer

val AppCardShape = RoundedCornerShape(18.dp)
val AppButtonShape = RoundedCornerShape(28.dp)
val AppChipShape = RoundedCornerShape(999.dp)
val AppDialogShape = RoundedCornerShape(24.dp)

@Composable
fun GoogleButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (dark) Color(0xFF131314) else Color.White,
            contentColor = if (dark) Color(0xFFE3E3E3) else Color(0xFF1A73E8),
        ),
        border = BorderStroke(1.dp, if (dark) Color(0xFF8E918F) else Color(0xFFDADCE0)),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 1.dp, pressedElevation = 0.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
            Image(painterResource(R.drawable.ic_google_g), contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(12.dp))
            Text(
                text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/**
 * Label for compact buttons / equal-weight rows.
 * Always one line — no mid-word wrap or clipped second line in any language.
 */
@Composable
fun ButtonLabel(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.labelLarge,
) {
    Text(
        text = text,
        modifier = modifier.fillMaxWidth(),
        color = color,
        style = style,
        textAlign = TextAlign.Center,
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppScreenScaffold(
    title: String,
    onBack: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable (Modifier) -> Unit,
) {
    Scaffold(
        modifier = modifier.imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        title,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onBackground,
                    )
                },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack, modifier = Modifier.testTag(TestTags.BTN_BACK)) {
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = stringResource(R.string.cd_back),
                            )
                        }
                    }
                },
                actions = actions,
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                    navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                    actionIconContentColor = MaterialTheme.colorScheme.onBackground,
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
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = AppCardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        content = { content() },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = AppCardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        content = { content() },
    )
}

@Composable
fun LemmaActionRow(
    lemma: String,
    gloss: String?,
    trailing: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    belowGloss: (@Composable ColumnScope.() -> Unit)? = null,
) {
    val body: @Composable () -> Unit = {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    lemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (!gloss.isNullOrBlank()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        gloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                belowGloss?.invoke(this)
            }
            trailing()
        }
    }
    if (onClick != null) {
        AppCard(onClick = onClick, modifier = modifier, content = body)
    } else {
        AppCard(modifier = modifier, content = body)
    }
}

@Composable
fun LemmaAddButton(
    onClick: () -> Unit,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = scheme.primary,
        contentColor = scheme.onPrimary,
        modifier = modifier.size(40.dp),
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Icon(Icons.Default.Add, contentDescription = contentDescription, modifier = Modifier.size(22.dp))
        }
    }
}

@Composable
fun LemmaOnListIndicator(modifier: Modifier = Modifier) {
    val extras = LocalVocabExtraColors.current
    Surface(
        shape = CircleShape,
        color = extras.onListBackground,
        contentColor = extras.onList,
        modifier = modifier.size(40.dp),
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Icon(
                Icons.Default.Check,
                contentDescription = stringResource(R.string.cd_on_list),
                modifier = Modifier.size(22.dp),
            )
        }
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
    showDivider: Boolean = false,
    testTag: String? = null,
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
                .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect)
                .heightIn(min = 44.dp)
                .padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
                RadioButton(
                    selected = selected,
                    onClick = null,
                    colors = RadioButtonDefaults.colors(selectedColor = MaterialTheme.colorScheme.primary),
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.bodyMedium)
                subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
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
fun AppToggle(
    checked: Boolean,
    onCheckedChange: ((Boolean) -> Unit)?,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    val interaction = if (onCheckedChange != null) {
        Modifier
            .toggleable(value = checked, enabled = enabled, role = Role.Switch, onValueChange = onCheckedChange)
            .size(48.dp)
    } else {
        Modifier
    }
    Box(modifier = modifier.then(interaction), contentAlignment = Alignment.Center) {
        Box(
            modifier = Modifier
                .alpha(if (enabled) 1f else 0.38f)
                .size(width = 42.dp, height = 26.dp)
                .background(if (checked) scheme.primaryContainer else scheme.surface, CircleShape)
                .border(1.5.dp, if (checked) scheme.primary else scheme.onSurfaceVariant.copy(alpha = 0.5f), CircleShape),
        ) {
            Box(
                modifier = Modifier
                    .align(if (checked) Alignment.CenterEnd else Alignment.CenterStart)
                    .padding(horizontal = 4.dp)
                    .size(16.dp)
                    .background(if (checked) scheme.primary else scheme.onSurfaceVariant.copy(alpha = 0.6f), CircleShape),
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
    showDivider: Boolean = false,
    testTag: String? = null,
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
                .toggleable(value = checked, role = Role.Switch, onValueChange = onCheckedChange)
                .heightIn(min = 48.dp)
                .padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.bodyMedium)
                subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            AppToggle(checked = checked, onCheckedChange = null)
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
fun TagChip(
    text: String,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    containerColor: Color = MaterialTheme.colorScheme.primaryContainer,
) {
    val content: @Composable () -> Unit = {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
    if (onClick != null) {
        // Without this, clickable Surface expands to 48dp min touch target and misaligns next to plain chips.
        CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
            Surface(
                onClick = onClick,
                modifier = modifier,
                shape = AppChipShape,
                color = containerColor,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                content = content,
            )
        }
    } else {
        Surface(
            modifier = modifier,
            shape = AppChipShape,
            color = containerColor,
            content = content,
        )
    }
}

@Composable
fun PosTagChip(pos: String) {
    TagChip(
        text = localizedPosLabel(pos).ifBlank { pos },
        containerColor = posChipContainer(MaterialTheme.colorScheme, pos),
    )
}

@Composable
fun SpeakIconButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
) {
    val size = if (compact) 36.dp else 44.dp
    val iconSize = if (compact) 18.dp else 22.dp
    IconButton(
        onClick = onClick,
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.primaryContainer),
    ) {
        Icon(
            Icons.AutoMirrored.Filled.VolumeUp,
            contentDescription = stringResource(R.string.cd_play),
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(iconSize),
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
fun PromptCard(
    text: String,
    modifier: Modifier = Modifier,
    languageLabel: String? = null,
    meanings: List<String> = listOf(text),
    highlighted: Boolean = false,
    compact: Boolean = false,
) {
    val baseStyle = MaterialTheme.typography.displaySmall
    val isSingleWord = remember(text) {
        val trimmed = text.trim()
        trimmed.isNotEmpty() && trimmed.none { it.isWhitespace() }
    }
    var fontSize by remember(text, isSingleWord) { mutableStateOf(baseStyle.fontSize) }

    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        if (languageLabel != null && !compact) {
            Surface(
                shape = AppChipShape,
                color = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            ) {
                Text(
                    languageLabel,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            Spacer(Modifier.height(8.dp))
        }
        val extras = LocalVocabExtraColors.current
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = AppCardShape,
            colors = CardDefaults.cardColors(
                containerColor = if (highlighted) extras.practicePrompt else MaterialTheme.colorScheme.surface,
            ),
            border = BorderStroke(
                1.dp,
                if (highlighted) extras.practicePromptBorder else MaterialTheme.colorScheme.outline,
            ),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        vertical = if (compact) 9.dp else if (meanings.size > 1) 10.dp else 32.dp,
                        horizontal = if (compact) 5.dp else 14.dp,
                    ),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (compact) {
                    Text(
                        meanings.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.Bold),
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                } else if (meanings.size > 1) {
                    meanings.forEachIndexed { index, meaning ->
                        if (index > 0) {
                            Spacer(
                                Modifier
                                    .padding(vertical = 4.dp)
                                    .width(29.dp)
                                    .height(1.dp)
                                    .background(MaterialTheme.colorScheme.outline),
                            )
                        }
                        Text(
                            meaning,
                            style = MaterialTheme.typography.headlineSmall.copy(
                                fontSize = 21.sp,
                                lineHeight = 26.sp,
                                fontWeight = FontWeight.Bold,
                            ),
                            textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                } else {
                    Text(
                        text,
                        style = baseStyle.copy(
                            fontSize = if (isSingleWord) fontSize else baseStyle.fontSize,
                            fontWeight = FontWeight.Bold,
                        ),
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = if (isSingleWord && fontSize.value > 16f) 1 else Int.MAX_VALUE,
                        softWrap = !isSingleWord || fontSize.value <= 16f,
                        overflow = TextOverflow.Clip,
                        onTextLayout = { layout ->
                            if (isSingleWord && layout.hasVisualOverflow && fontSize.value > 16f) {
                                fontSize = (fontSize.value - 2f).coerceAtLeast(16f).sp
                            }
                        },
                    )
                }
            }
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
    modifier: Modifier = Modifier,
    dimmed: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    val extras = LocalVocabExtraColors.current
    val borderColor = when {
        selected && isCorrect == true -> com.vocabulario.app.ui.theme.GradeKnown
        selected -> scheme.primary
        else -> scheme.outline
    }
    val bgColor = when {
        selected && isCorrect == true -> scheme.primaryContainer.copy(alpha = 0.45f)
        dimmed -> extras.practiceWrongBackground
        else -> scheme.surface
    }
    Surface(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().heightIn(min = 48.dp).testTag(TestTags.PRACTICE_CHOICE),
        shape = RoundedCornerShape(15.dp),
        color = bgColor,
        contentColor = scheme.onSurface,
        shadowElevation = 0.dp,
        border = BorderStroke(if (selected) 2.dp else 1.dp, borderColor),
    ) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            BoxWithConstraints(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 6.dp, vertical = 6.dp),
                contentAlignment = Alignment.Center,
            ) {
                val textMeasurer = rememberTextMeasurer()
                val baseStyle = MaterialTheme.typography.bodyLarge.copy(fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                val width = constraints.maxWidth
                val height = constraints.maxHeight
                val fittedSize = remember(text, width, height, baseStyle, textMeasurer) {
                    var size = baseStyle.fontSize.value
                    while (size > 10f) {
                        val style = baseStyle.copy(
                            fontSize = size.sp,
                            lineHeight = (size * 1.25f).sp,
                            lineBreak = LineBreak.Heading,
                        )
                        val wholeWordsFit = text.split(Regex("\\s+")).all { word ->
                            !textMeasurer.measure(
                                text = word,
                                style = style,
                                constraints = Constraints(maxWidth = width),
                                maxLines = 1,
                                softWrap = false,
                            ).hasVisualOverflow
                        }
                        val layout = textMeasurer.measure(
                            text = text,
                            style = style,
                            constraints = Constraints(maxWidth = width, maxHeight = height),
                        )
                        if (wholeWordsFit && !layout.hasVisualOverflow) break
                        size = (size - 0.5f).coerceAtLeast(10f)
                    }
                    size.sp
                }
                Text(
                    text,
                    modifier = Modifier.fillMaxWidth(),
                    style = baseStyle.copy(
                        fontSize = fittedSize,
                        lineHeight = (fittedSize.value * 1.25f).sp,
                        lineBreak = LineBreak.Heading,
                    ),
                    textAlign = TextAlign.Center,
                    color = if (dimmed) scheme.onSurfaceVariant else scheme.onSurface,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (dimmed) {
                Icon(
                    Icons.Default.Close,
                    contentDescription = stringResource(R.string.practice_error_title),
                    tint = extras.practiceWrong,
                    modifier = Modifier.align(Alignment.TopStart).padding(5.dp).size(12.dp),
                )
            }
        }
    }
}

@Composable
fun GradeRow(
    onAgain: () -> Unit,
    onHard: () -> Unit,
    onGood: () -> Unit,
    onEasy: () -> Unit,
    enabled: Boolean = true,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        GradeSquare(stringResource(R.string.grade_again), GradeAgain, Modifier.weight(1f).testTag(TestTags.GRADE_AGAIN), onAgain, enabled)
        GradeSquare(stringResource(R.string.grade_hard), GradeHard, Modifier.weight(1f).testTag(TestTags.GRADE_HARD), onHard, enabled)
        GradeSquare(stringResource(R.string.grade_good), GradeLearning, Modifier.weight(1f).testTag(TestTags.GRADE_GOOD), onGood, enabled)
        GradeSquare(stringResource(R.string.grade_easy), GradeKnown, Modifier.weight(1f).testTag(TestTags.GRADE_EASY), onEasy, enabled)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GradeSquare(
    label: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
    enabled: Boolean = true,
) {
    Surface(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.height(56.dp),
        shape = RoundedCornerShape(12.dp),
        color = color,
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = Color.White,
                textAlign = TextAlign.Center,
                maxLines = 1,
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
    val body: @Composable () -> Unit = {
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
                        Spacer(Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.creating_card),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    "failed" -> {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            stringResource(R.string.creating_card_failed),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
            if (enrichmentStatus == "pending") {
                CircularProgressIndicator(
                    modifier = Modifier.size(22.dp),
                    strokeWidth = 2.5.dp,
                    color = MaterialTheme.colorScheme.primary,
                )
            } else {
                when {
                    !pos.isNullOrBlank() -> PosTagChip(pos)
                }
            }
        }
    }
    if (onClick != null) {
        AppCard(onClick = onClick, content = body)
    } else {
        AppCard(content = body)
    }
}

@Composable
fun EmptyState(message: String, subtitle: String? = null) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        subtitle?.let {
            Spacer(Modifier.height(8.dp))
            Text(
                it,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
    }
}
