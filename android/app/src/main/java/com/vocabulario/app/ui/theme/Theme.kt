package com.vocabulario.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Stonowane kolory ocen SRS */
val GradeHard = Color(0xFFB85C5C)
val GradeLearning = Color(0xFFC4894A)
val GradeKnown = Color(0xFF5A9E6F)
val ProgressMuted = Color(0xFF6B7280)

private val Indigo = Color(0xFF6366F1)
private val IndigoMuted = Color(0xFF7C83D4)
private val Slate50 = Color(0xFFF8FAFC)
private val SoftBg = Color(0xFF12161C)
private val SoftSurface = Color(0xFF1A222D)
private val SoftSurfaceVariant = Color(0xFF243041)
private val SoftOn = Color(0xFFE8EDF4)
private val SoftMuted = Color(0xFF9AA6B5)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEEF2FF),
    onPrimaryContainer = Color(0xFF312E81),
    secondary = Color(0xFF8B5CF6),
    background = Slate50,
    onBackground = Color(0xFF0F172A),
    surface = Color.White,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFF1F5F9),
    onSurfaceVariant = Color(0xFF475569),
    outline = Color(0xFFE2E8F0),
    outlineVariant = Color(0xFFF1F5F9),
)

private val DarkColors = darkColorScheme(
    primary = IndigoMuted,
    onPrimary = SoftOn,
    primaryContainer = Color(0xFF2A3148),
    onPrimaryContainer = SoftOn,
    secondary = Color(0xFF9B93C9),
    background = SoftBg,
    onBackground = SoftOn,
    surface = SoftSurface,
    onSurface = SoftOn,
    surfaceVariant = SoftSurfaceVariant,
    onSurfaceVariant = SoftMuted,
    outline = Color(0xFF3A4556),
    outlineVariant = SoftSurfaceVariant,
    error = GradeHard,
    onError = SoftOn,
)

private val AppTypography = Typography(
    displaySmall = TextStyle(fontSize = 32.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, lineHeight = 40.sp),
    headlineMedium = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.25).sp, lineHeight = 32.sp),
    headlineSmall = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.SemiBold, lineHeight = 30.sp),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold, lineHeight = 28.sp),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium, lineHeight = 24.sp),
    bodyLarge = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Normal, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Normal, lineHeight = 22.sp),
    bodySmall = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.Normal, lineHeight = 20.sp),
    labelLarge = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.1.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.3.sp, lineHeight = 16.sp),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp),
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
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
