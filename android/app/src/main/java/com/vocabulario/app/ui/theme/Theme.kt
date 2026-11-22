package com.vocabulario.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import com.vocabulario.app.R
import com.vocabulario.app.data.normalizePosKey

/** Brand palette from design swatches. */
val BrandBlueLight = Color(0xFF5F6ABE)
val BrandBlueDark = Color(0xFF9BABAC)
val BrandTeal = Color(0xFF72AEAA)
val BrandCream = Color(0xFFE1E2E6)
val BrandInk = Color(0xFF2D3039)

/** Shared action colors (cancel / confirm) — both themes. */
val ActionCancel = Color(0xFFBF557F)
val ActionConfirm = Color(0xFF569252)
val ActionTeal = Color(0xFF74AEAB)

val GradeAgain = ActionCancel
val GradeHard = Color(0xFFB85C5C)
val GradeLearning = Color(0xFFC4894A)
val GradeKnown = ActionConfirm
val ProgressMuted = Color(0xFF6B7280)

/** List tile chip palette (POS ≠ status). */
val ChipPosLight = Color(0xFFD7F1EB)
val ChipStatusLight = Color(0xFFF4DEDF)
val ChipPosDark = Color(0xFF54543B)
val ChipStatusDark = Color(0xFF4C4C5D)

data class VocabExtraColors(
    val chipPosContainer: Color,
    val chipPosOnContainer: Color,
    val chipStatusContainer: Color,
    val chipStatusOnContainer: Color,
    val importLemma: Color,
)

val LocalVocabExtraColors = staticCompositionLocalOf {
    VocabExtraColors(
        chipPosContainer = ChipPosLight,
        chipPosOnContainer = BrandInk,
        chipStatusContainer = ChipStatusLight,
        chipStatusOnContainer = BrandInk,
        importLemma = BrandBlueLight,
    )
}

val Inter = FontFamily(
    Font(R.font.inter_regular, FontWeight.Normal),
    Font(R.font.inter_medium, FontWeight.Medium),
    Font(R.font.inter_semibold, FontWeight.SemiBold),
    Font(R.font.inter_bold, FontWeight.Bold),
)

private val LightBg = Color(0xFFF1F5F4)
private val LightSurface = Color(0xFFFFFEFA)
private val LightMuted = Color(0xFF535B67)
private val LightBorder = Color(0xFFDFE1E5)
private val LightPrimaryContainer = Color(0xFFD7D9EB)

private val DarkBg = Color(0xFF20232A)
private val DarkSurface = Color(0xFF292D35)
private val DarkSurface2 = Color(0xFF2C3239)
private val DarkMuted = Color(0xFFC4C9D1)
private val DarkBorder = Color(0xFF424853)
private val DarkPrimaryContainer = Color(0xFF323C41)

internal val LightColors = lightColorScheme(
    primary = BrandBlueLight,
    onPrimary = LightSurface,
    primaryContainer = LightPrimaryContainer,
    onPrimaryContainer = BrandInk,
    secondary = Color(0xFFD17E8E),
    onSecondary = BrandInk,
    secondaryContainer = ChipStatusLight,
    onSecondaryContainer = BrandInk,
    tertiary = Color(0xFF5FCBBF),
    onTertiary = BrandInk,
    tertiaryContainer = ChipPosLight,
    onTertiaryContainer = BrandInk,
    background = LightBg,
    onBackground = BrandInk,
    surface = LightSurface,
    surfaceContainerLowest = LightSurface,
    surfaceContainerLow = LightSurface,
    surfaceContainer = LightSurface,
    surfaceContainerHigh = Color(0xFFF6F6F7),
    surfaceContainerHighest = Color(0xFFF6F6F7),
    onSurface = BrandInk,
    surfaceVariant = Color(0xFFF6F6F7),
    onSurfaceVariant = LightMuted,
    outline = LightBorder,
    outlineVariant = Color(0xFFF0F2F4),
    error = ActionCancel,
    onError = Color.White,
    errorContainer = Color(0xFFF6D7E3),
    onErrorContainer = Color(0xFF5A1833),
)

internal val DarkColors = darkColorScheme(
    primary = BrandBlueDark,
    onPrimary = DarkBg,
    primaryContainer = DarkPrimaryContainer,
    onPrimaryContainer = BrandCream,
    secondary = Color(0xFFBCB7D6),
    onSecondary = DarkBg,
    secondaryContainer = ChipStatusDark,
    onSecondaryContainer = BrandCream,
    tertiary = Color(0xFFD0CB6E),
    onTertiary = DarkBg,
    tertiaryContainer = ChipPosDark,
    onTertiaryContainer = BrandCream,
    background = DarkBg,
    onBackground = BrandCream,
    surface = DarkSurface,
    surfaceContainerLowest = DarkBg,
    surfaceContainerLow = DarkSurface,
    surfaceContainer = DarkSurface,
    surfaceContainerHigh = DarkSurface2,
    surfaceContainerHighest = DarkSurface2,
    onSurface = BrandCream,
    surfaceVariant = DarkSurface2,
    onSurfaceVariant = DarkMuted,
    outline = DarkBorder,
    outlineVariant = Color(0xFF1A1E22),
    error = ActionCancel,
    onError = Color.White,
    errorContainer = Color(0xFF4A2033),
    onErrorContainer = Color(0xFFF6D7E3),
)

fun posChipContainer(scheme: ColorScheme, pos: String?): Color = when (normalizePosKey(pos)) {
    "noun" -> scheme.secondaryContainer
    "phrase", "construction" -> scheme.primaryContainer
    else -> scheme.tertiaryContainer
}

private fun type(
    size: Int,
    weight: FontWeight,
    line: Int,
    tracking: Double = 0.0,
) = TextStyle(
    fontFamily = Inter,
    fontSize = size.sp,
    fontWeight = weight,
    lineHeight = line.sp,
    letterSpacing = tracking.sp,
)

private val AppTypography = Typography(
    displayLarge = Typography().displayLarge.copy(fontFamily = Inter),
    displayMedium = Typography().displayMedium.copy(fontFamily = Inter),
    displaySmall = type(32, FontWeight.Bold, 40, -0.5),
    headlineLarge = Typography().headlineLarge.copy(fontFamily = Inter),
    headlineMedium = type(26, FontWeight.Bold, 32, -0.3),
    headlineSmall = type(22, FontWeight.SemiBold, 28),
    titleLarge = type(20, FontWeight.SemiBold, 28),
    titleMedium = type(16, FontWeight.SemiBold, 24),
    titleSmall = type(14, FontWeight.SemiBold, 20),
    bodyLarge = type(16, FontWeight.Normal, 24),
    bodyMedium = type(14, FontWeight.Normal, 22),
    bodySmall = type(13, FontWeight.Normal, 18),
    labelLarge = type(14, FontWeight.SemiBold, 20, 0.1),
    labelMedium = type(12, FontWeight.Medium, 16, 0.2),
    labelSmall = type(11, FontWeight.Medium, 14, 0.2),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(12.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

internal fun usesDarkTheme(themeMode: String, systemDark: Boolean): Boolean = when (themeMode) {
    "dark" -> true
    "light" -> false
    else -> systemDark
}

@Composable
fun VocabularioTheme(
    themeMode: String = "system",
    content: @Composable () -> Unit,
) {
    val darkTheme = usesDarkTheme(themeMode, isSystemInDarkTheme())
    val extras = if (darkTheme) {
        VocabExtraColors(
            chipPosContainer = ChipPosDark,
            chipPosOnContainer = BrandCream,
            chipStatusContainer = ChipStatusDark,
            chipStatusOnContainer = BrandCream,
            importLemma = BrandBlueDark,
        )
    } else {
        VocabExtraColors(
            chipPosContainer = ChipPosLight,
            chipPosOnContainer = BrandInk,
            chipStatusContainer = ChipStatusLight,
            chipStatusOnContainer = BrandInk,
            importLemma = BrandBlueLight,
        )
    }
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = view.context.findActivity()?.window ?: return@SideEffect
            val insets = WindowCompat.getInsetsController(window, view)
            insets.isAppearanceLightStatusBars = !darkTheme
            insets.isAppearanceLightNavigationBars = !darkTheme
        }
    }
    CompositionLocalProvider(LocalVocabExtraColors provides extras) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColors else LightColors,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}

private fun android.content.Context.findActivity(): android.app.Activity? {
    var ctx: android.content.Context = this
    while (ctx is android.content.ContextWrapper) {
        if (ctx is android.app.Activity) return ctx
        ctx = ctx.baseContext
    }
    return null
}
