package com.vocabulario.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
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

/** Brand palette from design swatches. */
val BrandBlueLight = Color(0xFF407DC0)
val BrandBlueDark = Color(0xFF8EC5FE)
val BrandTeal = Color(0xFF72AEAA)
val BrandCream = Color(0xFFFFF5DC)
val BrandInk = Color(0xFF000000)

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
val ChipPosLight = Color(0xFFFFF5DC)
val ChipStatusLight = Color(0xFFCAD3BB)
val ChipPosDark = Color(0xFF163A5C)
val ChipStatusDark = Color(0xFF575D9A)

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

val DmSans = FontFamily(
    Font(R.font.dmsans_regular, FontWeight.Normal),
    Font(R.font.dmsans_medium, FontWeight.Medium),
    Font(R.font.dmsans_semibold, FontWeight.SemiBold),
    Font(R.font.dmsans_bold, FontWeight.Bold),
)

private val LightBg = Color(0xFFF7F8FA)
private val LightSurface = Color(0xFFFFFFFF)
private val LightMuted = Color(0xFF5C6670)
private val LightBorder = Color(0xFFE2E6EA)
private val LightPrimaryContainer = Color(0xFFD9E8F7)

private val DarkBg = Color(0xFF000000)
private val DarkSurface = Color(0xFF141618)
private val DarkSurface2 = Color(0xFF1E2226)
private val DarkMuted = Color(0xFFB8BFC7)
private val DarkBorder = Color(0xFF2A3036)
private val DarkPrimaryContainer = Color(0xFF1A3350)

private val LightColors = lightColorScheme(
    primary = BrandBlueLight,
    onPrimary = Color.White,
    primaryContainer = LightPrimaryContainer,
    onPrimaryContainer = Color(0xFF163A5C),
    secondary = BrandTeal,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD8ECEB),
    onSecondaryContainer = Color(0xFF1F3F3D),
    tertiary = ActionConfirm,
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD8F5D5),
    onTertiaryContainer = Color(0xFF1B4D18),
    background = LightBg,
    onBackground = BrandInk,
    surface = LightSurface,
    onSurface = BrandInk,
    surfaceVariant = Color(0xFFEEF1F4),
    onSurfaceVariant = LightMuted,
    outline = LightBorder,
    outlineVariant = Color(0xFFF0F2F4),
    error = ActionCancel,
    onError = Color.White,
    errorContainer = Color(0xFFF6D7E3),
    onErrorContainer = Color(0xFF5A1833),
)

private val DarkColors = darkColorScheme(
    primary = BrandBlueDark,
    onPrimary = Color(0xFF0A1E33),
    primaryContainer = DarkPrimaryContainer,
    onPrimaryContainer = BrandCream,
    secondary = BrandTeal,
    onSecondary = Color(0xFF0C2423),
    secondaryContainer = Color(0xFF1C3332),
    onSecondaryContainer = Color(0xFFD8ECEB),
    tertiary = ActionConfirm,
    onTertiary = Color(0xFF0C2A0A),
    tertiaryContainer = Color(0xFF1E4A1B),
    onTertiaryContainer = Color(0xFFD8F5D5),
    background = DarkBg,
    onBackground = BrandCream,
    surface = DarkSurface,
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

private fun type(
    size: Int,
    weight: FontWeight,
    line: Int,
    tracking: Double = 0.0,
) = TextStyle(
    fontFamily = DmSans,
    fontSize = size.sp,
    fontWeight = weight,
    lineHeight = line.sp,
    letterSpacing = tracking.sp,
)

private val AppTypography = Typography(
    displaySmall = type(32, FontWeight.Bold, 40, -0.5),
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

@Composable
fun VocabularioTheme(
    themeMode: String = "system",
    content: @Composable () -> Unit,
) {
    val darkTheme = when (themeMode) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    val extras = if (darkTheme) {
        VocabExtraColors(
            chipPosContainer = ChipPosDark,
            chipPosOnContainer = BrandCream,
            chipStatusContainer = ChipStatusDark,
            chipStatusOnContainer = BrandCream,
            importLemma = Color(0xFF9EC9F5),
        )
    } else {
        VocabExtraColors(
            chipPosContainer = ChipPosLight,
            chipPosOnContainer = BrandInk,
            chipStatusContainer = ChipStatusLight,
            chipStatusOnContainer = BrandInk,
            importLemma = Color(0xFF2C5F94),
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
